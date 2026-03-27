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

TOOL_DISCORD_ASK_USER = {
    "name": "discord_ask_user",
    "description": "Ask the user a question in the Discord thread and wait for their reply. Use when you need clarification or a decision.",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user (in 繁體中文)",
            },
            "urgent": {
                "type": "boolean",
                "description": "If true, ping the user multiple times (default: false)",
            },
        },
        "required": ["question"],
    },
}

TOOL_DISCORD_DISCUSS = {
    "name": "discord_discuss",
    "description": "Post a message in the Discord thread to discuss with other agents or share observations. Does not wait for reply.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to post (in 繁體中文)",
            },
        },
        "required": ["message"],
    },
}

TOOL_DISCORD_REPORT_BLOCKER = {
    "name": "discord_report_blocker",
    "description": "Report a blocking issue that requires user decision. Pings the user and waits for reply.",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Description of the blocker and what decision is needed",
            },
        },
        "required": ["description"],
    },
}

TOOL_UPDATE_PROJECT_CONTEXT = {
    "name": "update_project_context",
    "description": "Record an important project decision, requirement, or constraint for other agents to reference.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["requirement", "decision", "constraint", "user_preference"],
                "description": "Category of the information",
            },
            "content": {
                "type": "string",
                "description": "The information to record (in 繁體中文)",
            },
        },
        "required": ["category", "content"],
    },
}

# Tool sets per agent type
CONVERSATIONAL_TOOLS = [
    TOOL_DISCORD_ASK_USER,
    TOOL_DISCORD_DISCUSS,
    TOOL_DISCORD_REPORT_BLOCKER,
    TOOL_UPDATE_PROJECT_CONTEXT,
]

PLANNING_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_LINEAR_QUERY_ISSUES,
    TOOL_DISCORD_NOTIFY,
    TOOL_COMPLETE_TASK,
] + CONVERSATIONAL_TOOLS

TOOL_VERCEL_DEPLOY = {
    "name": "vercel_deploy",
    "description": (
        "Deploy a GitHub repo to Vercel. Creates a Vercel project linked to the repo "
        "and triggers a production deployment. Returns the deployment URL."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "GitHub repo (owner/name format, e.g. 'mkkb2156/hello-world')",
            },
            "project_name": {
                "type": "string",
                "description": "Vercel project name (optional, defaults to repo name)",
            },
            "framework": {
                "type": "string",
                "enum": ["nextjs", "vite", "remix", "astro", "nuxtjs", "static"],
                "description": "Framework preset (default: nextjs)",
            },
        },
        "required": ["repo"],
    },
}

TOOL_GITHUB_MERGE_PR = {
    "name": "github_merge_pr",
    "description": "Merge a pull request after review passes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository (owner/name)"},
            "pr_number": {"type": "integer", "description": "Pull request number"},
            "merge_method": {
                "type": "string",
                "enum": ["merge", "squash", "rebase"],
                "description": "Merge method (default: squash)",
            },
        },
        "required": ["repo", "pr_number"],
    },
}

TOOL_VERCEL_CHECK_DEPLOY = {
    "name": "vercel_check_deploy",
    "description": (
        "Check Vercel deployment status and get build logs if failed. "
        "Use after vercel_deploy or after merging a PR to verify deployment succeeded."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "Vercel project name",
            },
        },
        "required": ["project_name"],
    },
}

BUILD_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_DISCORD_NOTIFY,
    TOOL_GITHUB_LIST_REPOS,
    TOOL_GITHUB_CREATE_REPO,
    TOOL_GITHUB_CREATE_PR,
    TOOL_GITHUB_READ_FILE,
    TOOL_GITHUB_MERGE_PR,
    TOOL_VERCEL_DEPLOY,
    TOOL_VERCEL_CHECK_DEPLOY,
    TOOL_COMPLETE_TASK,
] + CONVERSATIONAL_TOOLS

VERIFY_TOOLS = [
    TOOL_LINEAR_UPDATE_ISSUE,
    TOOL_LINEAR_ADD_COMMENT,
    TOOL_LINEAR_CREATE_ISSUE,
    TOOL_LINEAR_QUERY_ISSUES,
    TOOL_DISCORD_NOTIFY,
    TOOL_GITHUB_READ_FILE,
    TOOL_GITHUB_MERGE_PR,
    TOOL_VERCEL_CHECK_DEPLOY,
    TOOL_COMPLETE_TASK,
] + CONVERSATIONAL_TOOLS

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
