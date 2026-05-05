import { useMemo, useState } from 'react';
import { List, Button, Typography, Divider, Tag, Input, Dropdown, Modal, message, Avatar } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CheckOutlined, CloseOutlined, EllipsisOutlined, PushpinOutlined, LogoutOutlined, MenuFoldOutlined, SettingOutlined, LoadingOutlined, CommentOutlined, LineChartOutlined } from '@ant-design/icons';
import type { ChatSession } from '../types';
import { renameSession, deleteSession, pinSession } from '../services/session';
import { useAuthStore } from '../stores/authStore';
import { useNavigate } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';

const { Text } = Typography;
const SUGGESTIONS = [
  '查询贵州茅台从2025-01-01到2025-01-31的收盘价走势',
  '比较2024年1月贵州茅台、五粮液、中芯国际、广发证券的平均收盘价',
  '查询中芯国际历史最高收盘价及对应日期',
];

interface SidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  completedSessions: Set<string>;
  streamingSessions: Set<string>;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onSuggestion: (text: string) => void;
  onRefresh: () => void;
  onDeleteActive: () => void;
  onCollapse: () => void;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function getSessionGroupLabel(updatedAt: string): '今天' | '昨天' | '7日内' | '更早' {
  const sessionDate = new Date(updatedAt);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - DAY_MS;
  const sevenDaysStart = todayStart - DAY_MS * 7;
  const sessionTime = sessionDate.getTime();

  if (sessionTime >= todayStart) {
    return '今天';
  }
  if (sessionTime >= yesterdayStart) {
    return '昨天';
  }
  if (sessionTime >= sevenDaysStart) {
    return '7日内';
  }
  return '更早';
}

export default function Sidebar({ sessions, activeSessionId, completedSessions, streamingSessions, onSelectSession, onNewSession, onSuggestion, onRefresh, onDeleteActive, onCollapse }: SidebarProps) {
  const navigate = useNavigate();
  const username = useAuthStore((s) => s.username);
  const role = useAuthStore((s) => s.role);
  const logout = useAuthStore((s) => s.logout);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

  const sortedSessions = useMemo(
    () => [...sessions].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()),
    [sessions],
  );

  const pinnedSessions = sortedSessions.filter((session) => session.is_pinned);
  const normalSessions = sortedSessions.filter((session) => !session.is_pinned);
  const groupedSessions = [
    { label: '置顶', sessions: pinnedSessions },
    ...['今天', '昨天', '7日内', '更早'].map((label) => ({
      label,
      sessions: normalSessions.filter((session) => getSessionGroupLabel(session.updated_at) === label),
    })),
  ].filter((group) => group.sessions.length > 0);

  const startRename = (e: React.MouseEvent, session: ChatSession) => {
    e.stopPropagation();
    setEditingId(session.session_id);
    setEditValue(session.title);
  };

  const confirmRename = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const title = editValue.trim();
    if (title && editingId) {
      const res = await renameSession(editingId, title);
      if (res.code === 0) {
        message.success('已重命名');
        onRefresh();
      }
    }
    setEditingId(null);
  };

  const cancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const handleDelete = async (e: React.MouseEvent | undefined, sessionId: string) => {
    e?.stopPropagation();
    const res = await deleteSession(sessionId);
    if (res.code === 0) {
      message.success('已删除');
      if (sessionId === activeSessionId) {
        onDeleteActive();
      }
      onRefresh();
    }
  };

  const confirmDeleteSession = (e: React.MouseEvent | undefined, sessionId: string) => {
    e?.stopPropagation();
    Modal.confirm({
      title: '确认删除该对话？',
      content: '删除后无法恢复',
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        await handleDelete(undefined, sessionId);
      },
      onCancel: () => setMenuOpenId(null),
    });
  };

  const handlePinToggle = async (e: React.MouseEvent | undefined, session: ChatSession) => {
    e?.stopPropagation();
    const nextPinned = !session.is_pinned;
    const res = await pinSession(session.session_id, nextPinned);
    if (res.code === 0) {
      message.success(nextPinned ? '已置顶' : '已取消置顶');
      onRefresh();
    }
    setMenuOpenId(null);
  };

  const userDisplayName = username || '访客';
  const userInitial = userDisplayName.trim().charAt(0).toUpperCase() || 'U';
  const newChatIcon = (
    <span style={{ position: 'relative', width: 16, height: 16, display: 'inline-block' }}>
      <CommentOutlined style={{ fontSize: 16, lineHeight: 1 }} />
      <PlusOutlined
        style={{
          position: 'absolute',
          right: -3,
          top: -4,
          fontSize: 9,
          padding: 1,
          borderRadius: '50%',
          background: 'rgba(255, 255, 255, 0.96)',
          color: 'var(--primary-color)',
        }}
      />
    </span>
  );
  const userMenuItems = useMemo(() => {
    const items: Array<{ key: string; danger?: boolean; label: React.ReactNode }> = [];
    if (role === 'admin' || role === 'superadmin') {
      items.push({
        key: 'admin',
        label: (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <SettingOutlined />
            <span>后台管理</span>
          </span>
        ),
      });
    }
    items.push({
      key: 'logout',
      danger: true,
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <LogoutOutlined />
          <span>退出登录</span>
        </span>
      ),
    });
    return items;
  }, [role]);

  return (
    <div className="app-page" style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 16, background: 'var(--bg-subtle)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
        <Typography.Title level={4} style={{ marginBottom: 0, color: 'var(--text-primary)' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <LineChartOutlined style={{ color: 'var(--primary-color)', fontSize: 18 }} />
            <span>ChatBI</span>
          </span>
        </Typography.Title>
        <Button
          type="text"
          size="small"
          icon={<MenuFoldOutlined />}
          onClick={onCollapse}
          style={{ color: 'var(--text-secondary)', flexShrink: 0 }}
        />
      </div>

      <Button type="primary" icon={newChatIcon} block onClick={onNewSession} style={{ marginBottom: 16 }}>
        新建对话
      </Button>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {groupedSessions.map((group) => (
          <div key={group.label} style={{ marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 13 }}>
              {group.label}
            </Text>
            <List
              size="small"
              dataSource={group.sessions}
              renderItem={(session) => {
                const isEditing = editingId === session.session_id;
                const isActive = session.session_id === activeSessionId;
                const isCompleted = completedSessions.has(session.session_id) && !isActive;
                const isStreaming = streamingSessions.has(session.session_id) && !isActive;
                const activeTextColor = 'var(--primary-color)';
                const isPinned = !!session.is_pinned;
                const showActions = !isEditing && (hoveredId === session.session_id || menuOpenId === session.session_id);
                const actionItems = [
                  {
                    key: 'pin',
                    label: (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                        <PushpinOutlined />
                        <span>{isPinned ? '取消置顶' : '置顶'}</span>
                      </span>
                    ),
                  },
                  {
                    key: 'rename',
                    label: (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                        <EditOutlined />
                        <span>重命名</span>
                      </span>
                    ),
                  },
                  {
                    key: 'delete',
                    danger: true,
                    label: (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                        <DeleteOutlined />
                        <span>删除</span>
                      </span>
                    ),
                  },
                ];

                return (
                  <List.Item
                    onClick={() => !isEditing && onSelectSession(session.session_id)}
                    onMouseEnter={() => setHoveredId(session.session_id)}
                    onMouseLeave={() => setHoveredId((current) => (current === session.session_id ? null : current))}
                    style={{
                      cursor: isEditing ? 'default' : 'pointer',
                      padding: '6px 12px',
                      borderRadius: 10,
                      background: isActive ? 'var(--primary-soft)' : 'transparent',
                      border: isActive ? '1px solid rgba(91,140,255,0.45)' : '1px solid transparent',
                      marginTop: 6,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      color: isActive ? activeTextColor : undefined,
                    }}
                  >
                    {isEditing ? (
                      <Input
                        size="small"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onPressEnter={(e) => confirmRename(e as unknown as React.MouseEvent)}
                        style={{ flex: 1, fontSize: 14 }}
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                        suffix={
                          <span style={{ display: 'flex', gap: 2 }}>
                            <Button type="text" size="small" icon={<CheckOutlined style={{ fontSize: 13, color: 'var(--success-color)' }} />} onClick={confirmRename} />
                            <Button type="text" size="small" icon={<CloseOutlined style={{ fontSize: 13, color: 'var(--text-secondary)' }} />} onClick={cancelRename} />
                          </span>
                        }
                      />
                    ) : (
                      <>
                        <Text ellipsis style={{ fontSize: 14, lineHeight: 1.35, flex: 1, minWidth: 0, color: isActive ? activeTextColor : undefined, fontWeight: isActive ? 600 : 400 }}>
                          {isStreaming && (
                            <LoadingOutlined style={{
                              color: 'var(--primary-color)',
                              marginRight: 6,
                              verticalAlign: 'middle',
                              position: 'relative',
                              top: -1,
                              fontSize: 13,
                            }} />
                          )}
                          {isCompleted && !isStreaming && (
                            <span style={{
                              display: 'inline-block',
                              width: 6,
                              height: 6,
                              borderRadius: '50%',
                              background: 'var(--primary-color)',
                              marginRight: 6,
                              verticalAlign: 'middle',
                              position: 'relative',
                              top: -1,
                            }} />
                          )}
                          {session.title}
                        </Text>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                          {isPinned && <PushpinOutlined style={{ fontSize: 13, color: 'var(--primary-color)' }} />}
                          <Dropdown
                            menu={{
                              items: actionItems,
                              onClick: ({ key, domEvent }) => {
                                const clickEvent = domEvent as unknown as React.MouseEvent;
                                if (key === 'pin') {
                                  void handlePinToggle(clickEvent, session);
                                }
                                if (key === 'rename') {
                                  startRename(clickEvent, session);
                                }
                                if (key === 'delete') {
                                  confirmDeleteSession(clickEvent, session.session_id);
                                }
                              },
                            }}
                            trigger={['click']}
                            open={menuOpenId === session.session_id}
                            onOpenChange={(open) => setMenuOpenId(open ? session.session_id : null)}
                          >
                            <Button
                              type="text"
                              size="small"
                              icon={<EllipsisOutlined style={{ fontSize: 16 }} />}
                              onClick={(e) => e.stopPropagation()}
                              style={{
                                opacity: showActions ? 1 : 0,
                                pointerEvents: showActions ? 'auto' : 'none',
                                color: isActive ? activeTextColor : 'var(--text-secondary)',
                              }}
                            />
                          </Dropdown>
                        </span>
                      </>
                    )}
                  </List.Item>
                );
              }}
            />
          </div>
        ))}
      </div>

      <Divider style={{ margin: '12px 0' }} />
      <Text type="secondary" style={{ fontSize: 13, marginBottom: 8 }}>
        推荐问题
      </Text>
      {SUGGESTIONS.map((text) => (
        <Tag
          key={text}
          style={{
            cursor: 'pointer',
            marginBottom: 6,
            maxWidth: '100%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            fontSize: 14,
            lineHeight: '22px',
            paddingInline: 10,
          }}
          onClick={() => onSuggestion(text)}
        >
          {text.length > 30 ? text.slice(0, 30) + '...' : text}
        </Tag>
      ))}

      <Divider style={{ margin: '12px 0' }} />
      <div
        className="panel-surface"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 12px',
          borderRadius: 10,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-color)',
          marginTop: 'auto',
        }}
      >
        <Avatar
          style={{
            backgroundColor: 'var(--primary-soft)',
            color: 'var(--primary-color)',
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {userInitial}
        </Avatar>
        <Text
          ellipsis={{ tooltip: userDisplayName }}
          style={{ flex: 1, minWidth: 0, fontSize: 14, color: 'var(--text-primary)', fontWeight: 500 }}
        >
          {userDisplayName}
        </Text>
        <ThemeToggle compact />
        <Dropdown
          trigger={['click']}
          menu={{
            items: userMenuItems,
            onClick: ({ key, domEvent }) => {
              (domEvent as unknown as React.MouseEvent).stopPropagation();
              if (key === 'admin') {
                navigate('/admin');
              }
              if (key === 'logout') {
                logout();
                navigate('/login', { replace: true });
              }
            },
          }}
        >
          <Button
            type="text"
            size="small"
            icon={<EllipsisOutlined style={{ fontSize: 16 }} />}
            onClick={(e) => e.stopPropagation()}
            style={{ color: 'var(--text-secondary)' }}
          />
        </Dropdown>
      </div>
    </div>
  );
}
