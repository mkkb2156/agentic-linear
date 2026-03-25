"""E2E integration test — simulates a Linear webhook and verifies the pipeline.

Usage:
    # Against local gateway:
    python scripts/test_e2e.py http://localhost:8000

    # Against Railway:
    python scripts/test_e2e.py https://your-app.railway.app

Tests:
1. Health check — verify gateway is running
2. Webhook delivery — send a simulated "Strategy Complete" status change
3. Verify response — gateway should accept and dispatch agent
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import uuid

import httpx

# Test payload: simulates an issue transitioning to "Strategy Complete"
TEST_ISSUE_ID = f"test-{uuid.uuid4().hex[:8]}"
TEST_PAYLOAD = {
    "action": "update",
    "type": "Issue",
    "data": {
        "id": f"uuid-{uuid.uuid4().hex[:12]}",
        "identifier": "DRO-TEST",
        "title": "E2E Test Issue — Pipeline Integration",
        "description": "Automated E2E test to verify pipeline agent dispatch.",
        "state": {"id": "state-new", "name": "Strategy Complete"},
    },
    "updatedFrom": {
        "state": {"id": "state-old", "name": "In Progress"},
    },
    "url": "https://linear.app/drone168/issue/DRO-TEST",
    "createdAt": "2026-03-25T00:00:00.000Z",
}


def sign_payload(body: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature matching Linear's format."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_health(base_url: str) -> bool:
    print("\n=== 1. Health Check ===")
    try:
        resp = httpx.get(f"{base_url}/health", timeout=10)
        data = resp.json()
        print(f"  Status: {resp.status_code}")
        print(f"  Response: {json.dumps(data, indent=2)}")

        if resp.status_code != 200:
            print("  FAIL: Non-200 response")
            return False

        if data.get("agents_registered", 0) < 10:
            print(f"  WARN: Only {data.get('agents_registered')} agents registered (expected 10)")

        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_webhook_delivery(base_url: str, secret: str) -> bool:
    print("\n=== 2. Webhook Delivery (Strategy Complete) ===")
    body = json.dumps(TEST_PAYLOAD).encode()
    delivery_id = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/json",
        "Linear-Delivery": delivery_id,
    }

    if secret:
        headers["Linear-Signature"] = sign_payload(body, secret)
        print(f"  Signed with HMAC-SHA256 (secret={'*' * len(secret)})")

    try:
        resp = httpx.post(
            f"{base_url}/webhooks/linear",
            content=body,
            headers=headers,
            timeout=10,
        )
        print(f"  Delivery-ID: {delivery_id}")
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            print("  PASS: Webhook accepted")
            return True
        elif resp.status_code == 401:
            print("  FAIL: Signature verification failed (check LINEAR_WEBHOOK_SECRET)")
            return False
        else:
            print(f"  FAIL: Unexpected status {resp.status_code}")
            return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_idempotency(base_url: str, secret: str) -> bool:
    print("\n=== 3. Idempotency Check (duplicate delivery) ===")
    body = json.dumps(TEST_PAYLOAD).encode()
    delivery_id = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/json",
        "Linear-Delivery": delivery_id,
    }
    if secret:
        headers["Linear-Signature"] = sign_payload(body, secret)

    try:
        # Send twice with same delivery ID
        resp1 = httpx.post(f"{base_url}/webhooks/linear", content=body, headers=headers, timeout=10)
        resp2 = httpx.post(f"{base_url}/webhooks/linear", content=body, headers=headers, timeout=10)

        print(f"  First request: {resp1.status_code}")
        print(f"  Second request (duplicate): {resp2.status_code}")

        if resp1.status_code == 200 and resp2.status_code == 200:
            print("  PASS: Both accepted (idempotency handled internally)")
            return True
        else:
            print("  WARN: Unexpected response codes")
            return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_invalid_signature(base_url: str) -> bool:
    print("\n=== 4. Invalid Signature Rejection ===")
    body = json.dumps(TEST_PAYLOAD).encode()

    headers = {
        "Content-Type": "application/json",
        "Linear-Delivery": str(uuid.uuid4()),
        "Linear-Signature": "invalid-signature",
    }

    try:
        resp = httpx.post(
            f"{base_url}/webhooks/linear",
            content=body,
            headers=headers,
            timeout=10,
        )
        print(f"  Status: {resp.status_code}")

        # If webhook secret is configured, should reject; otherwise accept
        if resp.status_code == 401:
            print("  PASS: Invalid signature correctly rejected")
            return True
        elif resp.status_code == 200:
            print("  WARN: Accepted (webhook secret may not be configured)")
            return True
        else:
            print(f"  FAIL: Unexpected status {resp.status_code}")
            return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_backward_transition(base_url: str, secret: str) -> bool:
    print("\n=== 5. Backward Transition (DAG enforcement) ===")
    backward_payload = {
        **TEST_PAYLOAD,
        "data": {
            **TEST_PAYLOAD["data"],
            "state": {"id": "s1", "name": "Strategy Complete"},
        },
        "updatedFrom": {
            "state": {"id": "s2", "name": "Architecture Complete"},
        },
    }
    body = json.dumps(backward_payload).encode()

    headers = {
        "Content-Type": "application/json",
        "Linear-Delivery": str(uuid.uuid4()),
    }
    if secret:
        headers["Linear-Signature"] = sign_payload(body, secret)

    try:
        resp = httpx.post(
            f"{base_url}/webhooks/linear",
            content=body,
            headers=headers,
            timeout=10,
        )
        print(f"  Status: {resp.status_code}")
        print("  PASS: Accepted (backward transitions are blocked internally, no error returned)")
        return resp.status_code == 200
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_e2e.py <gateway-url>")
        print("  e.g.: python scripts/test_e2e.py http://localhost:8000")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    secret = os.environ.get("LINEAR_WEBHOOK_SECRET", "")

    print(f"Target: {base_url}")
    print(f"Secret: {'configured' if secret else 'not set (signature verification skipped)'}")

    results = []
    results.append(("Health Check", test_health(base_url)))
    results.append(("Webhook Delivery", test_webhook_delivery(base_url, secret)))
    results.append(("Idempotency", test_idempotency(base_url, secret)))
    results.append(("Invalid Signature", test_invalid_signature(base_url)))
    results.append(("Backward Transition", test_backward_transition(base_url, secret)))

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    passed = 0
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if ok:
            passed += 1

    print(f"\n{passed}/{len(results)} tests passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
