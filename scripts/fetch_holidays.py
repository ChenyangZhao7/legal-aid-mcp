from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holidays import fetch_timor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取免费节假日 API 快照")
    parser.add_argument("--out", default="data/holidays")
    parser.add_argument("--years", default="2025,2026")
    args = parser.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    for text in args.years.split(","):
        year = int(text.strip())
        days = fetch_timor(year)
        path = out_dir / f"{year}.json"
        path.write_text(
            json.dumps(
                {
                    "year": year,
                    "source": "timor.tech",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "days": days,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {path} ({len(days)} 个日期)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
