import { Avatar, Typography, Spin } from 'antd';
import { UserOutlined, RobotOutlined, LoadingOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { Streamdown } from 'streamdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import DataTable from './DataTable';
import SqlBlock from './SqlBlock';

const { Text } = Typography;

interface ChatMessageItem {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  sql_text?: string | null;
  result_preview?: string | null;
  chart_path?: string | null;
  status_text?: string | null;
  render_key?: number;
}

interface ChatMessageProps {
  message: ChatMessageItem;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isStreaming = !isUser && message.status_text !== null && message.status_text !== undefined && message.status_text !== '';

  const avatar = (
    <Avatar
      icon={isUser ? <UserOutlined /> : <RobotOutlined />}
      size={38}
      style={{
        backgroundColor: isUser ? 'var(--primary-color)' : 'var(--success-color)',
        flexShrink: 0,
        boxShadow: `0 4px 12px ${isUser ? 'rgba(37,99,235,0.25)' : 'rgba(22,163,74,0.24)'}`,
      }}
    />
  );

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 28,
      padding: '0 2px',
    }}>
      {!isUser && avatar}
      <div style={{ maxWidth: '85%', minWidth: 0, marginLeft: isUser ? 0 : 14, marginRight: isUser ? 14 : 0 }}>
        <Text
          type="secondary"
          style={{ fontSize: 13, marginBottom: 4, display: 'block', fontWeight: 500, textAlign: isUser ? 'right' : 'left' }}
        >
          {isUser ? '你' : 'ChatBI 助手'}
        </Text>
        <div
          className={isUser ? '' : 'markdown-body'}
          style={{
            background: isUser ? 'linear-gradient(135deg, var(--primary-color) 0%, #3b82f6 100%)' : 'var(--bg-elevated)',
            color: isUser ? '#fff' : 'var(--text-primary)',
            padding: '14px 20px',
            borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
            border: isUser ? 'none' : '1px solid var(--border-color)',
            boxShadow: isUser ? '0 8px 16px rgba(37,99,235,0.25)' : '0 8px 20px rgba(15,23,42,0.06)',
            lineHeight: 1.8,
            fontSize: 16,
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
            overflow: 'hidden',
          }}
        >
          {!message.content && !message.result_preview && message.status_text ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)' }}>
              <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} />
              <span>{message.status_text}</span>
            </div>
          ) : isUser ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
          ) : isStreaming ? (
            <div className="markdown-content">
              <Streamdown
                key={`stream-${message.id}`}
                mode="streaming"
                parseIncompleteMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeHighlight, rehypeKatex]}
              >
                {message.content}
              </Streamdown>
              <span style={{
                display: 'inline-block',
                width: 8,
                height: 17,
                backgroundColor: 'var(--primary-color)',
                marginLeft: 2,
                verticalAlign: 'text-bottom',
                animation: 'blink 0.8s infinite',
              }} />
            </div>
          ) : (
            <div className="markdown-content">
              {message.content ? (
                <ReactMarkdown
                  key={`md-${message.render_key || message.id}`}
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeHighlight, rehypeKatex]}
                >
                  {message.content}
                </ReactMarkdown>
              ) : null}
            </div>
          )}
        </div>
        {!isUser && !isStreaming && message.sql_text && (
          <div style={{ marginTop: 10 }}>
            <SqlBlock sqlText={message.sql_text} />
          </div>
        )}
        {!isUser && !isStreaming && message.result_preview && (
          <div style={{ marginTop: 10, overflow: 'auto' }}>
            <DataTable resultPreview={message.result_preview} />
          </div>
        )}
        {!isUser && !isStreaming && message.chart_path && (
          <div style={{
            marginTop: 10,
            borderRadius: 10,
            overflow: 'hidden',
            border: '1px solid var(--border-color)',
            boxShadow: '0 8px 18px rgba(15,23,42,0.08)',
          }}>
            <img
              src={`/api/charts/${message.chart_path.split(/[/\\]/).pop()}`}
              alt="查询图表"
              style={{ width: '100%', display: 'block' }}
            />
          </div>
        )}
      </div>
      {isUser && avatar}
    </div>
  );
}
