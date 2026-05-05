# AI Agent 智能客服前端美化实施方案

## 技术栈
- 前端：React + Tailwind CSS + shadcn/ui
- 后端：LangChain + LangGraph (FastAPI 提供 SSE)
- 核心 UI 库：assistant-ui

---

## 实施步骤

### 1. 环境准备
- [ ] 确保项目已安装并配置 Tailwind CSS (3.x)
- [ ] 按 shadcn/ui 官方文档初始化组件库 (`npx shadcn-ui@latest init`)
- [ ] 安装 assistant-ui 及 Markdown 增强包：
  ```bash
  npm install @assistant-ui/react @assistant-ui/react-markdown
  npm install rehype-highlight rehype-katex remark-math
  npm install highlight.js katex
  ```

### 2. 构建基础聊天界面
- 创建 Chat.tsx 组件，使用 Thread 和 MarkdownText 快速搭建 UI：
  ```tsx
  // Chat.tsx
  import { AssistantRuntimeProvider } from "@assistant-ui/react";
  import { Thread } from "@assistant-ui/react";
  import { MarkdownText } from "@assistant-ui/react-markdown";

  export function Chat() {
    // 运行时 hook 将在下一步实现
    const runtime = useBackendRuntime();
    return (
      <AssistantRuntimeProvider runtime={runtime}>
        <div className="h-dvh">
          <Thread />
        </div>
      </AssistantRuntimeProvider>
    );
  }
  ```

### 3. 实现连接 LangGraph 的自定义 Hook
- 创建 useBackendRuntime.ts，通过 useLocalRuntime 和 SSE 流式读取连接后端：
  ```tsx
  // hooks/useBackendRuntime.ts
  import { useLocalRuntime, AppendMessage } from "@assistant-ui/react";

  export function useBackendRuntime() {
    return useLocalRuntime({
      async onAppend(message: AppendMessage) {
        const userText = message.content[0]?.text || "";
        const response = await fetch("/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: userText }),
        });

        const adapter = runtime.getCurrentAdapter();
        for await (const chunk of readSSEChunks(response)) {
          if (chunk.type === "text-delta") {
            adapter.appendText(chunk.content);
          } else if (chunk.type === "tool-start") {
            adapter.appendToolCall({ name: chunk.name });
          }
        }
      },
    });
  }

  // SSE 流解析工具函数
  async function* readSSEChunks(response: Response) {
    const reader = response.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ") && line !== "data: [DONE]") {
          yield JSON.parse(line.slice(6));
        }
      }
    }
  }
  ```

### 4. 后端实现 SSE 流式端点 (LangGraph)
- 在 FastAPI 中创建端点，使用 astream_events 推送 token 增量：
  ```python
  from fastapi import FastAPI
  from fastapi.responses import StreamingResponse
  import json

  app = FastAPI()

  @app.post("/chat/stream")
  async def stream_chat(message: dict):
      async def event_stream():
          inputs = {"messages": [{"role": "user", "content": message["text"]}]}
          async for event in graph.astream_events(inputs, version="v2"):
              if event["event"] == "on_chat_model_stream":
                  token = event["data"]["chunk"].content
                  yield f"data: {json.dumps({'type': 'text-delta', 'content': token})}\n\n"
              elif event["event"] == "on_tool_start":
                  yield f"data: {json.dumps({'type': 'tool-start', 'name': event['name']})}\n\n"
          yield "data: [DONE]\n\n"

      return StreamingResponse(event_stream(), media_type="text/event-stream")
  ```
- 将 graph 替换为你已编译的 LangGraph 工作流。

### 5. 强化消息富文本渲染
- 配置代码语法高亮（在 Chat.tsx 或全局 Messages 组件中）：
  ```tsx
  import rehypeHighlight from "rehype-highlight";
  import "highlight.js/styles/github-dark.css";
  // 使用 MarkdownText 时传入插件
  <MarkdownText rehypePlugins={[rehypeHighlight]} />
  ```
- (可选) 开启数学公式支持：
  ```bash
  npm install rehype-katex katex
  ```
  ```tsx
  import rehypeKatex from "rehype-katex";
  import "katex/dist/katex.min.css";
  <MarkdownText rehypePlugins={[rehypeHighlight, rehypeKatex]} />
  ```

### 6. 自定义消息外观（可选）
- 使用 Tailwind 的 prose 类美化整体排版：
  ```tsx
  <div className="prose dark:prose-invert max-w-none">
    <MarkdownText />
  </div>
  ```
- 如需图表 (Mermaid)，可在消息组件中集成 react-mermaid2，通过判断代码块语言来渲染。

### 7. 测试与优化
- 验证流式输出是否逐字显示
- 确认代码块高亮和复制按钮工作正常
- 调整 mobile 端样式（assistant-ui 默认响应式）
- 配置生产环境 CORS 和鉴权

---

## 关键依赖一览
- @assistant-ui/react
- @assistant-ui/react-markdown
- rehype-highlight rehype-katex katex
- highlight.js (CSS 主题)
- tailwindcss shadcn/ui
- 后端：langgraph, fastapi, sse-starlette(可选)

## 快速启动模板（可选）
- 可使用 `npm create assistant-ui@latest` 快速生成已集成 Tailwind + shadcn/ui 的聊天项目骨架，然后替换上面的 Hook 和后端地址即可。

---

文档版本: 1.0 · 更新时间: 2026-04-30
