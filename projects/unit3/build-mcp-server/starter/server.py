#!/usr/bin/env python3
"""
Module 1: Basic MCP Server - Starter Code
TODO: Implement tools for analyzing git changes and suggesting PR templates
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pr-agent")

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


@mcp.tool()
async def analyze_file_changes(base_branch: str = "main", include_diff: bool = True) -> str:
    """Get the full diff and list of changed files in the current git repository.

    Args:
        base_branch: Base branch to compare against (default: main)
        include_diff: Include the full diff content (default: true)
    """

    try:
        context = mcp.get_context()
        roots_result = await context.session.list_roots()
        working_dir = roots_result.roots[0].uri.path
    except Exception as e:
        print("Failed to get working directory from session roots:", e)
        working_dir = "."

    max_chars = 2000
    res = subprocess.run(["git", "diff"], capture_output=True, text=True, cwd=working_dir)
    if res.returncode == 0:
        if res.returncode == 0:
            diff_output = res.stdout.strip()
            truncated = diff_output[:max_chars]
            if len(diff_output) > max_chars:
                truncated += "\n...[truncated]"
            return json.dumps({"files_changed": truncated})
        return json.dumps({"files_changed": res.stdout})
    else:
        return json.dumps({
            "error": "Git command failed",
            "stderr": res.stderr.strip()
        })



@mcp.tool()
async def get_pr_templates() -> str:
    """List available PR templates with their content."""
    templates = {}
    for template in TEMPLATES_DIR.glob("*.md"):
        try:
            with open(template, "r") as f:
                content = f.read()
            templates[template.name] = content
        except Exception as e:
            return json.dumps({"error": f"Failed to read template {template.name}: {str(e)}"})
    return json.dumps(templates)


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """Let Claude analyze the changes and suggest the most appropriate PR template.

    Args:
        changes_summary: Your analysis of what the changes do
        change_type: The type of change you've identified (bug, feature, docs, refactor, test, etc.)
    """
    templates_response = await get_pr_templates()
    templates = json.loads(templates_response)

    template_file = change_type.lower() + ".md"  # Example: "bugfix.md", "feature.md", etc.
    # selected_template = templates.get(template_file,"feature.md") #per default returned feature.md
    selected_template = templates.get("feature.md")
    suggestion = {
        "recommended_template": template_file,
        "reasoning": f"Based on your analysis: '{changes_summary}', this appears to be a {change_type} change.",
        "template_content": selected_template,
        "usage_hint": "Claude can help you fill out this template based on the specific changes in your PR."
    }

    return json.dumps(suggestion, indent=2)


if __name__ == "__main__":
    mcp.run()
