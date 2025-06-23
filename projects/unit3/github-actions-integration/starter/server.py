#!/usr/bin/env python3
"""
Module 2: GitHub Actions Integration - STARTER CODE
Extend your PR Agent with webhook handling and MCP Prompts for CI/CD workflows.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("pr-agent-actions")

# PR template directory (shared between starter and solution)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

# Default PR templates
DEFAULT_TEMPLATES = {
    "bug.md": "Bug Fix",
    "feature.md": "Feature",
    "docs.md": "Documentation",
    "refactor.md": "Refactor",
    "test.md": "Test",
    "performance.md": "Performance",
    "security.md": "Security"
}

mcp = FastMCP("pr-agent")
# Hint: EVENTS_FILE = Path(__file__).parent / "github_events.json"
EVENTS_FILE = Path(__file__).parent / "github_events.json"

# Type mapping for PR templates
TYPE_MAPPING = {
    "bug": "bug.md",
    "fix": "bug.md",
    "feature": "feature.md",
    "enhancement": "feature.md",
    "docs": "docs.md",
    "documentation": "docs.md",
    "refactor": "refactor.md",
    "cleanup": "refactor.md",
    "test": "test.md",
    "testing": "test.md",
    "performance": "performance.md",
    "optimization": "performance.md",
    "security": "security.md"
}


# ===== Module 1 Tools (Already includes output limiting fix from Module 1) =====

@mcp.tool()
async def analyze_file_changes(
        base_branch: str = "main",
        include_diff: bool = True,
        max_diff_lines: int = 500
) -> str:
    """Get the full diff and list of changed files in the current git repository.
    
    Args:
        base_branch: Base branch to compare against (default: main)
        include_diff: Include the full diff content (default: true)
        max_diff_lines: Maximum number of diff lines to include (default: 500)
    """
    try:
        # Get list of changed files
        files_result = subprocess.run(
            ["git", "diff", "--name-status", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True
        )

        # Get diff statistics
        stat_result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True
        )

        # Get the actual diff if requested
        diff_content = ""
        truncated = False
        if include_diff:
            diff_result = subprocess.run(
                ["git", "diff", f"{base_branch}...HEAD"],
                capture_output=True,
                text=True
            )
            diff_lines = diff_result.stdout.split('\n')

            # Check if we need to truncate (learned from Module 1)
            if len(diff_lines) > max_diff_lines:
                diff_content = '\n'.join(diff_lines[:max_diff_lines])
                diff_content += f"\n\n... Output truncated. Showing {max_diff_lines} of {len(diff_lines)} lines ..."
                diff_content += "\n... Use max_diff_lines parameter to see more ..."
                truncated = True
            else:
                diff_content = diff_result.stdout

        # Get commit messages for context
        commits_result = subprocess.run(
            ["git", "log", "--oneline", f"{base_branch}..HEAD"],
            capture_output=True,
            text=True
        )

        analysis = {
            "base_branch": base_branch,
            "files_changed": files_result.stdout,
            "statistics": stat_result.stdout,
            "commits": commits_result.stdout,
            "diff": diff_content if include_diff else "Diff not included (set include_diff=true to see full diff)",
            "truncated": truncated,
            "total_diff_lines": len(diff_lines) if include_diff else 0
        }

        return json.dumps(analysis, indent=2)

    except subprocess.CalledProcessError as e:
        return json.dumps({"error": f"Git error: {e.stderr}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_pr_templates() -> str:
    """List available PR templates with their content."""
    templates = [
        {
            "filename": filename,
            "type": template_type,
            "content": (TEMPLATES_DIR / filename).read_text()
        }
        for filename, template_type in DEFAULT_TEMPLATES.items()
    ]

    return json.dumps(templates, indent=2)


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """Let Claude analyze the changes and suggest the most appropriate PR template.
    
    Args:
        changes_summary: Your analysis of what the changes do
        change_type: The type of change you've identified (bug, feature, docs, refactor, test, etc.)
    """

    # Get available templates
    templates_response = await get_pr_templates()
    templates = json.loads(templates_response)

    # Find matching template
    template_file = TYPE_MAPPING.get(change_type.lower(), "feature.md")
    selected_template = next(
        (t for t in templates if t["filename"] == template_file),
        templates[0]  # Default to first template if no match
    )

    suggestion = {
        "recommended_template": selected_template,
        "reasoning": f"Based on your analysis: '{changes_summary}', this appears to be a {change_type} change.",
        "template_content": selected_template["content"],
        "usage_hint": "Claude can help you fill out this template based on the specific changes in your PR."
    }

    return json.dumps(suggestion, indent=2)


# ===== Module 2: New GitHub Actions Tools =====

@mcp.tool()
async def get_recent_actions_events(limit: int = 10) -> str:
    """Get recent GitHub Actions events received via webhook.
    
    Args:
        limit: Maximum number of events to return (default: 10)
    """
    try:
        with open(EVENTS_FILE, 'r') as f:
            events = json.load(f)
            if limit < len(events):
                recent_events = events[:limit]
                return json.dumps(recent_events, indent=2)
            return json.dumps(events, indent=2)
    except:
        return json.dumps([])


@mcp.tool()
async def get_workflow_status(workflow_name: Optional[str] = None) -> str:
    """Get the current status of GitHub Actions workflows.
    
    Args:
        workflow_name: Optional specific workflow name to filter by
    """
    crop_events = []
    try:
        with open(EVENTS_FILE, 'r') as f:
            events = json.load(f)
        for event in events:
            if event["workflow_run"]:
                if workflow_name is None or event["workflow_run"].get("name") == workflow_name:
                    crop_events.append(event)
        # Group by workflow and get latest status
        workflows = {}
        for event in crop_events:
            run = event["workflow_run"]
            name = run["name"]
            if name not in workflows or run["updated_at"] > workflows[name]["updated_at"]:
                workflows[name] = {
                    "name": name,
                    "status": run["status"],
                    "conclusion": run.get("conclusion"),
                    "run_number": run["run_number"],
                    "updated_at": run["updated_at"],
                    "html_url": run["html_url"]
                }
        return json.dumps(list(workflows.values()), indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to read events file"}, indent=2)


# ===== Module 2: MCP Prompts =====
@mcp.prompt()
async def analyze_ci_results():
    """Analyze recent CI/CD results and provide insights."""
    return (
        "Use `get_recent_actions_events()` to fetch the latest GitHub Actions activity. "
        "Then call `get_workflow_status()` for each relevant workflow run to collect status details. "
        "Summarize the outcomes, highlighting trends like frequently failing jobs, average execution time, "
        "or common failure causes. Provide actionable insights for improving CI stability and speed."
    )


@mcp.prompt()
async def create_deployment_summary():
    """Generate a deployment summary for team communication."""
    return (
        "Create a clear and concise deployment summary using the latest workflow run and commit metadata. "
        "Include the deployment time, triggered branch, author, key PRs included, and status of the deployment. "
        "If available, mention related issues resolved and link to the release or environment logs. "
        "Format the summary in markdown for posting in Slack or internal documentation."
    )


@mcp.prompt()
async def generate_pr_status_report():
    """Generate a comprehensive PR status report including CI/CD results."""
    return (
        "Gather all open pull requests and their associated GitHub Actions runs using `get_workflow_status()`. "
        "For each PR, include author, title, number, CI status (pass/fail/in-progress), and a short summary of code changes. "
        "Group PRs by status (ready to merge, needs attention, CI failing). Present the report in a readable markdown table."
    )


@mcp.prompt()
async def troubleshoot_workflow_failure():
    """Help troubleshoot a failing GitHub Actions workflow."""
    return (
        "Use `get_recent_actions_events()` to identify failed workflows. For each failure, use `get_workflow_status()` "
        "to retrieve job and step-level logs. Highlight the failed steps and provide likely root causes, "
        "based on error messages or repeated patterns. Suggest fixes or areas to investigate (e.g. dependency issues, "
        "permissions, flaky tests). Return a diagnosis summary with troubleshooting steps."
    )


if __name__ == "__main__":
    print("Starting PR Agent MCP server...")
    print("NOTE: Run webhook_server.py in a separate terminal to receive GitHub events")
    mcp.run()
