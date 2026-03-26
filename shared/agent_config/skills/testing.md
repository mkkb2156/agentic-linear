# 測試最佳實踐

## 測試金字塔
- **Unit Tests (70%)** — 單一函式/元件，快速，無外部依賴
- **Integration Tests (20%)** — API endpoints，含 DB/Redis
- **E2E Tests (10%)** — 完整使用者流程，Playwright

## pytest（Python 後端）

### 基本結構
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

@pytest.fixture
async def auth_headers(client):
    resp = await client.post("/auth/register", json={...})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### 測試模式
```python
# tests/test_campaigns.py
@pytest.mark.asyncio
async def test_create_campaign(client, auth_headers):
    resp = await client.post("/campaigns", json={"name": "Test"}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Test"

@pytest.mark.parametrize("name,expected", [("", 422), ("x" * 256, 422), ("Valid", 201)])
async def test_campaign_validation(client, auth_headers, name, expected):
    resp = await client.post("/campaigns", json={"name": name}, headers=auth_headers)
    assert resp.status_code == expected
```

### Mock 策略
```python
from unittest.mock import AsyncMock, patch

@patch("app.services.email.send_email", new_callable=AsyncMock)
async def test_with_mock(mock_send, client):
    mock_send.return_value = True
    # ... test code
    mock_send.assert_called_once()
```

## Vitest（前端）
```typescript
// __tests__/components/Button.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "@/components/ui/button";

test("renders button with text", () => {
  render(<Button>Click me</Button>);
  expect(screen.getByText("Click me")).toBeInTheDocument();
});

test("calls onClick handler", async () => {
  const onClick = vi.fn();
  render(<Button onClick={onClick}>Click</Button>);
  await fireEvent.click(screen.getByText("Click"));
  expect(onClick).toHaveBeenCalledOnce();
});
```

## Playwright（E2E）
```typescript
// e2e/auth.spec.ts
import { test, expect } from "@playwright/test";

test("user can login", async ({ page }) => {
  await page.goto("/login");
  await page.fill("[name=email]", "test@example.com");
  await page.fill("[name=password]", "password123");
  await page.click("button[type=submit]");
  await expect(page).toHaveURL("/dashboard");
});
```

## 覆蓋率要求
- 整體 >80%
- 核心業務邏輯 >90%
- API endpoints 100%（每個 endpoint 至少一個 test）
- 使用 `pytest --cov=app --cov-report=html`
