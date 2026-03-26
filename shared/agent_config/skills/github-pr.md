# GitHub PR Workflow Skill

此 skill 教你如何使用 GitHub 工具建立 repository 和 Pull Request。

## 建立 Repository

使用 `github_create_repo` tool。先用 `github_list_repos` 確認 repo 是否已存在。

```json
// 步驟 1：搜尋 repo
{"search": "qrbro"}

// 步驟 2：如果不存在，建立
{"name": "qrbro-frontend", "description": "QRBro Frontend - Next.js 14", "private": false}
```

## 建立 Pull Request（Push Code）

使用 `github_create_pr` tool 一次 push 多個檔案並開 PR。

### files 格式

每個檔案是 `{"path": "檔案路徑", "content": "完整檔案內容"}` 的 object。

```json
{
  "repo": "qrbro-frontend",
  "branch_name": "feat/initial-scaffold",
  "title": "feat: initial project scaffold",
  "body": "初始專案骨架，包含 Next.js 14 + Tailwind + 核心頁面",
  "files": [
    {"path": "package.json", "content": "{\n  \"name\": \"qrbro-frontend\",\n  \"version\": \"0.1.0\"...\n}"},
    {"path": "app/layout.tsx", "content": "import './globals.css'\n\nexport default function RootLayout..."},
    {"path": "app/page.tsx", "content": "export default function Home() {\n  return <main>...</main>\n}"}
  ]
}
```

## 讀取檔案

使用 `github_read_file` tool 讀取 repo 中的檔案：
```json
{"repo": "qrbro-frontend", "path": "package.json", "branch": "main"}
```

## 工具使用流程（必須按順序）

1. `github_list_repos` — 搜尋是否已有 repo
2. `github_create_repo` — 建立 repo（如不存在）
3. `github_create_pr` — 建立 branch + push 所有檔案 + 開 PR
4. `linear_add_comment` — 在 Linear issue 記錄 PR URL

## 最佳實踐

- Repo 名稱用小寫 kebab-case（如 `qrbro-frontend`、`qrbro-backend`）
- Branch 命名：`feat/xxx`、`fix/xxx`、`docs/xxx`
- PR body 包含：變更說明、檔案清單、相關 issue
- 一個 PR 可以包含多個檔案（建議一次 push 完整專案骨架）
- 檔案 content 是完整的檔案內容（不是 diff）

## 重要提醒

- **你必須使用這些工具建立真實的 GitHub repo 和 PR**
- 不要只在 Linear comment 中描述你「想要」建立什麼
- 不要在 comment 中貼程式碼片段代替建立 PR
- 先用 github_list_repos 檢查是否已存在，避免重複建立
