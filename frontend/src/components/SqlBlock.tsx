import { Collapse, Button, message } from 'antd';
import { CopyOutlined, CodeOutlined } from '@ant-design/icons';

interface SqlBlockProps {
  sqlText: string;
}

export default function SqlBlock({ sqlText }: SqlBlockProps) {
  const [api, contextHolder] = message.useMessage();

  return (
    <>
      {contextHolder}
      <Collapse
        size="small"
        ghost
        items={[
          {
            key: 'sql',
            label: (
              <span>
                <CodeOutlined style={{ marginRight: 8 }} />
                查看 SQL
              </span>
            ),
            extra: (
              <Button
                size="small"
                type="text"
                aria-label="复制SQL"
                icon={<CopyOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  navigator.clipboard.writeText(sqlText).then(() => {
                    api.success('SQL 已复制');
                  }).catch(() => {
                    api.error('复制失败');
                  });
                }}
              />
            ),
            children: (
              <pre style={{ background: 'var(--bg-soft)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', padding: 12, borderRadius: 8, overflow: 'auto', fontSize: 14 }}>
                <code>{sqlText}</code>
              </pre>
            ),
          },
        ]}
      />
    </>
  );
}
