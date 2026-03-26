# 部署最佳實踐

## Railway 部署

### Dockerfile（Python 後端）
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### 環境變數
- 在 Railway Dashboard → Variables 設定
- 必備：`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`
- 使用 Railway 的 Reference Variables（`${{Postgres.DATABASE_URL}}`）

### Health Check
```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```
Railway 自動偵測 `/health` endpoint。

## Vercel 部署（Next.js）

### 自動部署
- 連結 GitHub repo → 每次 push 自動部署
- Preview deployments on every PR
- Production on merge to main

### 環境變數
- Vercel Dashboard → Settings → Environment Variables
- `NEXT_PUBLIC_*` 前綴的變數會暴露給 client

### vercel.json（可選）
```json
{
  "framework": "nextjs",
  "buildCommand": "next build",
  "outputDirectory": ".next"
}
```

## Docker Compose（本地開發）
```yaml
version: "3.8"
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

volumes:
  pgdata:
```

## CI/CD（GitHub Actions）
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: pytest --cov=app
```

## Rollback 策略
1. Railway: Redeploy previous successful deployment
2. Vercel: Instant rollback via dashboard
3. DB: 每個 migration 要有 DOWN migration
4. 環境變數: 保留上一版的 .env backup

## 監控
- Railway: 內建 logs + metrics
- Vercel: Analytics + Web Vitals
- 自訂: Sentry for error tracking
- Health check endpoint + uptime monitoring
