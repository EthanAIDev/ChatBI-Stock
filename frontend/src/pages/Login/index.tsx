import { useState } from 'react';
import { Form, Input, Button, Card, Typography, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { login as loginApi } from '../../services/auth';
import ThemeToggle from '../../components/ThemeToggle';

const { Title, Text } = Typography;

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const loginStore = useAuthStore((s) => s.login);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await loginApi(values);
      if (res.code === 0) {
        const d = res.data;
        loginStore(d.username, d.role, d.access_token);
        message.success('登录成功');
        navigate(d.role === 'admin' || d.role === 'superadmin' ? '/admin' : '/chat', { replace: true });
      } else {
        message.error(res.message || '登录失败');
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="app-page"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'radial-gradient(circle at 20% 20%, rgba(37,99,235,0.24), transparent 35%), radial-gradient(circle at 80% 80%, rgba(22,163,74,0.18), transparent 35%), var(--bg-app)',
      }}
    >
      <div style={{ position: 'fixed', top: 16, right: 20 }}>
        <ThemeToggle />
      </div>
      <Card className="panel-surface" style={{ width: 400, borderRadius: 14, boxShadow: 'var(--shadow-base)', background: 'var(--bg-elevated)' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={3} style={{ marginBottom: 4, color: 'var(--text-primary)' }}>ChatBI 股票查询助手</Title>
          <Text type="secondary">基于自然语言的智能股票分析平台</Text>
        </div>
        <Form name="login" onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
        <Text type="secondary" style={{ fontSize: 13, display: 'block', textAlign: 'center' }}>
          默认账号: admin/admin123 或 user/user123
        </Text>
      </Card>
    </div>
  );
}
