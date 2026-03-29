const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Agents ─────────────────────────────────────────────────────────────

export interface AgentState {
  status: string;
  issue_id?: string;
  issue_title?: string;
  current_turn?: number;
  tokens_used?: number;
  last_tool?: string;
  started_at?: string;
  updated_at?: string;
  last_issue_id?: string;
  last_tokens?: number;
  last_summary?: string;
  last_success?: boolean;
  completed_at?: string;
}

export interface Agent {
  role: string;
  name: string;
  emoji: string;
  color: string;
  avatar_url: string;
  state: AgentState;
  config?: Record<string, unknown>;
}

export const getAgents = () => fetchAPI<Agent[]>("/api/agents");
export const getAgent = (role: string) => fetchAPI<Agent>(`/api/agents/${role}`);
export const updateAgentConfig = (role: string, config: Record<string, unknown>) =>
  fetchAPI(`/api/agents/${role}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });

// ── Metrics ────────────────────────────────────────────────────────────

export interface AggregateMetrics {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  total_tokens: number;
  avg_tokens_per_run: number;
  avg_duration_ms: number;
  estimated_cost_usd: number;
}

export interface RunRecord {
  id?: number;
  agent_role: string;
  issue_id: string;
  tokens_used: number;
  model_used: string;
  duration_ms: number;
  success: boolean;
  error_message: string;
  summary: string;
  created_at?: string;
  timestamp?: string;
}

export interface TokenUsage {
  period: string;
  agent_role: string;
  tokens: number;
  runs: number;
  cost_usd: number;
}

export interface CostBreakdown {
  total_cost_usd: number;
  by_agent: Record<
    string,
    {
      runs: number;
      tokens: number;
      cost_usd: number;
      models: Record<string, { runs: number; tokens: number; cost_usd: number }>;
    }
  >;
}

export const getMetrics = (params?: { agent_role?: string; since?: string }) => {
  const sp = new URLSearchParams();
  if (params?.agent_role) sp.set("agent_role", params.agent_role);
  if (params?.since) sp.set("since", params.since);
  return fetchAPI<AggregateMetrics>(`/api/metrics?${sp}`);
};

export const getRuns = (params?: {
  agent_role?: string;
  limit?: number;
  offset?: number;
}) => {
  const sp = new URLSearchParams();
  if (params?.agent_role) sp.set("agent_role", params.agent_role);
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  return fetchAPI<RunRecord[]>(`/api/metrics/runs?${sp}`);
};

export const getTokenUsage = (params?: {
  period?: string;
  agent_role?: string;
  limit?: number;
}) => {
  const sp = new URLSearchParams();
  if (params?.period) sp.set("period", params.period);
  if (params?.agent_role) sp.set("agent_role", params.agent_role);
  if (params?.limit) sp.set("limit", String(params.limit));
  return fetchAPI<TokenUsage[]>(`/api/metrics/tokens?${sp}`);
};

export const getCosts = (params?: { since?: string }) => {
  const sp = new URLSearchParams();
  if (params?.since) sp.set("since", params.since);
  return fetchAPI<CostBreakdown>(`/api/metrics/costs?${sp}`);
};

// ── Memory ─────────────────────────────────────────────────────────────

export interface Soul {
  role: string;
  name?: string;
  emoji?: string;
  content: string;
  line_count: number;
  has_content?: boolean;
}

export interface ProjectContext {
  project_id: string;
  content: string;
  line_count?: number;
  has_content?: boolean;
}

export const getSouls = () => fetchAPI<Soul[]>("/api/memory/souls");
export const getSoul = (role: string) => fetchAPI<Soul>(`/api/memory/souls/${role}`);
export const updateSoul = (role: string, content: string) =>
  fetchAPI(`/api/memory/souls/${role}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });

export const getProjects = () => fetchAPI<ProjectContext[]>("/api/memory/projects");
export const getProject = (id: string) =>
  fetchAPI<ProjectContext>(`/api/memory/projects/${id}`);
export const updateProject = (id: string, content: string) =>
  fetchAPI(`/api/memory/projects/${id}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });

// ── Skills ─────────────────────────────────────────────────────────────

export interface Skill {
  name: string;
  content?: string;
  line_count: number;
  preview?: string;
}

export const getSkills = () => fetchAPI<Skill[]>("/api/skills");
export const getSkill = (name: string) => fetchAPI<Skill>(`/api/skills/${name}`);
export const updateSkill = (name: string, content: string) =>
  fetchAPI(`/api/skills/${name}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
export const createSkill = (name: string, content: string) =>
  fetchAPI("/api/skills", {
    method: "POST",
    body: JSON.stringify({ name, content }),
  });
export const deleteSkill = (name: string) =>
  fetchAPI(`/api/skills/${name}`, { method: "DELETE" });

// ── Logs ───────────────────────────────────────────────────────────────

export interface LogEntry {
  id: number;
  agent_role: string;
  issue_id: string;
  level: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface LearningLog {
  content: string;
  line_count: number;
  recent: string[];
}

export const getLogs = (params?: {
  agent_role?: string;
  level?: string;
  limit?: number;
  offset?: number;
}) => {
  const sp = new URLSearchParams();
  if (params?.agent_role) sp.set("agent_role", params.agent_role);
  if (params?.level) sp.set("level", params.level);
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  return fetchAPI<LogEntry[]>(`/api/logs?${sp}`);
};

export const getLearningLog = () => fetchAPI<LearningLog>("/api/logs/learning");

// ── WebSocket ──────────────────────────────────────────────────────────

export function connectWebSocket(
  onMessage: (event: { type: string; data: unknown }) => void
): WebSocket {
  const ws = new WebSocket(`${WS_URL}/api/ws`);
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage(data);
    } catch {
      // ignore parse errors
    }
  };
  return ws;
}
