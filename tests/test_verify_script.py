import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_requires_raw(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_laws.py",
            "--data-dir",
            str(ROOT / "data" / "laws"),
            "--raw-dir",
            str(tmp_path),
            "--require-raw",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "raw" in (result.stdout + result.stderr).lower() or "不存在" in (result.stdout + result.stderr)
