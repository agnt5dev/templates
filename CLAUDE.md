# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repo is a **catalog of starter templates** for building durable AI workflows on the AGNT5 platform — not an application. Each template is a self-contained, runnable project that users clone via `agnt5 create --template <name>`. Changes here ship as tarballs to GitHub Releases and Cloudflare R2 (see `.github/workflows/release-templates.yml`).

The authoritative list of published templates is `templates.json` at the repo root. A template directory that is not listed there will not be released. When adding or renaming a template, update `templates.json` (name, category, capabilities, latest version) in the same change.

## Layout

- `python/<template-name>/`, `typescript/<template-name>/`, and `go/<template-name>/` — one directory per template per language. The release workflow tars each `<lang>/<template>` directory referenced in `templates.json`.
- `templates.json` — manifest. Drives both the release workflow and the CLI's template picker.
- `.github/workflows/release-templates.yml` — on push to `main` touching `python/**`, `typescript/**`, or `templates.json`, builds `{template}-{lang}-{version}.tar.gz` for every manifest entry, creates a dated GitHub Release, and syncs to R2 at `templates/{template}/{lang}/{version}.tar.gz` (plus `latest.tar.gz`). Excludes: `.venv`, `__pycache__`, `.git`, `.agnt5`, `*.pyc`, `.env`, `uv.lock`, `.ruff_cache`.

## Template anatomy (Python)

Every Python template follows the same shape. Match it when adding a new one:

- `agnt5.yaml` — service manifest: `name`, `language`, `language_version`, `environment`, `deploy.resources`. The CLI reads this.
- `app.py` — entry point. Creates an `agnt5.Worker(service_name=..., auto_register=True)` and calls `await worker.run()`. `auto_register=True` discovers all `@function`, `@workflow`, `@tool`, `@entity`, and `Agent` components from the package — do not register them manually.
- `pyproject.toml` — `requires-python = ">= 3.12"`, depends on `agnt5~=0.7.x`, hatchling build, `packages = ["src/<pkg>"]`.
- `src/<package>/` — the actual code. `__init__.py` re-exports workflows/functions so `auto_register` can find them via the package import.
- `README.md` — minimal: env setup, `agnt5 dev`, one `agnt5 run` example, link to docs.

## Template anatomy (Go)

Every Go template follows the same shape:

- `agnt5.yaml` — same manifest shape as Python/TypeScript, plus `worker: { command: "go run ." }` (Go, like TypeScript, needs an explicit worker command).
- `go.mod` — `module <template-name>`, `go 1.23`, `require agnt5.dev/sdk-go v0.2.0`. Never ship a `replace` directive — see verification note below.
- `main.go` — entry point. Creates an `agnt5.NewWorker(serviceName, opts...)` and calls `worker.Run(context.Background())`. **The Go SDK has no auto-register equivalent**: every function, workflow, agent, and tool must be registered explicitly via `agnt5.RegisterFunction`/`RegisterWorkflow`/`RegisterAgent`/`RegisterTool` in `main()`.
- Flat `package main` directory (mirrors the real `sdk/templates/go/go-quickstart` example) — one file per concern (`functions.go`, `workflows.go`, `agents.go`, `tools.go`, `models.go`) rather than a `src/<package>/` tree, since there's no package-import auto-discovery to support.
- `README.md` — same shape as the Python/TypeScript sibling, Setup section uses `go mod download` + `go run .`/`agnt5 dev`.
- No `go.sum` checksum for `agnt5.dev/sdk-go` itself is possible yet — its vanity import endpoint isn't publicly configured, so `go mod tidy` can't fetch it from the real module proxy. To verify a Go template compiles: temporarily add `replace agnt5.dev/sdk-go => <path-to-a-local-checkout-of-sdk-go>` to `go.mod`, run `go build ./...`/`go vet ./...`, regenerate `go.sum` (it will contain only the indirect dependencies' checksums, none for `agnt5.dev/sdk-go` itself — that's expected), then **remove the `replace` line** before committing. This matches how the real `go-quickstart` example's own `go.mod`/`go.sum` were produced.
- Known Go SDK gaps to design around (do not silently paper over them): no `ctx.parallel()`/fan-out helper (wrap goroutines in one `agnt5.Step`), no structured-output/`response_format` field on `GenerateRequest` (prompt for JSON + `json.Unmarshal`, or a schema-locked tool call), no named sandbox providers (only `InMemorySandbox`/`HTTPSandbox`, and `HTTPSandbox` speaks AGNT5's own protocol, not a third-party provider's), `NewAgent` defaults `MaxTurns` to `1` (always raise it when a template's agent has tools), and model constructors need `APIKey` passed explicitly (no env-var auto-pickup).

## AGNT5 programming model (what to preserve when editing templates)

Templates are pedagogical — they demonstrate idiomatic durable-workflow patterns. Don't "clean up" code that looks redundant; the structure is usually load-bearing.

- **Durability requires `context=ctx`** on every model/agent call inside a `@workflow`. Without it, every LLM call replays from scratch on retry. See `python/quickstart/src/agnt5_quickstart/workflows.py:58`.
- **Side effects go through `ctx.step(...)`** so they're checkpointed once and skipped on replay. Direct I/O inside a `@workflow` body breaks replay determinism.
- **MCP tools are discovered after `await mcp.connect()`** inside the workflow, not at import time, so the discovered tool list is part of the run's recorded state.
- **Human-in-the-loop** uses `await ctx.wait_for_user(...)` with `input_type` of `text` / `approval` / `select` / `multiselect`. The workflow is not in process memory while waiting — it resumes on a different host.
- **Mock mode**: templates that call external APIs should support `AGNT5_MOCK_MODE=1` and produce a deterministic stub (see `canned_brief` in quickstart) so users can run without API keys.

## Working with templates

These commands run **inside a template directory** (e.g., `python/quickstart/`), not at the repo root. The repo root has no build/test/lint of its own.

```bash
# Start the AGNT5 local platform (dashboard at http://localhost:34180)
agnt5 dev up           # or: agnt5 dev (some templates)

# Run a workflow by its registered name
agnt5 run <workflow-name> --input '{"key": "value"}'

# Run the worker directly (alternative to agnt5 dev)
uv run python app.py
```

Dev dependencies are usually `pytest` + `pytest-asyncio` declared in `[dependency-groups].dev`. Run with `uv run pytest` from the template dir. Not every template has tests — check before assuming.

## Versioning a template

Bump `version` in the template's `pyproject.toml` AND `templates.json` `languages.<lang>.latest` (and append to `versions`) in the same commit. The release workflow tags releases by date (`templates-YYYYMMDD-HHMMSS`), but the published artifact is named by the manifest version: `{template}-{lang}-{version}.tar.gz`.

## Adding a new template

1. Create `python/<name>/` (or `typescript/<name>/`) following the anatomy above.
2. Add an entry to `templates.json` with title, description, category, capabilities, and `languages.<lang>.latest`.
3. Verify it runs locally with `agnt5 dev` + `agnt5 run`.
4. Merging to `main` triggers the release workflow automatically.
