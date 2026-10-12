# Testing changes on AGNT5

This project runs on AGNT5. Test each change on your own **dev session**: a dev
deployment for the current git branch, so runs from other branches, worktrees
and agents never reach your code, and yours never reach theirs.

## Test a change

1. Start this branch's worker in the background. It reloads on file changes.

   ```bash
   agnt5 dev -d -o json
   ```

   It never prompts. Keep `data.studio_url`, `data.mcp_servers` and
   `data.session.deployment_id` from the output. Running it again reports the
   worker that is already running.

2. Run a component against it:

   ```bash
   agnt5 run lookup_order --input '{"order_id": "o-1001"}'
   agnt5 run workflow refund_order --input '{"order_id": "o-1002"}'
   agnt5 run workflow audit_orders --input '{"minutes": 1}'
   agnt5 run agent support_agent --input '{"message": "Where is order o-1003?"}'
   ```

   `agnt5 components --deployment <data.session.deployment_id>` lists what
   the worker registered; `agnt5 dev logs` shows its output.

3. Check the MCP server the way a client sees it:

   ```bash
   agnt5 mcp check support --dev
   ```

4. End your final message to the human with `data.studio_url`. It opens Studio
   on this session, so they can try the change themselves.

## Exit codes

- `3`: this branch's session is live in another checkout. Start a separate
  one with `agnt5 dev -d -o json --session <new-name>`, or take it over with
  `--replace`.
- `4`: not authenticated. In a cloud sandbox, set `AGNT5_API_KEY` to a
  personal API key; project service keys are refused.
- `5`: no project found. Set `AGNT5_PROJECT` to the project ref in
  `.agnt5/project-ref`.

`agnt5 dev stop` stops this checkout's worker.

## MCP

`src/agnt5_mcp_server/server.py` defines the `support` MCP server; `app.py`
imports it, which is what publishes it. `lookup_order` shows the order view,
built from `ui/` into the committed `src/agnt5_mcp_server/views/order.html`:
after changing `ui/`, run `cd ui && npm install && npm run build` and commit
the result. `audit_orders` is the long-running tool (`mode="background"`):
about 10 minutes by default, so pass `{"minutes": 1}` (1 to 30) when you only
need it to finish. `data.mcp_servers` lists each server
the session publishes with its dev `url`: only the developer who started the
session can sign in to it, with their AGNT5 account, so it is for a human's
MCP client, not for you. Connect one with
`agnt5 mcp connect support --dev --client claude-code`.
