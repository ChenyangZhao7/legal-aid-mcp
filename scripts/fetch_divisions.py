from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from divisions import DivisionIndex  # noqa: E402

BASE = "https://dmfw.mca.gov.cn/9095/xzqh/getList"


def fetch(code: str, max_level: int) -> dict:
    url = f"{BASE}?code={code}&maxLevel={max_level}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取济南市区县行政区划快照")
    parser.add_argument("--out", default="data/divisions/jinan.json")
    parser.add_argument("--code", default="370100000000")
    args = parser.parse_args()

    payload = fetch(args.code, 3)
    index = DivisionIndex.from_mca_payload(payload)
    districts = index.districts()
    if len(districts) != 12:
        print(f"ERROR: 期望 12 个区县，实际 {len(districts)} 个", file=sys.stderr)
        return 1

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": f"{BASE}?code={args.code}&maxLevel=3",
        "data": payload.get("data", payload),
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path} ({len(districts)} 个区县)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
