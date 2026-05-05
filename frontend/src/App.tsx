import { useEffect, useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import ChatLayout from './layouts/ChatLayout';
import LoginPage from './pages/Login';
import ChatPage from './pages/Chat';
import AdminLayout from './pages/Admin';
import { useUiStore } from './stores/uiStore';
import {
  AdminActionLogsPage,
  AdminAiSettingsPage,
  AdminLoginLogsPage,
  AdminOverviewPage,
  AdminQueryAuditsPage,
  AdminSessionsPage,
  AdminUsersPage,
} from './pages/Admin/views';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('access_token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const role = localStorage.getItem('role');
  if (role !== 'admin' && role !== 'superadmin') {
    return <Navigate to="/chat" replace />;
  }
  return <>{children}</>;
}

function HomeRedirect() {
  const role = localStorage.getItem('role');
  return <Navigate to={role === 'admin' || role === 'superadmin' ? '/admin' : '/chat'} replace />;
}

export default function App() {
  const themeMode = useUiStore((state) => state.themeMode);
  const isDark = themeMode === 'dark';

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', themeMode);
  }, [themeMode]);

  const appTheme = useMemo(() => ({
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: isDark ? '#5b8cff' : '#2563eb',
      colorSuccess: isDark ? '#3ddc97' : '#16a34a',
      colorWarning: isDark ? '#f4b54b' : '#d97706',
      colorError: isDark ? '#ff6b7a' : '#dc2626',
      borderRadius: 14,
      controlHeight: 40,
      fontSize: 15,
      fontFamily: '"Inter", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Segoe UI", system-ui, sans-serif',
      colorBgBase: isDark ? '#070b16' : '#f3f7ff',
      colorBgContainer: isDark ? '#121a2a' : '#ffffff',
      colorTextBase: isDark ? '#edf2ff' : '#1e293b',
      colorTextSecondary: isDark ? '#9aaad0' : '#60708c',
      colorBorder: isDark ? '#26344f' : '#d7e0ee',
      boxShadowSecondary: isDark
        ? '0 14px 32px rgba(2, 6, 16, 0.55)'
        : '0 10px 24px rgba(15, 23, 42, 0.08)',
    },
    components: {
      Card: {
        headerFontSize: 18,
      },
      Table: {
        headerBg: isDark ? '#161f32' : '#f4f7ff',
        rowHoverBg: isDark ? 'rgba(91,140,255,0.14)' : 'rgba(37,99,235,0.08)',
      },
      Menu: {
        darkItemBg: '#0d1629',
        darkSubMenuItemBg: '#0d1629',
        darkItemSelectedBg: 'linear-gradient(90deg, rgba(91,140,255,0.4), rgba(91,140,255,0.18))',
      },
      Input: {
        activeBorderColor: isDark ? '#5b8cff' : '#2563eb',
      },
      Select: {
        activeBorderColor: isDark ? '#5b8cff' : '#2563eb',
      },
      Button: {
        primaryShadow: isDark ? '0 10px 24px rgba(59,130,246,0.35)' : '0 8px 20px rgba(37,99,235,0.24)',
      },
    },
  }), [isDark]);

  return (
    <ConfigProvider locale={zhCN} theme={appTheme}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/admin"
            element={
              <RequireAuth>
                <RequireAdmin>
                  <AdminLayout />
                </RequireAdmin>
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/admin/overview" replace />} />
            <Route path="overview" element={<AdminOverviewPage />} />
            <Route path="users" element={<AdminUsersPage />} />
            <Route path="login-logs" element={<AdminLoginLogsPage />} />
            <Route path="action-logs" element={<AdminActionLogsPage />} />
            <Route path="sessions" element={<AdminSessionsPage />} />
            <Route path="query-audits" element={<AdminQueryAuditsPage />} />
            <Route path="ai-settings" element={<AdminAiSettingsPage />} />
          </Route>
          <Route
            element={
              <RequireAuth>
                <ChatLayout />
              </RequireAuth>
            }
          >
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/" element={<HomeRedirect />} />
          </Route>
          <Route path="*" element={<HomeRedirect />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
