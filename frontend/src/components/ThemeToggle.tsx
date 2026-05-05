import { Button, Tooltip } from 'antd';
import { SunOutlined, MoonOutlined } from '@ant-design/icons';
import { useUiStore } from '../stores/uiStore';

interface ThemeToggleProps {
  compact?: boolean;
}

export default function ThemeToggle({ compact = false }: ThemeToggleProps) {
  const themeMode = useUiStore((state) => state.themeMode);
  const toggleThemeMode = useUiStore((state) => state.toggleThemeMode);
  const isDark = themeMode === 'dark';

  return (
    <Tooltip title={isDark ? '切换浅色模式' : '切换深色模式'}>
      <Button
        type={compact ? 'text' : 'default'}
        size={compact ? 'small' : 'middle'}
        className="theme-toggle-btn"
        icon={isDark ? <SunOutlined /> : <MoonOutlined />}
        aria-label={isDark ? '切换浅色模式' : '切换深色模式'}
        onClick={toggleThemeMode}
      />
    </Tooltip>
  );
}
