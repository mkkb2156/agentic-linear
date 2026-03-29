"use client";

import { useEffect, useState } from "react";
import {
  getSouls,
  getSoul,
  updateSoul,
  getProjects,
  getProject,
  updateProject,
  type Soul,
  type ProjectContext,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/card";

export default function MemoryPage() {
  const [tab, setTab] = useState<"souls" | "projects">("souls");
  const [souls, setSouls] = useState<Soul[]>([]);
  const [projects, setProjects] = useState<ProjectContext[]>([]);
  const [selectedSoul, setSelectedSoul] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (tab === "souls") {
      getSouls().then(setSouls).catch(console.error);
    } else {
      getProjects().then(setProjects).catch(console.error);
    }
  }, [tab]);

  useEffect(() => {
    if (selectedSoul) {
      getSoul(selectedSoul).then((s) => {
        setContent(s.content);
        setEditing(false);
      }).catch(console.error);
    }
  }, [selectedSoul]);

  useEffect(() => {
    if (selectedProject) {
      getProject(selectedProject).then((p) => {
        setContent(p.content);
        setEditing(false);
      }).catch(console.error);
    }
  }, [selectedProject]);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (tab === "souls" && selectedSoul) {
        await updateSoul(selectedSoul, content);
      } else if (tab === "projects" && selectedProject) {
        await updateProject(selectedProject, content);
      }
      setEditing(false);
    } catch (e) {
      console.error("Save failed:", e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold">Memory</h2>
        <div className="flex gap-1 ml-auto">
          <button
            onClick={() => { setTab("souls"); setSelectedProject(null); }}
            className={`px-3 py-1 text-sm rounded ${
              tab === "souls" ? "bg-[var(--accent)] text-white" : "text-[var(--muted)]"
            }`}
          >
            Agent Souls
          </button>
          <button
            onClick={() => { setTab("projects"); setSelectedSoul(null); }}
            className={`px-3 py-1 text-sm rounded ${
              tab === "projects" ? "bg-[var(--accent)] text-white" : "text-[var(--muted)]"
            }`}
          >
            Project Context
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List */}
        <div className="space-y-2">
          {tab === "souls" ? (
            souls.map((soul) => (
              <button
                key={soul.role}
                onClick={() => setSelectedSoul(soul.role)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedSoul === soul.role
                    ? "border-[var(--accent)] bg-[var(--accent)]/10"
                    : "border-[var(--card-border)] bg-[var(--card)] hover:border-[var(--muted)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span>{soul.emoji}</span>
                  <span className="text-sm font-medium">{soul.name || soul.role}</span>
                  <span className="ml-auto text-xs text-[var(--muted)]">
                    {soul.line_count} lines
                  </span>
                </div>
              </button>
            ))
          ) : projects.length === 0 ? (
            <p className="text-sm text-[var(--muted)] p-3">No projects yet</p>
          ) : (
            projects.map((proj) => (
              <button
                key={proj.project_id}
                onClick={() => setSelectedProject(proj.project_id)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedProject === proj.project_id
                    ? "border-[var(--accent)] bg-[var(--accent)]/10"
                    : "border-[var(--card-border)] bg-[var(--card)] hover:border-[var(--muted)]"
                }`}
              >
                <span className="text-sm font-mono">{proj.project_id}</span>
                <span className="ml-2 text-xs text-[var(--muted)]">
                  {proj.line_count} lines
                </span>
              </button>
            ))
          )}
        </div>

        {/* Content */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader
              title={
                tab === "souls"
                  ? selectedSoul || "Select a soul"
                  : selectedProject || "Select a project"
              }
              action={
                (selectedSoul || selectedProject) && (
                  <div className="flex gap-2">
                    {editing ? (
                      <>
                        <button
                          onClick={() => setEditing(false)}
                          className="px-2 py-1 text-xs text-[var(--muted)] hover:text-white"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleSave}
                          disabled={saving}
                          className="px-2 py-1 text-xs bg-[var(--accent)] text-white rounded"
                        >
                          {saving ? "Saving..." : "Save"}
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setEditing(true)}
                        className="px-2 py-1 text-xs text-[var(--muted)] hover:text-white"
                      >
                        Edit
                      </button>
                    )}
                  </div>
                )
              }
            />
            {selectedSoul || selectedProject ? (
              editing ? (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="w-full h-96 bg-black/30 rounded p-3 text-sm font-mono resize-y border border-[var(--card-border)] focus:border-[var(--accent)] outline-none"
                />
              ) : (
                <pre className="text-sm font-mono whitespace-pre-wrap text-[var(--muted)] max-h-[600px] overflow-auto">
                  {content || "(empty)"}
                </pre>
              )
            ) : (
              <p className="text-sm text-[var(--muted)] py-8 text-center">
                Select an item from the list
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
