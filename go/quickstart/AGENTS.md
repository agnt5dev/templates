# Testing changes on AGNT5

This project runs on AGNT5. Test each change on your own **dev session**: a dev
deployment for the current git branch, so runs from other branches, worktrees
and agents never reach your code, and yours never reach theirs.

## Test a change

1. Start this branch's worker in the background. It reloads on file changes.

   ```bash
   agnt5 dev -d -o json
   ```

   It never prompts. Keep `data.studio_url` and `data.session.deployment_id`
   from the output. Running it again reports the worker that is already
   running.

2. Run a component against it:

   ```bash
   agnt5 run <function> --input '<json>'
   agnt5 run workflow <workflow> --input '<json>'    # also: tool, agent
   ```

   `agnt5 components --deployment <data.session.deployment_id>` lists what
   the worker registered; `agnt5 dev logs` shows its output.

3. End your final message to the human with `data.studio_url`. It opens Studio
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

`data.mcp_servers` lists the MCP servers this session publishes. The Go SDK
can call MCP servers but cannot publish one, so for this template the list
stays empty.
