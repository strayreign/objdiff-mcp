#!/usr/bin/env python3
"""
objdiff_mcp.py — MCP server wrapping objdiff-cli for decompilation projects.

Tools exposed:
  check_match(unit_name)   → fuzzy match % for a specific unit
  generate_report()        → regenerate full report.json and return summary
  list_incomplete()        → all units below 100%

Install deps:  pip install mcp
Run:           python3 objdiff_mcp.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:
    print("ERROR: mcp package not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ── Configuration ────────────────────────────────────────────────────────────
# By default the server assumes it lives inside the project repo and that
# objdiff-cli was built to <project_root>/build/tools/objdiff-cli.
#
# Override with environment variables:
#   OBJDIFF_PROJECT_ROOT   — absolute path to your project root
#   OBJDIFF_CLI_PATH       — absolute path to the objdiff-cli binary
#   OBJDIFF_REPORT_PATH    — absolute path to report.json
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(
    os.environ.get("OBJDIFF_PROJECT_ROOT", Path(__file__).resolve().parent.parent)
)

OBJDIFF_CLI = Path(
    os.environ.get("OBJDIFF_CLI_PATH", PROJECT_ROOT / "build" / "tools" / "objdiff-cli")
)

REPORT_JSON = Path(
    os.environ.get("OBJDIFF_REPORT_PATH", PROJECT_ROOT / "build" / "report.json")
)

server = Server("objdiff-mcp")


def _regen_report() -> dict:
    result = subprocess.run(
        [str(OBJDIFF_CLI), "report", "generate", "-o", str(REPORT_JSON)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"objdiff-cli failed: {result.stderr[:500]}")
    with open(REPORT_JSON) as f:
        return json.load(f)


def _read_report() -> dict:
    if not REPORT_JSON.exists():
        raise FileNotFoundError(
            f"report.json not found at {REPORT_JSON}. "
            "Run generate_report first, or set OBJDIFF_REPORT_PATH."
        )
    with open(REPORT_JSON) as f:
        return json.load(f)


def _resolve_unit_name(unit_arg: str, report: dict) -> str | None:
    """Try to find a unit by exact name, then by suffix match."""
    units = report.get("units", [])
    # Exact match first
    for unit in units:
        if unit["name"] == unit_arg:
            return unit["name"]
    # Suffix match (e.g. user passes 'foo' and unit is 'main/foo')
    for unit in units:
        if unit["name"].endswith("/" + unit_arg) or unit["name"].endswith(unit_arg):
            return unit["name"]
    return None


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="check_match",
            description=(
                "Return the fuzzy match percentage for a single unit. "
                "Reads the existing report.json (fast — no rebuild). "
                "Accepts a full unit name or a suffix, e.g. 'src/main.c' or just 'main.c'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "unit_name": {
                        "type": "string",
                        "description": "Full or partial unit name to look up",
                    },
                },
                "required": ["unit_name"],
            },
        ),
        Tool(
            name="generate_report",
            description=(
                "Re-run objdiff-cli report generate to refresh report.json, "
                "then return a summary of all incomplete units."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_incomplete",
            description=(
                "List all units below 100% fuzzy match from the current report.json. "
                "Optionally filter to only units at or above min_pct."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "min_pct": {
                        "type": "number",
                        "description": "Only include units at or above this % (default 0)",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "check_match":
        unit_arg = arguments["unit_name"]
        report = _read_report()
        full_name = _resolve_unit_name(unit_arg, report)
        if full_name is None:
            return [TextContent(type="text", text=f"Unit '{unit_arg}' not found in report.json")]
        for unit in report.get("units", []):
            if unit["name"] == full_name:
                m = unit.get("measures", {})
                pct = m.get("fuzzy_match_percent", 0.0)
                funcs = unit.get("functions", [])
                fn_lines = [
                    f"  {fn.get('name', '?')}: {fn.get('fuzzy_match_percent', 'N/A')}%"
                    for fn in funcs
                ]
                text = (
                    f"Unit: {unit['name']}\n"
                    f"Fuzzy match: {pct:.2f}%\n"
                    + ("\n".join(fn_lines) if fn_lines else "  (no function data)")
                )
                return [TextContent(type="text", text=text)]

    elif name == "generate_report":
        report = _regen_report()
        incomplete = [
            (unit["name"], unit.get("measures", {}).get("fuzzy_match_percent", 100.0))
            for unit in report.get("units", [])
            if unit.get("measures", {}).get("fuzzy_match_percent", 100.0) < 100.0
        ]
        incomplete.sort(key=lambda x: -x[1])
        lines = [f"Report regenerated. {len(incomplete)} unit(s) below 100%:\n"]
        for uname, pct in incomplete:
            lines.append(f"  {uname}: {pct:.1f}%")
        if not incomplete:
            lines.append("  All units are at 100%! 🎉")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "list_incomplete":
        min_pct = float(arguments.get("min_pct", 0.0))
        report = _read_report()
        incomplete = [
            (unit["name"], unit.get("measures", {}).get("fuzzy_match_percent", 100.0))
            for unit in report.get("units", [])
            if min_pct <= unit.get("measures", {}).get("fuzzy_match_percent", 100.0) < 100.0
        ]
        incomplete.sort(key=lambda x: -x[1])
        lines = [f"{len(incomplete)} incomplete unit(s):\n"]
        for uname, pct in incomplete:
            lines.append(f"  {uname}: {pct:.1f}%")
        return [TextContent(type="text", text="\n".join(lines))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
