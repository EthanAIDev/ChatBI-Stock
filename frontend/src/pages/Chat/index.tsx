import { useState, useRef, useEffect, useCallback } from 'react';
import { Input, Button, message as antMessage, Typography } from 'antd';
import { SendOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import Sidebar from '../../components/Sidebar';
import ChatMessageBox from '../../components/ChatMessageBox';
import { useChatStore } from '../../stores/chatStore';
import { getSessions, createSession, getMessages } from '../../services/session';
import { useSSE } from '../../hooks/useSSE';
import type { SSEState } from '../../hooks/useSSE';
import type { ChatMessage, ChatSession } from '../../types';

const { Text } = Typography;

interface StreamingEntry {
  userMsg: ChatMessage;
  assistantMsg: ChatMessage;
  loading: boolean;
}

export default function ChatPage() {
  const [inputValue, setInputValue] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [streamingSessions, setStreamingSessions] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const shouldJumpToBottomRef = useRef(false);
  const streamingCacheRef = useRef<Map<string, StreamingEntry>>(new Map());
  const { startStream } = useSSE();
  const {
    sessions,
    messages,
    activeSessionId,
    loading,
    completedSessions,
    setSessions,
    setMessages,
    setActiveSession,
    addMessage,
    setLoading,
  } = useChatStore();

  const loadSessions = useCallback(async () => {
    try {
      const res = await getSessions();
      if (res.code === 0) setSessions(res.data as ChatSession[]);
    } catch { /* ignore */ }
  }, [setSessions]);

  useEffect(() => { void loadSessions(); }, [loadSessions]);

  useEffect(() => {
    const shouldJump = shouldJumpToBottomRef.current || streamingSessions.has(activeSessionId || '');
    if (shouldJump) {
      const container = messagesContainerRef.current;
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    shouldJumpToBottomRef.current = false;
  }, [messages, streamingSessions]);

  const initializedRef = useRef(false);
  useEffect(() => {
    if (!initializedRef.current && sessions.length > 0 && !activeSessionId) {
      initializedRef.current = true;
      shouldJumpToBottomRef.current = true;
      const firstId = sessions[0].session_id;
      setActiveSession(firstId);
      getMessages(firstId).then((res) => {
        if (res.code === 0) setMessages(res.data as ChatMessage[]);
      }).catch(() => {});
    }
  }, [sessions, activeSessionId, setActiveSession, setMessages]);

  const applyStreamingCache = useCallback((sessionId: string) => {
    const entry = streamingCacheRef.current.get(sessionId);
    if (!entry) return;
    const store = useChatStore.getState();
    if (store.activeSessionId === sessionId) {
      const existingUser = store.messages.findIndex((m) => m.id === entry.userMsg.id);
      if (existingUser < 0) {
        addMessage(entry.userMsg);
      }
      const existingAsst = store.messages.findIndex((m) => m.id === entry.assistantMsg.id);
      if (existingAsst >= 0) {
        store.updateMessage(entry.assistantMsg.id, entry.assistantMsg);
      } else {
        addMessage(entry.assistantMsg);
      }
      if (entry.loading) {
        setLoading(true);
      }
    }
  }, [addMessage, setLoading]);

  const refreshSessionMessages = useCallback(async (sessionId: string, activate = false) => {
    if (activate) {
      setActiveSession(sessionId);
    }
    try {
      const res = await getMessages(sessionId);
      const store = useChatStore.getState();
      if (res.code === 0 && store.activeSessionId === sessionId) {
        setMessages(res.data as ChatMessage[]);
      }
    } catch { /* ignore */ }
  }, [setActiveSession, setMessages]);

  const selectSession = useCallback(async (sessionId: string) => {
    const store = useChatStore.getState();
    store.clearSessionCompleted(sessionId);
    shouldJumpToBottomRef.current = true;
    await refreshSessionMessages(sessionId, true);
    applyStreamingCache(sessionId);
  }, [refreshSessionMessages, applyStreamingCache]);

  const refreshCurrentSessionAfterStream = useCallback(async (sessionId: string) => {
    await loadSessions();
    await refreshSessionMessages(sessionId);
  }, [loadSessions, refreshSessionMessages]);

  const handleNewSession = async (): Promise<string | null> => {
    try {
      const res = await createSession();
      if (res.code === 0) {
        await loadSessions();
        shouldJumpToBottomRef.current = true;
        setMessages([]);
        setActiveSession(res.data.session_id);
        return res.data.session_id;
      }
      return null;
    } catch {
      antMessage.error('创建对话失败');
      return null;
    }
  };

  const handleSend = async () => {
    const question = inputValue.trim();
    if (!question) return;
    let sid = activeSessionId;
    if (!sid) {
      sid = await handleNewSession();
      if (!sid) return;
    }
    setInputValue('');
    const store = useChatStore.getState();
    store.setLoading(true);
    const userMsgId = Date.now();
    const assistantMsgId = userMsgId + 1;

    const assistantMsg: ChatMessage = {
      id: assistantMsgId, role: 'assistant', content: '',
      sql_text: null, result_preview: null, chart_path: null, status_text: '正在思考...', render_key: 0,
      created_at: new Date().toISOString(),
    };

    const userMsg: ChatMessage = {
      id: userMsgId, role: 'user', content: question,
      sql_text: null, result_preview: null, chart_path: null, status_text: null, render_key: 0,
      created_at: new Date().toISOString(),
    };

    streamingCacheRef.current.set(sid, { userMsg, assistantMsg, loading: true });
    setStreamingSessions((prev) => {
      const next = new Set(prev);
      next.add(sid);
      return next;
    });

    addMessage(userMsg);
    addMessage(assistantMsg);

    startStream(sid, question, (sseState: SSEState) => {
      const currentStore = useChatStore.getState();
      const isActiveSession = sid === currentStore.activeSessionId;

      if (sseState.status === 'error') {
        streamingCacheRef.current.delete(sid);
        setStreamingSessions((prev) => {
          const next = new Set(prev);
          next.delete(sid);
          return next;
        });
        if (isActiveSession) {
          currentStore.updateMessage(assistantMsgId, { content: sseState.content || '请求失败，请稍后重试。', status_text: '' });
        }
        currentStore.setLoading(false);
        return;
      }
      if (sseState.status === 'done') {
        streamingCacheRef.current.delete(sid);
        setStreamingSessions((prev) => {
          const next = new Set(prev);
          next.delete(sid);
          return next;
        });
        if (!isActiveSession) {
          currentStore.markSessionCompleted(sid);
          currentStore.setLoading(false);
          void loadSessions();
          return;
        }
        currentStore.updateMessage(assistantMsgId, {
          content: sseState.content,
          sql_text: sseState.sqlText,
          result_preview: sseState.resultPreview,
          chart_path: sseState.chartUrl,
          status_text: null,
          render_key: Date.now(),
        });
        currentStore.setLoading(false);
        void refreshCurrentSessionAfterStream(sid);
        return;
      }

      const updatedMsg: ChatMessage = {
        id: assistantMsgId, role: 'assistant',
        content: sseState.content,
        sql_text: sseState.sqlText,
        result_preview: sseState.resultPreview,
        chart_path: sseState.chartUrl,
        status_text: sseState.statusText || '查询中...',
        render_key: 0,
        created_at: assistantMsg.created_at,
      };
      streamingCacheRef.current.set(sid, { userMsg, assistantMsg: updatedMsg, loading: true });

      if (isActiveSession) {
        currentStore.updateMessage(assistantMsgId, {
          content: updatedMsg.content,
          status_text: updatedMsg.status_text,
        });
      }
    });
  };

  const handleSuggestion = (text: string) => setInputValue(text);
  const handleRefreshSessions = () => loadSessions();
  const handleDeleteActive = () => { setMessages([]); setActiveSession(null); };
  const activeSessionTitle = sessions.find((session) => session.session_id === activeSessionId)?.title || '当前对话';
  let latestUserQuestion = '';
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role === 'user' && message.content.trim()) {
      latestUserQuestion = message.content;
      break;
    }
  }

  return (
    <div className="app-page" style={{ display: 'flex', height: '100%', position: 'relative', background: 'var(--bg-app)' }}>
      {/* Sidebar */}
      {!sidebarCollapsed && (
        <div style={{ width: 280, borderRight: '1px solid var(--border-color)', flexShrink: 0, background: 'var(--bg-subtle)' }}>
          <Sidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            completedSessions={completedSessions}
            streamingSessions={streamingSessions}
            onSelectSession={(id) => { selectSession(id); }}
            onNewSession={handleNewSession}
            onSuggestion={handleSuggestion}
            onRefresh={handleRefreshSessions}
            onDeleteActive={handleDeleteActive}
            onCollapse={() => setSidebarCollapsed(true)}
          />
        </div>
      )}

      {/* Chat area */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        marginLeft: sidebarCollapsed ? 48 : 0,
      }}>
        {sidebarCollapsed && (
          <div style={{ position: 'absolute', left: 8, top: 12, zIndex: 10 }}>
            <Button
              type="text"
              size="small"
              icon={<MenuUnfoldOutlined />}
              onClick={() => setSidebarCollapsed(false)}
              style={{ color: 'var(--text-secondary)', background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', borderRadius: 8 }}
            />
          </div>
        )}
        <div style={{
          minHeight: 52,
          padding: '12px clamp(16px, 5vw, 120px) 10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <Text
            style={{
              display: 'block',
              maxWidth: 768,
              fontSize: 17,
              fontWeight: 600,
              color: 'var(--text-primary)',
              textAlign: 'center',
            }}
            ellipsis={{ tooltip: activeSessionTitle }}
          >
            {activeSessionTitle}
          </Text>
        </div>

        {/* Messages */}
        <div ref={messagesContainerRef} style={{
          flex: 1,
          overflow: 'auto',
          padding: '18px clamp(16px, 5vw, 120px) 170px',
          background: 'var(--bg-app)',
        }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', marginTop: '15vh', color: 'var(--text-secondary)' }}>
              <h2 style={{ color: 'var(--text-primary)', fontSize: 26, fontWeight: 700, marginBottom: 12 }}>
                欢迎使用 ChatBI 股票查询助手
              </h2>
              <Text type="secondary" style={{ fontSize: 16 }}>
                输入股票分析问题开始对话，或从左侧推荐问题中选择
              </Text>
            </div>
          )}

          <div style={{ maxWidth: 768, margin: '0 auto' }}>
            {latestUserQuestion && (
              <div className="panel-surface" style={{
                marginBottom: 18,
                padding: '12px 14px',
                borderRadius: 10,
                background: 'var(--bg-soft)',
                border: '1px solid var(--border-color)',
              }}>
                <Text type="secondary" style={{ display: 'block', marginBottom: 6, fontSize: 13 }}>
                  你刚刚的问题
                </Text>
                <div style={{ color: 'var(--text-primary)', fontSize: 16, lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
                  {latestUserQuestion}
                </div>
              </div>
            )}
            {messages.map((msg) => (
              <ChatMessageBox key={`${msg.id}-${msg.render_key || msg.id}`} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input area */}
        <div style={{
          position: 'sticky',
          bottom: 0,
          zIndex: 5,
          padding: '0 clamp(16px, 5vw, 120px) 16px',
          background: 'transparent',
        }}>
          <div
            className="panel-surface"
            style={{
              maxWidth: 768,
              margin: '0 auto',
              padding: '12px 12px 10px',
              borderRadius: 16,
              background: 'color-mix(in srgb, var(--bg-elevated) 90%, transparent)',
              boxShadow: '0 18px 36px rgba(2, 8, 24, 0.45)',
            }}
          >
            <Input.TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPressEnter={(e) => {
                if (!e.shiftKey) { e.preventDefault(); handleSend(); }
              }}
              placeholder="输入股票分析问题，例如：比较2024年1月贵州茅台和五粮液的平均收盘价"
              autoSize={{ minRows: 2, maxRows: 4 }}
              style={{ borderRadius: 10, fontSize: 16, background: 'var(--bg-soft)' }}
            />
            <div style={{ marginTop: 8, minHeight: 38, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
              <Text
                type="secondary"
                style={{
                  position: 'absolute',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  fontSize: 12,
                  lineHeight: '38px',
                  textAlign: 'center',
                  pointerEvents: 'none',
                }}
              >
                内容由AI生成，请仔细甄别
              </Text>
              {loading && (
                <Text type="secondary" style={{ marginRight: 12, lineHeight: '38px', fontSize: 13 }}>
                  模型回复中...
                </Text>
              )}
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!inputValue.trim()}
                loading={loading}
                style={{ borderRadius: 10, minWidth: 92 }}
              >
                发送
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
