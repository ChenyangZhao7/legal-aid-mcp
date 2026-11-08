from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    re.compile(r"BAIDU_AK\s*=\s*([A-Za-z0-9]{20,})"),
    re.compile(r"AMAP_KEY\s*=\s*([A-Za-z0-9]{20,})"),
    re.compile(r"\bak\s*=\s*([A-Za-z0-9]{16,})"),
]
SKIP_SUFFIXES = {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".pyc"}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    return [ROOT / line for line in output.splitlines() if line]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1)
                if value.startswith("your-") or value in {"***", "test-ak"}:
                    continue
                findings.append(f"{path.relative_to(ROOT)}: {match.group(0)[:80]}")

    if findings:
        print("ERROR: tracked files contain possible secrets:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("OK: no secrets in tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
