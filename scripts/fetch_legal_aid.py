from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from divisions import DivisionIndex  # noqa: E402
from errors import ToolError  # noqa: E402
from legal_aid import fetch_centers  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取 12348 济南法律援助中心快照")
    parser.add_argument("--divisions", default="data/divisions/jinan.json")
    parser.add_argument("--out", default="data/legal_aid/jinan.json")
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args()

    divisions = DivisionIndex.load(ROOT / args.divisions)
    districts = divisions.districts()
    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "12348.gov.cn",
        "districts": {},
    }
    failed = 0
    for node in districts:
        code6 = node.code[:6]
        try:
            centers = fetch_centers(code6)
            status = "ok" if centers else "empty"
            print(f"{node.name} ({code6}): {len(centers)} 条")
        except ToolError as exc:
            failed += 1
            status = "failed"
            centers = []
            print(f"WARN: {node.name} ({code6}) 查询失败：{exc.message}")
        result["districts"][code6] = {
            "name": node.name,
            "status": status,
            "centers": [asdict(center) for center in centers],
        }
        time.sleep(args.sleep)

    if failed == len(districts):
        print("ERROR: 所有区县都查询失败，不写快照", file=sys.stderr)
        return 1

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}（failed={failed}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
