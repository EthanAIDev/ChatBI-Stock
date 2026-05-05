import { useMemo } from 'react';
import { Button, Layout, Menu, Typography } from 'antd';
import {
  DashboardOutlined,
  TeamOutlined,
  LoginOutlined,
  AuditOutlined,
  MessageOutlined,
  DatabaseOutlined,
  SettingOutlined,
  LogoutOutlined,
  CommentOutlined,
} from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import ThemeToggle from '../../components/ThemeToggle';

const { Header, Sider, Content } = Layout;
const { Text, Title } = Typography;

const menuItems = [
  { key: '/admin/overview', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
  { key: '/admin/login-logs', icon: <LoginOutlined />, label: '登录日志' },
  { key: '/admin/action-logs', icon: <AuditOutlined />, label: '操作日志' },
  { key: '/admin/sessions', icon: <MessageOutlined />, label: '会话管理' },
  { key: '/admin/query-audits', icon: <DatabaseOutlined />, label: '查询审计' },
  { key: '/admin/ai-settings', icon: <SettingOutlined />, label: 'AI 配置' },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const username = useAuthStore((s) => s.username);
  const logout = useAuthStore((s) => s.logout);

  const selectedKey = useMemo(() => {
    const match = [...menuItems].reverse().find((item) => location.pathname.startsWith(item.key));
    return match?.key ?? '/admin/overview';
  }, [location.pathname]);

  return (
    <Layout className="app-page" style={{ height: '100vh', overflow: 'hidden', background: 'var(--bg-app)' }}>
      <Sider
        width={236}
        style={{
          height: '100vh',
          background: 'linear-gradient(180deg, #0a1427 0%, #132544 100%)',
          borderRight: '1px solid var(--border-color)',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ padding: '20px 8px 12px' }}>
            <Title level={4} style={{ color: '#fff', margin: 0, paddingInlineStart: 24 }}>ChatBI 后台</Title>
            <Text style={{ color: 'rgba(255,255,255,0.65)', display: 'block', paddingInlineStart: 24 }}>轻量运营管理台</Text>
          </div>
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingBottom: 8 }}>
            <Menu
              theme="dark"
              mode="inline"
              selectedKeys={[selectedKey]}
              items={menuItems}
              onClick={({ key }) => navigate(key)}
              style={{ borderInlineEnd: 'none' }}
            />
          </div>
          <div style={{ marginTop: 'auto', padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <Button
              type="text"
              icon={<CommentOutlined />}
              block
              style={{ color: 'rgba(255,255,255,0.65)', textAlign: 'left' }}
              onClick={() => navigate('/chat')}
            >
              去聊天
            </Button>
          </div>
        </div>
      </Sider>
      <Layout style={{ minWidth: 0, minHeight: 0 }}>
        <Header
          style={{
            background: 'color-mix(in srgb, var(--bg-elevated) 92%, transparent)',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-color)',
            backdropFilter: 'var(--panel-blur)',
          }}
        >
          <Text style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)' }}>后台管理</Text>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <Text type="secondary" style={{ fontSize: 15, paddingInline: 2 }}>{username}</Text>
            <div style={{ display: 'inline-flex', alignItems: 'center' }}>
              <ThemeToggle compact />
            </div>
            <Button
              type="text"
              icon={<LogoutOutlined />}
              style={{ paddingInline: 10 }}
              onClick={() => {
                logout();
                navigate('/login', { replace: true });
              }}
            >
              退出登录
            </Button>
          </div>
        </Header>
        <Content style={{ padding: 20, background: 'var(--bg-app)', overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
