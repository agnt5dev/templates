"""Demo-only helpers: the crash switch and the execution log.

None of this is needed in a real workflow. It exists so you can break the
worker on purpose and then *see* what replay skipped. Everything is written
under `.data/` in the project directory (override with ONBOARDING_DATA_DIR).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def data_dir() -> Path:
    path = Path(os.getenv("ONBOARDING_DATA_DIR", Path.cwd() / ".data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def mock_mode() -> bool:
    # `agnt5 dev` doesn't pass AGNT5_* variables from .env to the worker, so .env
    # uses ONBOARDING_MOCK_MODE. AGNT5_MOCK_MODE still works when exported in the shell.
    flags = (os.getenv("ONBOARDING_MOCK_MODE", ""), os.getenv("AGNT5_MOCK_MODE", ""))
    return any(flag.lower() in ("1", "true", "yes") for flag in flags)


def log_execution(run_id: str, step: str, item: str = "", attempt: int = 0) -> None:
    """Append one line each time a step's code *actually runs*.

    A replayed step returns its checkpointed result without running its code,
    so it never reaches this call. After a crash, the log shows which work was
    redone and which was not.
    """
    entry = {"run_id": run_id, "step": step, "item": item, "attempt": attempt, "ts": time.time()}
    with (data_dir() / "execution_log.jsonl").open("a") as f:
        f.write(json.dumps(entry) + "\n")


def read_execution_log(run_id: str) -> list[dict]:
    path = data_dir() / "execution_log.jsonl"
    if not path.exists():
        return []
    entries = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [e for e in entries if e["run_id"] == run_id]


def maybe_crash(run_id: str, crash_at: str | None, point: str) -> None:
    """Kill the worker process at `point`, once per run.

    The marker file makes the crash fire only on the first pass. When the run
    is replayed on a fresh worker, it sails past this point and finishes.
    `os._exit` skips all cleanup, like a power cut or an OOM kill.
    """
    if crash_at != point:
        return
    marker = data_dir() / "crashes" / f"{run_id}-{point}"
    if marker.exists():
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    print(f"💥 Simulated crash at '{point}' (run {run_id}). Restart the worker to resume.", flush=True)
    os._exit(1)


async def crash_point(ctx, crash_at: str | None, point: str) -> None:
    """Workflow-body version of `maybe_crash` that also survives a fresh filesystem.

    The crash point is itself a checkpointed step. Its code runs the first time
    the workflow reaches it, and that is the only time the worker is killed. On
    replay the step returns from its checkpoint without running, so the run
    continues even on a new container where `.data/` is empty.
    """
    if crash_at != point:
        return
    first_pass = False

    async def arm() -> str:
        nonlocal first_pass
        first_pass = True
        return point

    await ctx.step(f"crash_point_{point}", arm)
    if first_pass:
        maybe_crash(ctx.run_id, crash_at, point)


def approved(answer: str | None) -> bool:
    """Studio answers an approval with "approved"; the API takes the option id "approve"."""
    return (answer or "").strip().lower() in ("approve", "approved")
