import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  AuditOutlined,
  DatabaseOutlined,
  LoginOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../../stores/authStore';

import {
  createAdminUser,
  deleteAdminSession,
  getAdminActionLogs,
  getAdminLoginLogs,
  getAdminOverview,
  getAdminQueryAudits,
  getAdminSessionDetail,
  getAdminSessions,
  getAdminUsers,
  getModelSettings,
  getPromptTemplates,
  pinAdminSession,
  resetAdminUserPassword,
  updateAdminUserRole,
  updateAdminUserStatus,
  updateModelSettings,
  updatePromptTemplates,
} from '../../services/admin';
import type {
  AdminActionLog,
  AdminLoginLog,
  AdminOverview,
  AdminQueryAudit,
  AdminSession,
  AdminSessionDetail,
  AdminUser,
  CreateUserResponse,
  ModelSettings,
  PageResult,
  PromptTemplate,
} from '../../types';

const { Title, Text } = Typography;

function formatDateTime(value: string | null | undefined) {
  if (!value) return '-';
  const raw = value.trim();

  // Keep ISO-like strings readable without timezone drift when possible.
  const isoLike = raw
    .replace('T', ' ')
    .replace(/\.\d+$/, '')
    .replace(/Z$/, '');
  if (/^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$/.test(isoLike)) {
    return isoLike;
  }

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }

  const pad = (num: number) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function useTablePagination<T>() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [data, setData] = useState<PageResult<T> | null>(null);
  return { page, setPage, pageSize, setPageSize, data, setData };
}

export function AdminOverviewPage() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await getAdminOverview();
        if (res.code === 0) {
          setData(res.data);
        }
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const loginColumns: ColumnsType<AdminLoginLog> = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    {
      title: '结果',
      dataIndex: 'success',
      key: 'success',
      render: (value: number) => <Tag color={value ? 'green' : 'red'}>{value ? '成功' : '失败'}</Tag>,
    },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', render: formatDateTime },
  ];

  const failureColumns: ColumnsType<AdminQueryAudit> = [
    { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
    { title: '问题', dataIndex: 'question', key: 'question', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string) => <Tag color={value === 'success' ? 'green' : 'red'}>{value}</Tag>,
    },
    { title: '错误', dataIndex: 'error_message', key: 'error_message', ellipsis: true, render: (value: string | null) => value || '-' },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: formatDateTime },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>仪表盘</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="panel-surface"><Statistic title="今日登录数" value={data?.stats.today_logins || 0} prefix={<LoginOutlined />} loading={loading} /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="panel-surface"><Statistic title="总用户数" value={data?.stats.total_users || 0} prefix={<TeamOutlined />} loading={loading} /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="panel-surface"><Statistic title="活跃用户数" value={data?.stats.active_users || 0} prefix={<AuditOutlined />} loading={loading} /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="panel-surface"><Statistic title="总会话数" value={data?.stats.total_sessions || 0} prefix={<DatabaseOutlined />} loading={loading} /></Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card className="panel-surface" title="最近登录">
            <Table className="table-panel" rowKey="id" loading={loading} columns={loginColumns} dataSource={data?.recent_login_logs || []} pagination={false} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="panel-surface" title={`最近异常（失败登录 ${data?.stats.failed_logins || 0}）`}>
            <Table className="table-panel" rowKey="id" loading={loading} columns={failureColumns} dataSource={data?.recent_failures || []} pagination={false} />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}

export function AdminUsersPage() {
  const { page, setPage, pageSize, setPageSize, data, setData } = useTablePagination<AdminUser>();
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [role, setRole] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>();
  const [creating, setCreating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm<{ username: string; password: string }>();
  const [initialValues, setInitialValues] = useState<{ username: string; password: string }>({ username: '', password: '' });
  const currentUserRole = useAuthStore((s) => s.role);

  const roleOptions = useMemo(() => {
    const options = [{ label: '普通用户', value: 'user' }];
    if (currentUserRole === 'superadmin') {
      options.push({ label: '管理员', value: 'admin' });
    }
    return options;
  }, [currentUserRole]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAdminUsers({ page, page_size: pageSize, keyword: keyword || undefined, role, status });
      if (res.code === 0) {
        setData(res.data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [page, pageSize, role, status]);

  const generateDefaultUsername = (): string => {
    const existingUsers = data?.items || [];
    let maxSeq = 0;
    const re = /^user(\d+)$/;
    for (const u of existingUsers) {
      const m = re.exec(u.username);
      if (m) {
        const seq = parseInt(m[1], 10);
        if (seq > maxSeq) maxSeq = seq;
      }
    }
    return `user${maxSeq + 1}`;
  };

  const openCreateModal = () => {
    setInitialValues({
      username: generateDefaultUsername(),
      password: '123456',
    });
    setCreateOpen(true);
  };

  const handleCreateUser = async () => {
    const values = await createForm.validateFields().catch(() => null);
    if (!values) return;

    setCreating(true);
    try {
      const res = await createAdminUser({
        username: values.username,
        password: values.password,
      });
      if (res.code === 0) {
        const created = res.data as CreateUserResponse;
        message.success(`用户 ${created.username} 添加成功`);
        setCreateOpen(false);
        setPage(1);
        void load();
      }
    } finally {
      setCreating(false);
    }
  };

  const columns: ColumnsType<AdminUser> = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '昵称', dataIndex: 'nickname', key: 'nickname', render: (value: string | null) => value || '-' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (_value: string, record) => {
        const isAdmin = record.username === 'admin';
        return (
          <Select
            size="small"
            value={record.role}
            disabled={isAdmin}
            style={{ width: 120 }}
            options={roleOptions}
            onChange={async (nextRole) => {
              const res = await updateAdminUserRole(record.id, nextRole);
              if (res.code === 0) {
                message.success('角色已更新');
                void load();
              }
            }}
          />
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (_value: string, record) => {
        const isAdmin = record.username === 'admin';
        return (
          <Button
            size="small"
            disabled={isAdmin}
            type={record.status === 'active' ? 'default' : 'primary'}
            danger={record.status === 'active'}
            onClick={async () => {
              const nextStatus = record.status === 'active' ? 'disabled' : 'active';
              const res = await updateAdminUserStatus(record.id, nextStatus);
              if (res.code === 0) {
                message.success('状态已更新');
                void load();
              }
            }}
          >
            {record.status === 'active' ? '停用' : '启用'}
          </Button>
        );
      },
    },
    { title: '最近登录', dataIndex: 'last_login_time', key: 'last_login_time', render: formatDateTime },
    {
      title: '操作',
      key: 'actions',
      render: (_value, record) => {
        const isAdmin = record.username === 'admin';
        return (
          <Button
            size="small"
            disabled={isAdmin}
            onClick={async () => {
              const res = await resetAdminUserPassword(record.id);
              if (res.code === 0) {
                Modal.info({
                  title: `已重置 ${record.username} 的密码`,
                  content: <Text copyable>{res.data.temporary_password}</Text>,
                });
                void load();
              }
            }}
          >
            重置密码
          </Button>
        );
      },
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>用户管理</Title>
      <Card className="panel-surface">
        <Space wrap style={{ marginBottom: 16 }}>
          <Input placeholder="用户名/昵称" value={keyword} onChange={(e) => setKeyword(e.target.value)} style={{ width: 220 }} />
          <Select allowClear placeholder="角色" style={{ width: 140 }} value={role} onChange={setRole} options={roleOptions} />
          <Select allowClear placeholder="状态" style={{ width: 140 }} value={status} onChange={setStatus} options={[
            { label: '启用', value: 'active' },
            { label: '停用', value: 'disabled' },
          ]} />
          <Button type="primary" onClick={() => { setPage(1); void load(); }}>查询</Button>
          <Button type="primary" onClick={openCreateModal}>添加用户</Button>
        </Space>
        <Table
          className="table-panel"
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={data?.items || []}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>
      <Modal
        title="添加用户"
        open={createOpen}
        onOk={handleCreateUser}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={creating}
        okText="确认添加"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" preserve={false} initialValues={initialValues}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { pattern: /^[a-zA-Z0-9]+$/, message: '用户名仅支持数字加英文' },
              { max: 8, message: '用户名最多8位' },
            ]}
          >
            <Input placeholder="默认 user+自增序号" maxLength={8} />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { pattern: /^[a-zA-Z0-9!@#$%^&*()_+\-=[\]{};':"\\|,.<>\/?]+$/, message: '密码仅支持英文加数字加符号' },
              { max: 12, message: '密码最多12位' },
            ]}
          >
            <Input.Password placeholder="默认 123456" maxLength={12} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

export function AdminLoginLogsPage() {
  const { page, setPage, pageSize, setPageSize, data, setData } = useTablePagination<AdminLoginLog>();
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState('');
  const [success, setSuccess] = useState<number | undefined>();

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAdminLoginLogs({ page, page_size: pageSize, username: username || undefined, success });
      if (res.code === 0) setData(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [page, pageSize, success]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>登录日志</Title>
      <Card className="panel-surface">
        <Space wrap style={{ marginBottom: 16 }}>
          <Input placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} style={{ width: 220 }} />
          <Select
            allowClear
            placeholder="结果"
            style={{ width: 140 }}
            value={success}
            onChange={setSuccess}
            options={[
              { label: '成功', value: 1 },
              { label: '失败', value: 0 },
            ]}
          />
          <Button type="primary" onClick={() => { setPage(1); void load(); }}>查询</Button>
        </Space>
        <Table
          className="table-panel"
          rowKey="id"
          loading={loading}
          columns={[
            { title: '用户名', dataIndex: 'username', key: 'username' },
            {
              title: '结果',
              dataIndex: 'success',
              key: 'success',
              render: (value: number) => <Tag color={value ? 'green' : 'red'}>{value ? '成功' : '失败'}</Tag>,
            },
            { title: 'IP', dataIndex: 'ip_address', key: 'ip_address', render: (value: string | null) => value || '-' },
            { title: 'User-Agent', dataIndex: 'user_agent', key: 'user_agent', ellipsis: true },
            { title: '时间', dataIndex: 'created_at', key: 'created_at', render: formatDateTime },
          ]}
          dataSource={data?.items || []}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>
    </Space>
  );
}

export function AdminActionLogsPage() {
  const { page, setPage, pageSize, setPageSize, data, setData } = useTablePagination<AdminActionLog>();
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAdminActionLogs({ page, page_size: pageSize, keyword: keyword || undefined });
      if (res.code === 0) setData(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [page, pageSize]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>操作日志</Title>
      <Card className="panel-surface">
        <Space wrap style={{ marginBottom: 16 }}>
          <Input placeholder="操作人/动作/目标" value={keyword} onChange={(e) => setKeyword(e.target.value)} style={{ width: 260 }} />
          <Button type="primary" onClick={() => { setPage(1); void load(); }}>查询</Button>
        </Space>
        <Table
          className="table-panel"
          rowKey="id"
          loading={loading}
          columns={[
            { title: '操作人', dataIndex: 'actor_username', key: 'actor_username' },
            { title: '角色', dataIndex: 'actor_role', key: 'actor_role' },
            { title: '动作', dataIndex: 'action', key: 'action' },
            { title: '目标类型', dataIndex: 'target_type', key: 'target_type' },
            { title: '目标', dataIndex: 'target_label', key: 'target_label', render: (value: string | null, record) => value || record.target_id },
            { title: '详情', dataIndex: 'detail', key: 'detail', render: (value: Record<string, unknown> | null) => value ? JSON.stringify(value) : '-' },
            { title: '时间', dataIndex: 'created_at', key: 'created_at', render: formatDateTime },
          ]}
          dataSource={data?.items || []}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>
    </Space>
  );
}

export function AdminSessionsPage() {
  const { page, setPage, pageSize, setPageSize, data, setData } = useTablePagination<AdminSession>();
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [userId, setUserId] = useState('');
  const [pinned, setPinned] = useState<boolean | undefined>();
  const [detail, setDetail] = useState<AdminSessionDetail | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAdminSessions({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        user_id: userId || undefined,
        is_pinned: pinned,
      });
      if (res.code === 0) setData(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [page, pageSize, pinned]);

  const detailColumns: ColumnsType<AdminSessionDetail['messages'][number]> = [
    { title: '角色', dataIndex: 'role', key: 'role', width: 100 },
    { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: 'SQL', dataIndex: 'sql_text', key: 'sql_text', ellipsis: true, render: (value: string | null) => value || '-' },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: formatDateTime },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>会话管理</Title>
      <Card className="panel-surface">
        <Space wrap style={{ marginBottom: 16 }}>
          <Input placeholder="标题/关键词" value={keyword} onChange={(e) => setKeyword(e.target.value)} style={{ width: 220 }} />
          <Input placeholder="用户" value={userId} onChange={(e) => setUserId(e.target.value)} style={{ width: 180 }} />
          <Select
            allowClear
            placeholder="是否置顶"
            style={{ width: 140 }}
            value={pinned}
            onChange={setPinned}
            options={[
              { label: '已置顶', value: true },
              { label: '未置顶', value: false },
            ]}
          />
          <Button type="primary" onClick={() => { setPage(1); void load(); }}>查询</Button>
        </Space>
        <Table
          className="table-panel"
          rowKey="session_id"
          loading={loading}
          columns={[
            { title: '会话ID', dataIndex: 'session_id', key: 'session_id', width: 220, ellipsis: true },
            { title: '用户', dataIndex: 'user_id', key: 'user_id', width: 140 },
            { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
            {
              title: '置顶',
              dataIndex: 'is_pinned',
              key: 'is_pinned',
              width: 100,
              render: (value: boolean) => value ? <Tag color="blue">已置顶</Tag> : <Tag>否</Tag>,
            },
            { title: '消息数', dataIndex: 'message_count', key: 'message_count', width: 90 },
            { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 180, render: formatDateTime },
            {
              title: '操作',
              key: 'actions',
              width: 240,
              render: (_value, record) => (
                <Space>
                  <Button
                    size="small"
                    onClick={async () => {
                      const res = await getAdminSessionDetail(record.session_id);
                      if (res.code === 0) {
                        setDetail(res.data);
                        setDetailOpen(true);
                      }
                    }}
                  >
                    查看
                  </Button>
                  <Button
                    size="small"
                    onClick={async () => {
                      const res = await pinAdminSession(record.session_id, !record.is_pinned);
                      if (res.code === 0) {
                        message.success('置顶状态已更新');
                        void load();
                      }
                    }}
                  >
                    {record.is_pinned ? '取消置顶' : '置顶'}
                  </Button>
                  <Button
                    size="small"
                    danger
                    onClick={() => {
                      Modal.confirm({
                        title: '确认删除该会话？',
                        content: '会话消息与相关审计记录会一并清理。',
                        okButtonProps: { danger: true },
                        onOk: async () => {
                          const res = await deleteAdminSession(record.session_id);
                          if (res.code === 0) {
                            message.success('会话已删除');
                            void load();
                          }
                        },
                      });
                    }}
                  >
                    删除
                  </Button>
                </Space>
              ),
            },
          ]}
          dataSource={data?.items || []}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>
      <Modal
        width={1000}
        open={detailOpen}
        title="会话详情"
        onCancel={() => setDetailOpen(false)}
        footer={null}
      >
        {detail && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="会话ID">{detail.session.session_id}</Descriptions.Item>
              <Descriptions.Item label="用户">{detail.session.user_id}</Descriptions.Item>
              <Descriptions.Item label="标题">{detail.session.title}</Descriptions.Item>
              <Descriptions.Item label="消息数">{detail.session.message_count}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDateTime(detail.session.created_at)}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{formatDateTime(detail.session.updated_at)}</Descriptions.Item>
            </Descriptions>
            <Table className="table-panel" rowKey="id" columns={detailColumns} dataSource={detail.messages} pagination={{ pageSize: 6 }} />
          </Space>
        )}
      </Modal>
    </Space>
  );
}

export function AdminQueryAuditsPage() {
  const { page, setPage, pageSize, setPageSize, data, setData } = useTablePagination<AdminQueryAudit>();
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [username, setUsername] = useState('');
  const [status, setStatus] = useState<string | undefined>();

  const load = async () => {
    setLoading(true);
    try {
      const res = await getAdminQueryAudits({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        username: username || undefined,
        status,
      });
      if (res.code === 0) setData(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [page, pageSize, status]);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>查询审计</Title>
      <Card className="panel-surface">
        <Space wrap style={{ marginBottom: 16 }}>
          <Input placeholder="用户" value={username} onChange={(e) => setUsername(e.target.value)} style={{ width: 180 }} />
          <Input placeholder="问题/SQL/错误" value={keyword} onChange={(e) => setKeyword(e.target.value)} style={{ width: 260 }} />
          <Select
            allowClear
            placeholder="状态"
            style={{ width: 140 }}
            value={status}
            onChange={setStatus}
            options={[
              { label: '成功', value: 'success' },
              { label: '失败', value: 'failed' },
            ]}
          />
          <Button type="primary" onClick={() => { setPage(1); void load(); }}>查询</Button>
        </Space>
        <Table
          className="table-panel"
          rowKey="id"
          loading={loading}
          columns={[
            { title: '用户', dataIndex: 'username', key: 'username', width: 110 },
            { title: '会话ID', dataIndex: 'session_id', key: 'session_id', width: 220, ellipsis: true },
            { title: '问题', dataIndex: 'question', key: 'question', ellipsis: true },
            { title: 'SQL', dataIndex: 'sql_text', key: 'sql_text', ellipsis: true, render: (value: string | null) => value || '-' },
            {
              title: '耗时',
              dataIndex: 'duration_ms',
              key: 'duration_ms',
              width: 100,
              render: (value: number) => `${value} ms`,
            },
            {
              title: '缓存',
              dataIndex: 'from_cache',
              key: 'from_cache',
              width: 90,
              render: (value: boolean) => value ? <Tag color="blue">命中</Tag> : <Tag>否</Tag>,
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              width: 100,
              render: (value: string) => <Tag color={value === 'success' ? 'green' : 'red'}>{value}</Tag>,
            },
            { title: '错误', dataIndex: 'error_message', key: 'error_message', ellipsis: true, render: (value: string | null) => value || '-' },
            { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: formatDateTime },
          ]}
          dataSource={data?.items || []}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>
    </Space>
  );
}

export function AdminAiSettingsPage() {
  const [loading, setLoading] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingTemplates, setSavingTemplates] = useState(false);
  const [settingsForm] = Form.useForm<ModelSettings>();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);

  const templateMap = useMemo(() => {
    const result: Record<string, PromptTemplate> = {};
    templates.forEach((item) => {
      result[item.template_key] = item;
    });
    return result;
  }, [templates]);

  const load = async () => {
    setLoading(true);
    try {
      const [settingsRes, templatesRes] = await Promise.all([getModelSettings(), getPromptTemplates()]);
      if (settingsRes.code === 0) {
        settingsForm.setFieldsValue(settingsRes.data);
      }
      if (templatesRes.code === 0) {
        setTemplates(templatesRes.data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={4} style={{ margin: 0 }}>AI 配置</Title>
      <Tabs
        items={[
          {
            key: 'settings',
            label: '模型配置',
            children: (
              <Card className="panel-surface" loading={loading}>
                <Form
                  layout="vertical"
                  form={settingsForm}
                  onFinish={async (values: ModelSettings) => {
                    setSavingSettings(true);
                    try {
                      const res = await updateModelSettings(values);
                      if (res.code === 0) {
                        message.success('模型配置已保存');
                        settingsForm.setFieldsValue(res.data);
                      }
                    } finally {
                      setSavingSettings(false);
                    }
                  }}
                >
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="model_name" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: '请输入 Base URL' }]}>
                        <Input />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item name="timeout_seconds" label="超时（秒）" rules={[{ required: true }]}>
                        <InputNumber min={1} max={300} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="retry_count" label="重试次数" rules={[{ required: true }]}>
                        <InputNumber min={0} max={10} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="max_context_rounds" label="上下文轮数" rules={[{ required: true }]}>
                        <InputNumber min={1} max={20} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Button type="primary" htmlType="submit" loading={savingSettings}>保存模型配置</Button>
                </Form>
              </Card>
            ),
          },
          {
            key: 'prompts',
            label: 'Prompt 模板',
            children: (
              <Card className="panel-surface" loading={loading}>
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  {templates.map((template) => (
                    <div key={template.template_key}>
                      <Text strong>{template.template_name}</Text>
                      <div style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6, margin: '4px 0 8px' }}>{template.description || '-'}</div>
                      <Input.TextArea
                        value={templateMap[template.template_key]?.content}
                        autoSize={{ minRows: 6, maxRows: 16 }}
                        onChange={(event) => {
                          const value = event.target.value;
                          setTemplates((current) => current.map((item) => (
                            item.template_key === template.template_key ? { ...item, content: value } : item
                          )));
                        }}
                      />
                    </div>
                  ))}
                  <Button
                    type="primary"
                    loading={savingTemplates}
                    onClick={async () => {
                      setSavingTemplates(true);
                      try {
                        const res = await updatePromptTemplates(templates);
                        if (res.code === 0) {
                          message.success('Prompt 模板已保存');
                          setTemplates(res.data);
                        }
                      } finally {
                        setSavingTemplates(false);
                      }
                    }}
                  >
                    保存 Prompt 模板
                  </Button>
                </Space>
              </Card>
            ),
          },
        ]}
      />
    </Space>
  );
}
