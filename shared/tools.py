"""Claude Tool Use definitions for all agents."""

from __future__ import annotations

TOOL_LINEAR_UPDATE_ISSUE = {
    "name": "linear_update_issue",
    "description": "Update a Linear issue's status, description, assignee, or other fields.",
    "input_schema": {
        "type": "object",
        "properties": {
            "issue_id": {
                "type": "string",
                "description": "The Linear issue ID (e.g. the UUID, not the identifier like DRO-42)",
            },
            "state_name": {
                "type": "string",
                "description": "New status name to transition to (e.g. 'Spec Complete', 'Architecture Complete')",
            },
            "description": {
                "type": "string",
                "description": "Updated issue description (markdown)",
            },
        },
        "required": ["issue_id"],
    },
}

TOOL_LINEAR_ADD_COMMENT = {
    "name": "linear_add_comment",
    "description": "Add a comment to a Linear issue. Use this to post your analysis, deliverables, or status updates.",
    "input_schema": {
        "type": "object",
        "properties": {
            "issue_id": {
                "type": "string",
                "description": "The Linear issue ID",
            },
            "body": {
                "type": "string",
                "description": "Comment body in markdown format",
            },
        },
        "required": ["issue_id", "body"],
    },
}

TOOL_LINEAR_CREATE_ISSUE = {
    "name": "linear_create_issue",
    "description": "Create a new Linear issue (e.g. a sub-task or follow-up).",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Issue title",
            },
            "description": {
                "type": "string",
                "description": "Issue description in markdown",
            },
            "parent_id": {
                "type": "string",
                "description": "Parent issue ID (to create a sub-issue)",
            },
        },
        "required": ["title"],
    },
}

TOOL_LINEAR_QUERY_ISSUES = {
    "name": "linear_query_issues",
    "description": "Search/query Linear issues by filter criteria.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string",
            },
            "state_name": {
                "type": "string",
                "description": "Filter by status name",
            },
        },
        "required": [],
    },
}

TOOL_DISCORD_NOTIFY = {
    "name": "discord_notify",
    "description": "Send a notification to Discord with your progress or results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "enum": ["agent_hub", "dashboard", "alerts", "deploy_log"],
                "description": "Discord channel to send to",
            },
            "title": {
                "type": "string",
                "description": "Notification title",
            },
            "description": {
                "type": "string",
                "description": "Notification body (markdown)",
            },
        },
        "required": ["channel", "title", "description"],
    },
}

TOOL_COMPLETE_TASK = {
    "name": "complete_task",
    "description": "Signal that you have finished processing this task. Call this when your work is done. Provide a summary of what you accomplished and the next pipeline status to transition to.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of what was accomplished",
            },
            "next_status": {
                "type": "string",
                "description": "The Linear status to transition the issue to (e.g. 'Strategy Complete', 'Spec Complete', 'Architecture Complete', 'Implementation Done')",
            },
        },
        "required": ["summary", "next_status"],
    },
}

TOOL_GITHUB_CREATE_REPO = {
    "name": "github_create_repo",
    "description": (
        "Find an existing GitHub repo or create a new one. "
        "Use this before github_create_pr if you need to set up a new project repo."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Repository name (e.g. 'my-todo-app')",
            },
            "description": {
                "type": "string",
                "description": "Repository description",
            },
            "private": {
                "type": "boolean",
                "description": "Whether the repo should be private (default: false)",
            },
        },
        "required": ["name"],
    },
}

TOOL_GITHUB_CREATE_PR = {
    "name": "github_create_pr",
    "description": "Create a GitHub pull request with code changes on a specific repo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository name (e.g. 'my-todo-app' or 'owner/my-todo-app')",
            },
            "branch_name": {"type": "string", "description": "New branch name"},
            "title": {"type": "string", "description": "PR title"},
            "body": {"type": "string", "description": "PR description"},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path in repo"},
                        "content": {"type": "string", "description": "File content"},
                    },
                    "required": ["path", "content"],
                },
                "description": "Files to create/update",
            },
        },
        "required": ["repo", "branch_name", "title", "files"],
    },
}

TOOL_GITHUB_READ_FILE = {
    "name": "github_read_file",
    "description": "Read a file from a GitHub repository.",
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository name (e.g. 'my-todo-app' or 'owner/my-todo-app')",
            },
            "path": {"type": "string", "description": "File path in repo"},
            "branch": {
                "type": "string",
                "description": "Branch to read from (default: main)",
            },
        },
        "required": ["repo", "path"],
    },
}

TOOL_GITHUB_LIST_REPOS = {
    "name": "github_list_repos",
    "description": "List available GitHub repositories. Use to find existing repos before creating new ones.",
    "input_schema": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Optional search query to filter repos by name",
            },
        },
        "required": [],
    },
}

TOOL_QUERY_METRICS = {
    "name": "query_metrics",
    "description": "Query agent execution metrics. Returns aggregate stats like total runs, tokens, success rate, cost.",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_role": {"type": "string", "description": "Filter by agent role (optional)"},
            "days": {"type": "integer", "description": "Look back N days (default: 7)"},
        },
        "required": [],
    },
}

TOOL_GET_AGENT_CONFIG = {
    "name": "get_agent_config",
    "description": "Get a specific agent's YAML configuration (model, skills, max_turns, enabled).",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_role": {"type": "string", "description": "Agent role name"},
        },
        "required": ["agent_role"],
    },
}

TOOL_UPDATE_AGENT_CONFIG = {
    "name": "update_agent_config",
    "description": "Update an agent's configuration (model, skills list, max_turns, enabled).",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_role": {"type": "string", "description": "Agent role name"},
            "model": {"type": "string", "description": "Model to use (sonnet or opus)"},
            "max_turns": {"type": "integer", "description": "Maximum tool-use turns"},
            "skills": {"type": "array", "items": {"type": "string"}, "description": "Skill names to load"},
            "enabled": {"type": "boolean", "description": "Whether agent is enabled"},
        },
        "required": ["agent_role"],
    },
}

TOOL_LIST_SKILLS = {
    "name": "list_skills",
    "description": "List all available skill files.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

TOOL_READ_SKILL = {
    "name": "read_skill",
    "description": "Read the content of a skill file.",
    "input_schema": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Skill name (without .md)"}},
        "required": ["name"],
    },
}

TOOL_WRITE_SKILL = {
    "name": "write_skill",
    "description": "Create or update a skill file with new content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name (without .md)"},
            "content": {"type": "string", "description": "Skill content in markdown"},
        },
        "required": ["name", "content"],
    },
}

TOOL_READ_LEARNINGS = {
    "name": "read_learnings",
    "description": "Read the agent learning log.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

TOOL_GENERATE_REPORT = {
    "name": "generate_report",
    "description": "Generate a formatted performance report for agents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "report_type": {"type": "string", "enum": ["daily", "weekly", "agent_detail"], "description": "Report type"},
            "agent_role": {"type": "string", "description": "Agent role for detail report (optional)"},
        },
        "required": ["report_type"],
    },
}

# Tool sets per agent type
PLANNING_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_LINEAR_QUERY_ISSUES,
    TOOL_DISCORD_NOTIFY,
    TOOL_COMPLETE_TASK,
]

BUILD_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_DISCORD_NOTIFY,
    TOOL_GITHUB_LIST_REPOS,
    TOOL_GITHUB_CREATE_REPO,
    TOOL_GITHUB_CREATE_PR,
    TOOL_GITHUB_READ_FILE,
    TOOL_COMPLETE_TASK,
]

VERIFY_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_QUERY_ISSUES,
    TOOL_DISCORD_NOTIFY,
    TOOL_COMPLETE_TASK,
]

ADMIN_TOOLS = [
    TOOL_QUERY_METRICS,
    TOOL_GET_AGENT_CONFIG,
    TOOL_UPDATE_AGENT_CONFIG,
    TOOL_LIST_SKILLS,
    TOOL_READ_SKILL,
    TOOL_WRITE_SKILL,
    TOOL_READ_LEARNINGS,
    TOOL_GENERATE_REPORT,
    TOOL_DISCORD_NOTIFY,
    TOOL_COMPLETE_TASK,
]
