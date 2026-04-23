# 前端设计

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | Next.js 14（App Router） | RSC、流式渲染、基于文件的路由 |
| UI 组件库 | shadcn/ui + Tailwind CSS | Radix UI 原语，无运行时依赖 |
| 主题 | next-themes | 深色（默认）/ 浅色切换，SSR 无闪烁 |
| 国际化 | next-intl 3.x | App Router 原生支持，简体中文（默认）/ English |
| Toast 通知 | sonner | 轻量、可访问、自动消失，队列管理 |
| 状态管理 | React Server Components + `useState` | 无全局 store，服务端优先 |

---

## 页面结构

```
app/
├── [locale]/                         # next-intl 语言前缀（zh / en）
│   ├── layout.tsx                    # 根布局：主题 Provider、侧边栏、Toast 容器
│   ├── page.tsx                      # 仪表盘
│   │
│   ├── wiki/
│   │   ├── page.tsx                  # Wiki 列表——按主题列出所有页面
│   │   ├── [slug]/page.tsx           # Wiki 单页查看器
│   │   └── compile/page.tsx          # 触发 wiki 编译
│   │
│   ├── raw/
│   │   ├── page.tsx                  # 原始文件列表
│   │   └── upload/page.tsx           # 上传并追踪摄入状态
│   │
│   ├── qa/
│   │   └── page.tsx                  # Q&A 聊天界面（SSE 流式）
│   │
│   └── admin/
│       ├── page.tsx                  # 管理员仪表盘
│       ├── users/page.tsx
│       └── workspace/page.tsx
│
└── api/                              # Next.js 路由处理器（代理 / BFF，按需使用）
```

---

## 国际化（next-intl）

语言通过 URL 前缀区分：`/zh/wiki`、`/en/wiki`。默认语言为简体中文（`zh`），访问 `/` 自动重定向到 `/zh`。

### 目录结构

```
messages/
├── zh.json       # 简体中文（默认）
└── en.json       # English
```

### 配置

```typescript
// next.config.ts
import createNextIntlPlugin from "next-intl/plugin";
const withNextIntl = createNextIntlPlugin();
export default withNextIntl({ /* nextConfig */ });
```

```typescript
// i18n/routing.ts
import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["zh", "en"],
  defaultLocale: "zh",
});
```

```typescript
// middleware.ts
import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
export default createMiddleware(routing);
export const config = { matcher: ["/((?!api|_next|.*\\..*).*)"] };
```

### 翻译文件示例

```json
// messages/zh.json
{
  "common": {
    "loading": "加载中...",
    "save": "保存",
    "cancel": "取消",
    "confirm": "确认",
    "delete": "删除"
  },
  "error": {
    "100000": null,
    "404001": "工作区不存在",
    "404006": "您不是该工作区的成员",
    "401003": "权限不足",
    "404002": "文件不存在",
    "500000": "服务器内部错误，请稍后重试"
  },
  "wiki": {
    "compile": "编译 Wiki",
    "compiling": "编译中...",
    "ready": "已就绪",
    "failed": "编译失败"
  }
}
```

```json
// messages/en.json
{
  "common": {
    "loading": "Loading...",
    "save": "Save",
    "cancel": "Cancel",
    "confirm": "Confirm",
    "delete": "Delete"
  },
  "error": {
    "100000": null,
    "404001": "Workspace not found",
    "404006": "You are not a member of this workspace",
    "401003": "Permission denied",
    "404002": "File not found",
    "500000": "Internal server error, please try again later"
  },
  "wiki": {
    "compile": "Compile Wiki",
    "compiling": "Compiling...",
    "ready": "Ready",
    "failed": "Compilation failed"
  }
}
```

翻译键中 `"error"` 下以业务码为 key——API 层直接用 code 查表，查不到时降级显示通用错误文案。

---

## 主题（深色 / 浅色）

使用 `next-themes` 管理主题，shadcn/ui 内置对 `dark` class 的支持，无需额外配置。

### Root Layout

```tsx
// app/[locale]/layout.tsx
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";

export default async function RootLayout({ children, params: { locale } }) {
  const messages = await getMessages();
  return (
    <html lang={locale} suppressHydrationWarning>
      <body>
        <NextIntlClientProvider messages={messages}>
          <ThemeProvider
            attribute="class"
            defaultTheme="dark"
            enableSystem={false}
            themes={["dark", "light"]}
          >
            {children}
            <Toaster richColors position="top-right" />
          </ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
```

### 主题切换按钮

```tsx
// components/shared/ThemeToggle.tsx
"use client";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
```

---

## API 客户端与统一错误处理

所有对后端的调用必须经过 `lib/api.ts`——这是前端唯一与后端通信的入口。

后端采用 **RPC 风格**：HTTP 状态码始终为 200，业务成功或失败通过响应体中的 `code` 字段区分。成功码由 `SUCCESS_CODES` 集合维护（当前仅 `100000`，未来可扩展），其余均为业务错误码。

### 常量文件

所有魔法值集中管理，代码中禁止出现内联字面量：

```typescript
// lib/constants.ts

// --- API 业务码 ---
// 维护为 Set，以便未来新增成功码时调用方无需重构。
export const SUCCESS_CODES = new Set([100000]);
export const FALLBACK_ERROR_CODE = 500000;   // 无匹配翻译时使用

// --- 认证 ---
export const ACCESS_TOKEN_KEY = "access_token";   // localStorage 存储 JWT 的键名

// --- SSE ---
export const SSE_EVENT_TOKEN = "token";
export const SSE_EVENT_ERROR = "error";
export const SSE_DONE_SENTINEL = "[DONE]";
```

### 响应类型定义

```typescript
// lib/types.ts
export interface ApiResp<T = unknown> {
  requestId: string;
  code: number;
  message: string | null;
  data: T | null;
}

export interface ApiRespPage<T> {
  total: number;
  page: number;
  size: number;
  totalPages: number;
  list: T[];
}
```

### API 客户端核心

```typescript
// lib/api.ts
import { toast } from "sonner";
import { ApiResp } from "./types";
import { SUCCESS_CODES, FALLBACK_ERROR_CODE, ACCESS_TOKEN_KEY } from "./constants";

// 错误文案查找表 — key 为业务码字符串。
// 在应用启动时通过 initErrorMessages() 填充；每次错误响应时查表。
let _errorMessages: Record<string, string> = {};

export function initErrorMessages(messages: Record<string, string>) {
  _errorMessages = messages;
}

function getErrorText(code: number): string {
  return (
    _errorMessages[String(code)] ??
    _errorMessages[String(FALLBACK_ERROR_CODE)] ??
    "Unknown error"
  );
}

class ApiError extends Error {
  constructor(
    public readonly code: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem(ACCESS_TOKEN_KEY)
      : null;

  const method = options.method ?? "GET";
  const fullUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL}${url}`;

  const res = await fetch(fullUrl, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  // 网络层错误（非 200 HTTP 状态码）。RPC 约定：业务响应始终为 200。
  if (!res.ok) {
    const errText = getErrorText(FALLBACK_ERROR_CODE);
    toast.error(errText);
    console.error("[API] network error", {
      method,
      url,
      body: options.body ?? null,
      httpStatus: res.status,
    });
    throw new ApiError(FALLBACK_ERROR_CODE, errText);
  }

  const body: ApiResp<T> = await res.json();

  if (!SUCCESS_CODES.has(body.code)) {
    // 将业务码翻译为用户可读文案，显示 toast。
    const userText = getErrorText(body.code);
    toast.error(userText);

    // 记录完整请求+响应上下文，供调试使用。
    // 生产环境：message 简短；开发环境：message 含完整错误链。
    console.error("[API] business error", {
      method,
      url,
      body: options.body ?? null,
      code: body.code,
      requestId: body.requestId,
      message: body.message,
    });

    throw new ApiError(body.code, userText);
  }

  return body.data as T;
}

export const api = {
  get: <T>(url: string, options?: RequestInit) =>
    request<T>(url, { method: "GET", ...options }),

  post: <T>(url: string, data?: unknown, options?: RequestInit) =>
    request<T>(url, {
      method: "POST",
      body: JSON.stringify({ data }),
      ...options,
    }),

  put: <T>(url: string, data?: unknown, options?: RequestInit) =>
    request<T>(url, {
      method: "PUT",
      body: JSON.stringify({ data }),
      ...options,
    }),

  delete: <T>(url: string, options?: RequestInit) =>
    request<T>(url, { method: "DELETE", ...options }),
};
```

### 错误处理流程

```
后端响应 { code, message, data }
        │
        ├─ SUCCESS_CODES.has(code) ──→ 返回 data，业务正常继续
        │
        └─ 否则（业务错误）
              ├─ code → 翻译表查 user-facing 文案
              ├─ toast.error(文案)                     ← 用户看到的 Toast（自动消失）
              ├─ console.error({ method, url, body,    ← 开发者/AI 排查用
              │                  code, requestId,
              │                  message })
              │     生产环境：message 简短
              │     非生产：message 含完整错误链 JSON
              └─ throw ApiError(code, 文案)             ← 调用方可按需捕获
```

**关键设计原则**：
- Toast 显示的是翻译后的**用户友好文案**，不暴露技术细节
- `console.error` 输出完整的请求上下文（method、url、请求体、code、requestId、raw message），供开发者/AI Agent 排查，message 是否含详细错误链由后端环境决定
- 所有魔法值（错误码、存储键名、SSE 事件名等）统一在 `lib/constants.ts` 定义，代码中禁止出现内联字面量
- 成功码以**集合**（`SUCCESS_CODES`）维护，未来新增成功码只需修改常量文件，调用方无需改动
- 调用方（组件、Server Action）通常**不需要** `catch`——大多数错误在 `api.ts` 统一处理；只有需要针对特定 code 做特殊 UI 响应时才 catch `ApiError`

### 初始化翻译表

在 Root Layout 中将 error 翻译注入 `api.ts`：

```tsx
// app/[locale]/layout.tsx（补充部分）
"use client";
import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { initErrorMessages } from "@/lib/api";

function ApiErrorInit() {
  const t = useTranslations("error");
  useEffect(() => {
    // 将 error 命名空间下的所有条目作为普通对象传入
    initErrorMessages(
      Object.fromEntries(
        Object.keys(t.raw("")).map((k) => [k, t(k as never)]),
      ),
    );
  }, [t]);
  return null;
}
```

---

## SSE 流式响应（Q&A）

Q&A 端点返回 SSE 流，不经过 `ApiResp` 包装。前端用自定义 hook 消费。

```typescript
// lib/sse.ts
import { toast } from "sonner";
import { SSE_EVENT_TOKEN, SSE_EVENT_ERROR, SSE_DONE_SENTINEL } from "./constants";

const QA_ASK_PATH = "/api/v1/qa/ask";

export function streamAnswer(
  question: string,
  workspaceId: string,
  accessToken: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): () => void {
  const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}${QA_ASK_PATH}`;

  const controller = new AbortController();

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ data: { question, workspace_id: workspaceId } }),
    signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok || !res.body) {
      const msg = "流连接失败";
      toast.error(msg);
      onError(msg);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) { onDone(); break; }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const payload = line.slice(6).trim();
          if (payload === SSE_DONE_SENTINEL) { onDone(); return; }
          try {
            const { type, content } = JSON.parse(payload);
            if (type === SSE_EVENT_TOKEN) onToken(content);
            if (type === SSE_EVENT_ERROR) { toast.error(content); onError(content); }
          } catch { /* 格式异常的数据块，跳过 */ }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== "AbortError") {
      toast.error("连接断开");
      onError(err.message);
    }
  });

  // 返回取消函数
  return () => controller.abort();
}
```

---

## 组件结构

```
components/
├── shared/
│   ├── Sidebar.tsx               # 导航侧边栏
│   ├── TopBar.tsx                # 顶栏（ThemeToggle + 语言切换）
│   ├── ThemeToggle.tsx           # 深色/浅色切换
│   ├── LocaleSwitcher.tsx        # zh / en 切换
│   └── LoadingSpinner.tsx
│
├── wiki/
│   ├── WikiViewer.tsx            # Markdown 渲染器（含 wikilink 支持）
│   ├── WikiEditor.tsx            # 浏览器内 wiki 编辑（可选）
│   └── WikiGraph.tsx             # Neo4j 图可视化
│
├── qa/
│   ├── QAChat.tsx                # 聊天 UI（SSE token 流式渲染）
│   ├── QAMessage.tsx
│   └── SourceCitations.tsx       # 展示检索到的来源 chunk
│
└── ingest/
    ├── IngestDropzone.tsx        # 拖拽文件上传
    └── IngestStatus.tsx          # 任务状态轮询
```

### 语言切换组件

```tsx
// components/shared/LocaleSwitcher.tsx
"use client";
import { useLocale } from "next-intl";
import { useRouter, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";

export function LocaleSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  function toggle() {
    const next = locale === "zh" ? "en" : "zh";
    // 替换当前路径中的语言前缀
    router.push(pathname.replace(`/${locale}`, `/${next}`));
  }

  return (
    <Button variant="ghost" size="sm" onClick={toggle}>
      {locale === "zh" ? "EN" : "中文"}
    </Button>
  );
}
```
