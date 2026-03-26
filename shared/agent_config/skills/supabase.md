# Supabase / PostgreSQL 最佳實踐

## Schema 設計
```sql
-- 命名：snake_case，複數表名
-- 必備欄位：id (UUID), created_at, updated_at
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- updated_at 自動更新觸發器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

## Row Level Security (RLS)
```sql
ALTER TABLE todos ENABLE ROW LEVEL SECURITY;

-- 使用者只能存取自己的資料
CREATE POLICY "Users can CRUD own data" ON todos
    FOR ALL USING (auth.uid() = user_id);

-- 公開讀取（如需要）
CREATE POLICY "Public read" ON posts
    FOR SELECT USING (published = true);
```

## 索引策略
```sql
-- 外鍵一定要加索引
CREATE INDEX idx_todos_user_id ON todos(user_id);
-- 常用查詢欄位
CREATE INDEX idx_todos_created_at ON todos(created_at DESC);
-- 複合索引（查詢順序很重要）
CREATE INDEX idx_scan_events_qr_date ON scan_events(qr_code_id, scanned_at DESC);
```

## FastAPI + SQLAlchemy Async 模式
```python
# core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

## Auth 整合（JWT）
```python
# core/security.py
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.utcnow() + timedelta(hours=24)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

def verify_token(token: str) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    return payload["sub"]
```

## Migration 管理
- 使用 Alembic 或原生 SQL 檔案
- 每個 migration 要可 rollback
- 命名：`001_create_users.sql`, `002_add_campaigns.sql`
- 永遠先在 staging 測試 migration

## 連線池設定
- 使用 Supavisor（Supabase 內建）
- Connection pooling mode: Transaction
- 最大連線數根據 plan 調整（Free: 60, Pro: 200）
