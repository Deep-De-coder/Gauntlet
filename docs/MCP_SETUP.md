# MCP Setup — Cursor & Antigravity

Gauntlet works as an MCP server inside any MCP-compatible IDE.
Once connected, type `find gauntlet` in the chat and Gauntlet handles the rest.

---

## Installation

```bash
pip install gauntlet-eval
```

No cloning required. The `gauntlet` command and MCP server are available immediately after install.

---

## Cursor setup

1. Open your Cursor MCP config file:
   ```
   %APPDATA%\Cursor\User\globalStorage\cursor.mcp\config.json
   ```

2. Add this block (replace `your-key-here` with your Anthropic API key):
   ```json
   {
     "mcpServers": {
       "gauntlet": {
         "command": "python",
         "args": ["-m", "gauntlet.mcp_server"],
         "env": {
           "ANTHROPIC_API_KEY": "your-key-here"
         }
       }
     }
   }
   ```

3. Restart Cursor. You should see `gauntlet` with a green dot under Settings → MCP.

---

## Antigravity setup

1. Go to **Settings → MCP Servers → Add Server**
2. Paste the same JSON config above
3. Restart the MCP connection

---

## Using it

With any project open, type in the chat:

```
find gauntlet
```

Gauntlet scans your workspace recursively, detects agent files, and returns a table with the goal auto-detected from each file:

```
Gauntlet found 3 agent files in your workspace:

| # | File                        | Goal                              | Provider   | Model                    |
|---|-----------------------------|-----------------------------------|------------|--------------------------|
| 1 | agents/classifier_agent.py  | Classify support tickets          | anthropic  | claude-sonnet-4-20250514 |
| 2 | agents/summary_agent.py     | Summarise news articles           | openai     | gpt-4o                   |
| 3 | tools/llm.py                | Route prompts to correct provider | anthropic  | claude-sonnet-4-20250514 |

To run Gauntlet on one of them, just say:
Run Gauntlet on file [NUMBER]
```

Reply with the number — no API key needed, Gauntlet uses the key from your MCP config automatically.

---

## Available MCP tools

| Tool | Trigger | What it does |
|---|---|---|
| `gauntlet_find_agents` | `find gauntlet` | Scans workspace, detects agents, shows goal + model |
| `gauntlet_eval_file` | Paste agent code | Extracts system prompt and runs eval |
| `gauntlet_eval_prompt` | Provide model + prompt manually | Runs eval without needing a file |

---

## Troubleshooting

**Green dot not showing in Cursor**
Make sure `gauntlet-eval` is installed in the same Python that Cursor uses. Run `where python` in CMD to check.

**API key error on eval**
The `ANTHROPIC_API_KEY` in the MCP config is Gauntlet's own key for running the judges. Your agent's API key is only needed if you want to test a specific model directly via `gauntlet_eval_prompt`.

**`find` returns no agents**
Gauntlet looks for `system_prompt`, `SYSTEM_PROMPT`, `system=` arguments, or `{"role": "system"}` dicts. Make sure your agent file uses one of these patterns.

**Goal shows as "Agent: filename" instead of a real description**
Add a module-level docstring to your agent file. Gauntlet reads it automatically:
```python
"""Routes LLM prompts to the correct backend provider."""

import anthropic
...
```