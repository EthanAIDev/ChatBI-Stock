import { useCallback, useRef, useEffect } from 'react';

export interface SSEState {
  content: string;
  sqlText: string | null;
  resultPreview: string | null;
  chartUrl: string | null;
  status: 'idle' | 'thinking' | 'executing' | 'summarizing' | 'done' | 'error';
  statusText: string;
}

const FRIENDLY_STATUS: Record<string, string> = {
  thinking: '正在理解问题...',
  executing: '正在查询数据库...',
  summarizing: '正在分析数据...',
};

export function useSSE() {
  const controllersRef = useRef<Map<string, AbortController>>(new Map());

  useEffect(() => {
    const controllers = controllersRef.current;
    return () => {
      controllers.forEach((c) => c.abort());
      controllers.clear();
    };
  }, []);

  const startStream = useCallback(
    (sessionId: string, question: string, onUpdate: (s: SSEState) => void) => {
      const controller = new AbortController();
      controllersRef.current.set(sessionId, controller);

      const state: SSEState = {
        content: '',
        sqlText: null,
        resultPreview: null,
        chartUrl: null,
        status: 'idle',
        statusText: FRIENDLY_STATUS.thinking,
      };

      const token = localStorage.getItem('access_token');

      const cleanup = () => {
        controllersRef.current.delete(sessionId);
      };

      fetch('/api/chat/stream/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionId, question }),
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const reader = response.body?.getReader();
          if (!reader) throw new Error('不支持流式读取');

          const decoder = new TextDecoder();
          let buffer = '';
          let currentEvent = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            while (buffer.includes('\n')) {
              const idx = buffer.indexOf('\n');
              const line = buffer.slice(0, idx).trim();
              buffer = buffer.slice(idx + 1);

              if (line.startsWith('event: ')) {
                currentEvent = line.slice(7);
                continue;
              }

              if (line.startsWith('data: ') && currentEvent) {
                const rawData = line.slice(6);
                let data: unknown = rawData;
                try {
                  data = JSON.parse(rawData);
                } catch { /* keep as string */ }

                switch (currentEvent) {
                  case 'thinking':
                    state.status = 'thinking';
                    state.statusText = FRIENDLY_STATUS.thinking;
                    break;
                  case 'executing':
                    state.status = 'executing';
                    state.statusText = FRIENDLY_STATUS.executing;
                    break;
                  case 'chart_generated':
                    state.chartUrl = (data as Record<string, string>).chart_path || null;
                    break;
                  case 'summarizing':
                    state.status = 'summarizing';
                    state.statusText = FRIENDLY_STATUS.summarizing;
                    break;
                  case 'token':
                    state.content += typeof data === 'string' ? data : '';
                    state.status = 'summarizing';
                    break;
                  case 'done':
                    if (typeof data === 'object' && data !== null) {
                      const d = data as Record<string, string>;
                      state.sqlText = d.sql_text || null;
                      state.resultPreview = d.result_preview || null;
                      state.chartUrl = state.chartUrl || d.chart_url || null;
                    }
                    state.status = 'done';
                    break;
                  case 'error':
                    state.status = 'error';
                    state.statusText = (data as Record<string, string>).message || '未知错误';
                    break;
                }

                onUpdate({ ...state });
                currentEvent = '';
              }
            }
          }
          cleanup();
        })
        .catch((err) => {
          cleanup();
          if (err.name !== 'AbortError') {
            onUpdate({ ...state, status: 'error', content: state.content || '抱歉，查询请求失败，请稍后重试。', statusText: err.message });
          }
        });
    },
    [],
  );

  return { startStream };
}
