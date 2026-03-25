CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_name VARCHAR(50) NOT NULL,
    agent_role VARCHAR(50) NOT NULL,
    issue_id VARCHAR(20) NOT NULL,
    project_id UUID,
    payload JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    model_used VARCHAR(30),
    tokens_used INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    idempotency_key VARCHAR(100) UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_tasks_pending
    ON agent_tasks (queue_name, created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_tasks_issue
    ON agent_tasks (issue_id);
