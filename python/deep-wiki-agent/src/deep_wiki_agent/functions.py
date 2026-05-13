from datetime import datetime, timezone
from pathlib import Path

from agnt5 import FunctionContext, function

REPORTS_DIR = Path(".agnt5/reports")


@function
async def save_report(ctx: FunctionContext, question: str, brief: str) -> dict:
    """Write the approved brief to disk and return its path."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = REPORTS_DIR / f"investigation-{stamp}.md"
    body = (
        f"# Investigation: {question}\n\n"
        f"_Saved {stamp} UTC_\n\n"
        f"{brief}\n"
    )
    path.write_text(body, encoding="utf-8")
    return {"path": str(path)}


def canned_brief(question: str) -> str:
    """Deterministic stub used when AGNT5_MOCK_MODE=1 is set."""
    return (
        f"Answer: (mock) Provisional answer to: {question}\n\n"
        "Evidence:\n- (mock) Citation A\n- (mock) Citation B\n\n"
        "Trade-offs:\n- (mock) Pro\n- (mock) Con\n\n"
        "Risks:\n- (mock) Risk\n\n"
        "Open questions:\n- (mock) Question\n"
    )
