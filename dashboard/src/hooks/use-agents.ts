"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type Agent, connectWebSocket, getAgents } from "@/lib/api";

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getAgents();
      setAgents(data);
    } catch (e) {
      console.error("Failed to fetch agents:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();

    // Connect WebSocket for live updates
    const ws = connectWebSocket((event) => {
      if (event.type === "initial_state") {
        refresh();
      } else if (
        event.type === "agent_started" ||
        event.type === "agent_completed"
      ) {
        refresh();
      }
    });
    wsRef.current = ws;

    // Reconnect on close
    ws.onclose = () => {
      setTimeout(() => {
        if (wsRef.current === ws) refresh();
      }, 5000);
    };

    return () => {
      ws.close();
    };
  }, [refresh]);

  return { agents, loading, refresh };
}
