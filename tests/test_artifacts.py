import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_transcript_is_utf8_json():
    data = json.loads((ROOT / "docs" / "mcp-transcript.json").read_text(encoding="utf-8"))
    assert set(data["tools"]) == {
        "find_legal_service",
        "plan_route",
        "search_law",
        "verify_citation",
    }
    assert len(data["calls"]) == 4
