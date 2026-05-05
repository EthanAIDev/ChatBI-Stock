import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';

const { Content } = Layout;

export default function ChatLayout() {
  return (
    <Layout className="app-page" style={{ minHeight: '100vh', background: 'var(--bg-app)' }}>
      <Content style={{ height: '100vh', background: 'var(--bg-app)' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
