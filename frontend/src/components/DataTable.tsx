import { Table } from 'antd';
import type { ReactNode } from 'react';
import type { ResultPreview } from '../types';

interface DataTableProps {
  resultPreview: string;
}

export default function DataTable({ resultPreview }: DataTableProps) {
  let data: ResultPreview;
  try {
    data = JSON.parse(resultPreview);
  } catch {
    return <div style={{ color: 'var(--text-secondary)', fontSize: 14 }}>无法解析数据</div>;
  }

  if (!data?.columns || !data?.data) {
    return <div style={{ color: 'var(--text-secondary)', fontSize: 14 }}>数据为空</div>;
  }

  const columns = data.columns.map((col: string) => ({
    title: col,
    dataIndex: col,
    key: col,
    ellipsis: true,
    render: (value: unknown): ReactNode => {
      if (typeof value === 'number' && !Number.isInteger(value)) {
        return value.toFixed(2);
      }
      if (value === null || value === undefined) {
        return '-';
      }
      return String(value);
    },
  }));

  const dataSource = data.data.map((row: unknown[], i: number) => {
    const record: Record<string, unknown> = { _key: i };
    data.columns.forEach((col: string, j: number) => {
      record[col] = row[j];
    });
    return record;
  });

  return (
    <div className="table-panel" style={{ marginTop: 8 }}>
      <Table
        columns={columns}
        dataSource={dataSource}
        rowKey="_key"
        size="small"
        pagination={dataSource.length > 10 ? { pageSize: 10 } : false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: '暂无数据' }}
      />
    </div>
  );
}
