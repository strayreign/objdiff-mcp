# objdiff-mcp

An [MCP](https://modelcontextprotocol.io) server that wraps [`objdiff-cli`](https://github.com/encounter/objdiff) so any MCP-compatible LLM can query decompilation progress directly.

[objdiff](https://github.com/encounter/objdiff) is a tool by [encounter](https://github.com/encounter) that compares compiled object files against a target binary to measure how closely your decompiled C/C++ code matches the original.

---

## Tools

| Tool | Description |
|------|-------------|
| `check_match` | Returns the fuzzy match % for a single unit. Reads the existing `report.json` (no rebuild). |
| `generate_report` | Reruns `objdiff-cli report generate`, refreshes `report.json`, and returns a summary of incomplete units. |
| `list_incomplete` | Lists all units below 100% from the current `report.json`, sorted by match %. Supports an optional `min_pct` filter. |

---

## Requirements

- Python 3.10+
- `objdiff-cli` built or downloaded for your project
- The `mcp` Python package: `pip install mcp`

---

## Setup

### 1. Place the script

Copy `objdiff_mcp.py` anywhere in your project.

### 2. Configure paths

The server infers your project root from where the script lives. Override with environment variables if needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `OBJDIFF_PROJECT_ROOT` | Parent of the script's directory | Root of your decomp project |
| `OBJDIFF_CLI_PATH` | `$PROJECT_ROOT/build/tools/objdiff-cli` | Path to the objdiff-cli binary |
| `OBJDIFF_REPORT_PATH` | `$PROJECT_ROOT/build/report.json` | Path to `report.json` |

### 3. Add to your MCP config

```json
{
  "mcpServers": {
    "objdiff": {
      "command": "python3",
      "args": ["/path/to/objdiff_mcp.py"],
      "env": {
        "OBJDIFF_REPORT_PATH": "/path/to/your/project/build/report.json"
      }
    }
  }
}
```

---

## Notes

- `check_match` accepts full unit names (`main/src/player.c`) or a suffix (`player.c`).
- The server communicates over stdio, no ports or background processes needed.

---

## Credits

Built on top of [objdiff](https://github.com/encounter/objdiff) by [encounter](https://github.com/encounter).

---

## License

MIT
