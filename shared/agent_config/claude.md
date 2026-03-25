# 全域規範 — Drone168 Agent Platform

此文件是所有 Agent 的最高優先規範。任何 agent 的 system prompt 都會先載入此文件。

## 語言規範
- **Linear comment** 和 **Discord 通知** 必須使用**繁體中文**
- 程式碼、變數名、API endpoint、技術術語保留英文
- 錯誤訊息和 log 使用英文

## 程式碼風格
- Python 3.12+, async/await throughout
- Type hints on all public functions
- Pydantic for all data models
- httpx for HTTP clients
- Ruff linting (line-length 100)
- Prefer simple, direct solutions — avoid over-engineering

## 安全規範
- 絕不在 comment、PR、Discord 中暴露 API key、token、password
- 不執行破壞性操作（刪除 repo、drop table）除非明確要求
- 所有使用者輸入必須驗證

## 回覆格式
- 使用 Markdown 格式
- 重要決策和結論使用**粗體**標記
- 程式碼使用 code block（附帶語言標記）
- 技術規格包含表格、清單、程式碼範例

## 工具使用
- 必須使用工具執行任務，不要只描述你想做什麼
- 完成後必須呼叫 `complete_task` 並提供摘要和下一個狀態
- 在 Linear issue 上留下你的分析結果作為 comment
- 通知重要進度到 Discord

## 協作規範
- 讀取前一個 agent 的 comment 作為輸入
- 你的產出是下一個 agent 的輸入 — 必須清晰、完整、可執行
- 建立 sub-issues 分解大型任務
