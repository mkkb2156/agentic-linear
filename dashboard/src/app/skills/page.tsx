"use client";

import { useEffect, useState } from "react";
import {
  getSkills,
  getSkill,
  updateSkill,
  createSkill,
  deleteSkill,
  type Skill,
} from "@/lib/api";
import { Card, CardHeader } from "@/components/card";

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const loadSkills = () => getSkills().then(setSkills).catch(console.error);

  useEffect(() => {
    loadSkills();
  }, []);

  useEffect(() => {
    if (selected) {
      getSkill(selected)
        .then((s) => {
          setContent(s.content || "");
          setEditing(false);
        })
        .catch(console.error);
    }
  }, [selected]);

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await updateSkill(selected, content);
      setEditing(false);
      loadSkills();
    } catch (e) {
      console.error("Save failed:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      await createSkill(newName.trim(), "# " + newName.trim() + "\n\n");
      setCreating(false);
      setNewName("");
      loadSkills();
      setSelected(newName.trim());
    } catch (e) {
      console.error("Create failed:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selected || !confirm(`Delete skill "${selected}"?`)) return;
    try {
      await deleteSkill(selected);
      setSelected(null);
      setContent("");
      loadSkills();
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold">Skills</h2>
        <button
          onClick={() => setCreating(true)}
          className="ml-auto px-3 py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90"
        >
          + New Skill
        </button>
      </div>

      {/* Create Modal */}
      {creating && (
        <Card className="border-[var(--accent)]">
          <div className="flex items-center gap-3">
            <input
              autoFocus
              placeholder="Skill name (e.g. react-patterns)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="flex-1 bg-black/30 border border-[var(--card-border)] rounded px-3 py-1 text-sm focus:border-[var(--accent)] outline-none"
            />
            <button
              onClick={handleCreate}
              disabled={saving}
              className="px-3 py-1 text-sm bg-[var(--accent)] text-white rounded"
            >
              Create
            </button>
            <button
              onClick={() => setCreating(false)}
              className="px-3 py-1 text-sm text-[var(--muted)]"
            >
              Cancel
            </button>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Skill List */}
        <div className="space-y-2">
          {skills.map((skill) => (
            <button
              key={skill.name}
              onClick={() => setSelected(skill.name)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                selected === skill.name
                  ? "border-[var(--accent)] bg-[var(--accent)]/10"
                  : "border-[var(--card-border)] bg-[var(--card)] hover:border-[var(--muted)]"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">📚 {skill.name}</span>
                <span className="text-xs text-[var(--muted)]">
                  {skill.line_count} lines
                </span>
              </div>
              {skill.preview && (
                <p className="text-xs text-[var(--muted)] mt-1 truncate">
                  {skill.preview}
                </p>
              )}
            </button>
          ))}
        </div>

        {/* Skill Content */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader
              title={selected || "Select a skill"}
              action={
                selected && (
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
                      <>
                        <button
                          onClick={() => setEditing(true)}
                          className="px-2 py-1 text-xs text-[var(--muted)] hover:text-white"
                        >
                          Edit
                        </button>
                        <button
                          onClick={handleDelete}
                          className="px-2 py-1 text-xs text-[var(--error)] hover:opacity-80"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                )
              }
            />
            {selected ? (
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
                Select a skill from the list
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
