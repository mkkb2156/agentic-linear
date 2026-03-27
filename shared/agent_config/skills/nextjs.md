# Next.js 14 App Router 最佳實踐

## ⚠️ 重要限制（Next.js 14）
- **配置檔必須用 `next.config.mjs`**（不是 `.ts`，Next.js 14 不支援 TypeScript 配置）
- `tailwind.config.js` 或 `tailwind.config.ts` 都可以
- `postcss.config.js`（不是 `.ts`）

## 專案結構
```
app/                    # App Router（每個資料夾 = 一個路由）
  layout.tsx            # Root layout（共用 header/footer）
  page.tsx              # 首頁
  globals.css           # 全域樣式（含 Tailwind directives）
  (auth)/               # Route group（不影響 URL）
    login/page.tsx
    register/page.tsx
  (dashboard)/
    layout.tsx          # Dashboard layout（sidebar）
    page.tsx
    settings/page.tsx
components/             # 可重用元件
  ui/                   # shadcn/ui 元件
lib/                    # 工具函式
  api.ts                # API client（fetch wrapper + token）
  utils.ts
types/                  # TypeScript 型別定義
public/                 # 靜態資源
```

## Server vs Client Components
- **預設是 Server Component**（可直接 await fetch）
- 加 `"use client"` 才變 Client Component
- 需要 useState/useEffect/onClick 的才用 Client
- 優先用 Server Component（SEO + 效能）

## Tailwind CSS + shadcn/ui
```bash
npx create-next-app@latest --typescript --tailwind --app
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input dialog table
```

## API Client 模式
```typescript
// lib/api.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

## Auth Middleware
```typescript
// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("token")?.value;
  if (!token && request.nextUrl.pathname.startsWith("/dashboard")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/dashboard/:path*"] };
```

## 常用頁面模式
- **列表頁**：用 @tanstack/react-query 取資料 + 表格/卡片顯示
- **詳情頁**：動態路由 `[id]/page.tsx` + 資料載入
- **表單頁**：react-hook-form + zod validation
- **Loading/Error**：`loading.tsx` + `error.tsx` per route

## package.json 依賴（建議）
```json
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.0.0",
    "react-hook-form": "^7.0.0",
    "zod": "^3.0.0",
    "@hookform/resolvers": "^3.0.0",
    "lucide-react": "^0.300.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/react": "^18.0.0",
    "tailwindcss": "^3.0.0",
    "autoprefixer": "^10.0.0",
    "postcss": "^8.0.0"
  }
}
```
