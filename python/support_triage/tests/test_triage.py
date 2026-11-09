"""Runs `triage_ticket` in-process, in mock mode, against the shared cases.

`tests/cases.json` is the same file the TypeScript template tests against, so
both languages are held to identical inputs and outputs.
"""
import json
import os
from pathlib import Path

import pytest

os.environ["MOCK_MODE"] = "1"

from agnt5 import WaitingForUserInputException  # noqa: E402

from agnt5_support_triage import triage_ticket  # noqa: E402

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
async def test_triage_ticket(case):
    if "expected_pause" in case:
        with pytest.raises(WaitingForUserInputException) as paused:
            await triage_ticket(**case["input"])
        assert paused.value.question == case["expected_pause"]
        return
    assert await triage_ticket(**case["input"]) == case["expected"]
