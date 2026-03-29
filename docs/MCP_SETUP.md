# MCP Setup — Cursor & Antigravity

Gauntlet works as an MCP server inside any MCP-compatible IDE.
Once connected, type `find` in the chat and Gauntlet handles the rest.

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

Gauntlet scans your workspace recursively, detects agent files, and returns a numbered list:

```
Found 2 agent files in your workspace:

1. agents/classifier_agent.py
   - Provider: anthropic
   - Model: claude-sonnet-4-20250514
   - System prompt: You are a support ticket classifier...

2. agents/summary_agent.py
   - Provider: openai
   - Model: gpt-4o
   - System prompt: You are a news summariser...

To run Gauntlet, reply with:
Run Gauntlet on file 1
Goal: [what this agent does]
API key: sk-ant-...
```

Reply and Gauntlet runs the full eval inline — no terminal, no JSON, no manual work.

---

## Available MCP tools

| Tool | Trigger | What it does |
|---|---|---|
| `gauntlet_find_agents` | Type `find` | Scans workspace for agent files automatically |
| `gauntlet_eval_file` | Paste agent code | Extracts system prompt and runs eval |
| `gauntlet_eval_prompt` | Provide model + prompt manually | Runs eval without needing a file |

---

## Troubleshooting

**Green dot not showing in Cursor**
Make sure `gauntlet-eval` is installed in the same Python that Cursor uses. Run `where python` in CMD to check.

**API key error on eval**
The `ANTHROPIC_API_KEY` in the MCP config is Gauntlet's own key for running the judges. Your agent's API key is passed separately when you run the eval.

**`find` returns no agents**
Gauntlet looks for `system_prompt`, `SYSTEM_PROMPT`, `system=` arguments, or `{"role": "system"}` dicts. Make sure your agent file uses one of these patterns.
