# MCP server

An MCP server built from AGNT5 components: a function, a workflow and an agent,
published as tools that Claude, ChatGPT, Cursor, VS Code and Codex can call.
Clients sign in with AGNT5, and every tool call runs as a durable AGNT5 run you
can open in Studio.

| Tool | Component | What it shows |
|---|---|---|
| `lookup_order` | `fn` | A tool that answers right away, shown in its own view |
| `refund_order` | `workflow` | Durable multi-step work; a long call hands back a run handle |
| `audit_orders` | `workflow` | A 10-minute run with steps and progress, followed in the run card or with `get_run` |
| `ask_support` | `Agent` | An LLM with its own tools, behind one MCP tool |

## Files

```
app.ts                  worker entry point: imports the server
agnt5.yaml              project config: worker.command, mcp.servers
src/
  functions.ts          lookupOrder, issueRefund, auditOrder (sample data)
  workflows.ts          refundOrder, auditOrders
  agents.ts             supportAgent and its get_order tool
  server.ts             the "support" MCPServer
ui/                     the order view's source (Vite, vite-plugin-singlefile)
views/order.html        the built view, committed
test/server.test.ts     checks the published tools and the built view
```

A worker runs only the module graph of `worker.command` in `agnt5.yaml`, and
publishes the MCP servers defined in it, so `app.ts` imports `src/server.ts`.
Add a tool by writing the component and adding it to the server with
`addFunction`, `addWorkflow` or `addAgent`. Give functions and workflows an
input schema: it is what MCP clients see as the tool's arguments.

## The order view

Clients that render MCP Apps (ChatGPT, Claude, Cursor, VS Code) show
`lookup_order`'s result in the order view, your own UI. Clients that don't
read the result as text. A view is one self-contained HTML file: `ui/` builds
it with Vite and `vite-plugin-singlefile`, and `src/server.ts` ships it with
`support.addView('order', ...)` and shows it with `view: orderView`. The view
gets the tool's result (`structuredContent` and text) from the host through
`@modelcontextprotocol/ext-apps`, and makes no network requests of its own.

The built `views/order.html` is committed, so a deploy needs no UI build.
After changing `ui/`, rebuild it:

```bash
npm run build:views
```

A view can be up to 2 MB. Other tools without a view of their own show the
built-in AGNT5 run card while their run goes on.

## Run it

```bash
npm install
agnt5 dev
```

Once the worker registers, `agnt5 dev` prints the server's dev URL. Only you
can sign in to it. Connect Claude Code to it:

```bash
agnt5 mcp connect support --dev --client claude-code
```

Then in Claude Code run `/mcp`, choose `support` and sign in with AGNT5. Other
clients: `--client cursor`, `--client vscode` or `--client codex`.

The agent needs `OPENAI_API_KEY`: copy `.env.example` to `.env` and set it. The
functions and workflows need nothing.

## A long-running call

`audit_orders` audits every order for about 10 minutes (pass `minutes`, 1 to
30): one step per order and check, each preceded by a `ctx.progress` report
and followed by a durable `ctx.sleep`. `src/server.ts` publishes it with
`mode: 'background'`, so a call hands back a run handle at once, and the run
carries on without the client, through worker restarts.

- **Claude Code and Codex** read the handle as text and follow the run with
  the built-in `get_run` tool (`cancel_run` stops it). Ask "audit all orders
  for 2 minutes", then "how is the audit going?": each `get_run` shows the
  run's status, latest progress and, once it finishes, the flagged orders.
- **claude.ai, ChatGPT, Cursor and VS Code** render MCP Apps, so the call
  shows the built-in AGNT5 run card: live status, steps, a progress bar, the
  result and **Cancel run**. In claude.ai or ChatGPT, add the server's
  deployed URL (see below) as a custom connector and sign in with AGNT5.

## Deploy it

```bash
agnt5 secrets set --name OPENAI_API_KEY --type api_key   # for the agent
agnt5 deploy --env production
agnt5 mcp connect support --env production --client claude-code
```

`agnt5 deploy` prints the server's URL,
`https://api.agnt5.com/mcp/<project>/<env>/support`, and warns if a server
named in `agnt5.yaml` was not published. Studio shows it under
**Build → MCP Servers**, with its tools, keys and calls. If a client can't
connect, `agnt5 mcp check support --env production` probes the server the
way a client does and says which step fails.

## Test

```bash
npm test
npm run typecheck
```
