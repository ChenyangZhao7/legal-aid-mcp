from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    baidu_ak: str | None
    use_mock: bool
    use_live: bool
    live_budget: int
    cache_dir: Path
    cache_ttl_hours: int
    law_data_dir: Path
    fixtures_dir: Path
    request_timeout_s: float


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _resolve(base_dir: Path, value: str | None, default: str) -> Path:
    path = Path(value or default)
    return path if path.is_absolute() else base_dir / path


def load_settings(
    env: Mapping[str, str] | None = None,
    base_dir: Path | None = None,
) -> Settings:
    base = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    if env is None:
        load_dotenv(base / ".env")
        env = os.environ

    use_mock = _as_bool(env.get("USE_MOCK"), True)
    use_live = _as_bool(env.get("USE_LIVE"), False)
    baidu_ak = (env.get("BAIDU_AK") or "").strip() or None

    if use_live and not baidu_ak:
        raise ConfigError("USE_LIVE=1 需要设置 BAIDU_AK")
    if use_live and use_mock:
        print("warning: USE_LIVE=1 优先于 USE_MOCK=1，将进行真实调用", file=sys.stderr)

    return Settings(
        base_dir=base,
        baidu_ak=baidu_ak,
        use_mock=use_mock,
        use_live=use_live,
        live_budget=_as_int(env.get("LIVE_BUDGET"), 20),
        cache_dir=_resolve(base, env.get("CACHE_DIR"), "cache"),
        cache_ttl_hours=_as_int(env.get("CACHE_TTL_HOURS"), 24),
        law_data_dir=_resolve(base, env.get("LAW_DATA_DIR"), "data/laws"),
        fixtures_dir=_resolve(base, env.get("FIXTURES_DIR"), "fixtures/baidu"),
        request_timeout_s=float(env.get("REQUEST_TIMEOUT_S") or 10.0),
    )
