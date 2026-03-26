# Linear 工作流程最佳實踐

## Pipeline 狀態流程
```
Strategy Complete → Spec Complete → Architecture Complete
                                      ├→ Frontend Engineer (平行)
                                      └→ Backend Engineer  (平行)
                                                           ↓
                                    Implementation Done → QA Passed → Deployed → Deploy Complete
```

每個狀態變更會觸發下一個 agent。你的 `complete_task` 的 `next_status` 決定了下一個 agent。

## 讀取前一個 Agent 的產出

使用 `linear_query_issues` 查詢相關 issue：
```json
{"query": "QRBro"}
```

或直接查詢特定狀態的 issues：
```json
{"state_name": "Architecture Complete"}
```

前一個 agent 的產出在 issue 的 comments 中。你的 task payload 已包含 issue 內容。

## Comment 格式（重要）

每個 agent 的 comment 必須使用結構化 markdown：

```markdown
# [emoji] [標題]

## 1. 第一章節
內容...

## 2. 第二章節
內容...

## 結論 / 下一步
```

### 好的格式
- 使用 markdown headers (##) 分章節
- 程式碼用 code blocks（附語言標記）
- 列表用 bullet points
- 重要內容用**粗體**

### 不好的格式
- 一大段純文字沒有分段
- 沒有 code blocks 的程式碼
- 沒有結構的長篇大論

## Sub-issue 建立

使用 `linear_create_issue` 為主要功能模組建立 sub-issues：

```json
{
  "title": "[QRBro] Auth API — 使用者認證系統",
  "description": "## 任務\n- POST /auth/register\n- POST /auth/login\n- JWT middleware",
  "parent_id": "DRO-31"
}
```

命名規範：`[專案名] 功能名稱 — 簡短描述`

## 工具使用規則

1. **先讀後寫** — 用 `linear_query_issues` 了解上下文再開始工作
2. **一定要留 comment** — 你的產出必須發布為 Linear comment
3. **一定要 complete_task** — 否則 pipeline 會卡住
4. **next_status 要正確** — 錯誤的 status 會觸發錯誤的 agent

## 常見 next_status 對照
| 你的角色 | next_status |
|---------|-------------|
| 策略師 | Spec Complete |
| 規格師 | Spec Complete |
| 架構師 | Architecture Complete |
| 前端/後端工程師 | Implementation Done |
| QA 工程師 | QA Passed |
| DevOps | Deployed |
| 發版管理 | Deploy Complete |

## 注意事項
- 所有 comment 使用繁體中文
- 技術術語保留英文
- 引用前一個 agent 的產出時使用引用格式 (>)
- 不要在 comment 中暴露 API keys 或 tokens
