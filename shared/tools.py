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

TOOL_GITHUB_CREATE_PR = {
    "name": "github_create_pr",
    "description": "Create a GitHub pull request with code changes.",
    "input_schema": {
        "type": "object",
        "properties": {
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
        "required": ["branch_name", "title", "files"],
    },
}

TOOL_GITHUB_READ_FILE = {
    "name": "github_read_file",
    "description": "Read a file from the GitHub repository.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path in repo"},
            "branch": {
                "type": "string",
                "description": "Branch to read from (default: main)",
            },
        },
        "required": ["path"],
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
