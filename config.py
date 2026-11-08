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
    tencent_map_key: str | None = None
    tianditu_key: str | None = None
    map_providers: tuple[str, ...] = ("baidu", "tencent", "tianditu")
    map_cross_check: bool = True
    map_live_failure_mode: str = "cache"
    tencent_budget: int = 20
    tianditu_budget: int = 20
    legal_aid_live: bool = True
    legal_aid_cache_hours: int = 24
    division_cache_days: int = 30
    holiday_api: str = "https://timor.tech/api/holiday"
    holiday_live: bool = True
    holiday_cache_days: int = 30


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} 必须是整数，当前值：{value!r}")


def _as_float(name: str, value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} 必须是数字，当前值：{value!r}")


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
    tencent_map_key = (env.get("TENCENT_MAP_KEY") or "").strip() or None
    tianditu_key = (env.get("TIANDITU_KEY") or "").strip() or None

    if use_live and not baidu_ak:
        raise ConfigError("USE_LIVE=1 需要设置 BAIDU_AK")
    if not use_live and not use_mock:
        raise ConfigError("USE_MOCK=0 且 USE_LIVE=0：至少启用 mock 或 live")
    if use_live and use_mock:
        print("warning: USE_LIVE=1 优先于 USE_MOCK=1，将进行真实调用", file=sys.stderr)

    providers = tuple(
        item.strip()
        for item in (env.get("MAP_PROVIDERS") or "baidu,tencent,tianditu").split(",")
        if item.strip()
    )
    failure_mode = (env.get("MAP_LIVE_FAILURE_MODE") or "cache").strip().lower()
    if failure_mode not in {"cache", "error", "fixtures"}:
        raise ConfigError(
            "MAP_LIVE_FAILURE_MODE 必须是 cache、error 或 fixtures，"
            f"当前值：{failure_mode!r}"
        )

    return Settings(
        base_dir=base,
        baidu_ak=baidu_ak,
        use_mock=use_mock,
        use_live=use_live,
        live_budget=_as_int("LIVE_BUDGET", env.get("LIVE_BUDGET"), 20),
        cache_dir=_resolve(base, env.get("CACHE_DIR"), "cache"),
        cache_ttl_hours=_as_int("CACHE_TTL_HOURS", env.get("CACHE_TTL_HOURS"), 24),
        law_data_dir=_resolve(base, env.get("LAW_DATA_DIR"), "data/laws"),
        fixtures_dir=_resolve(base, env.get("FIXTURES_DIR"), "fixtures/baidu"),
        request_timeout_s=_as_float("REQUEST_TIMEOUT_S", env.get("REQUEST_TIMEOUT_S"), 10.0),
        tencent_map_key=tencent_map_key,
        tianditu_key=tianditu_key,
        map_providers=providers,
        map_cross_check=_as_bool(env.get("MAP_CROSS_CHECK"), True),
        map_live_failure_mode=failure_mode,
        tencent_budget=_as_int("TENCENT_BUDGET", env.get("TENCENT_BUDGET"), 20),
        tianditu_budget=_as_int("TIANDITU_BUDGET", env.get("TIANDITU_BUDGET"), 20),
        legal_aid_live=_as_bool(env.get("LEGAL_AID_LIVE"), True),
        legal_aid_cache_hours=_as_int(
            "LEGAL_AID_CACHE_HOURS", env.get("LEGAL_AID_CACHE_HOURS"), 24
        ),
        division_cache_days=_as_int(
            "DIVISION_CACHE_DAYS", env.get("DIVISION_CACHE_DAYS"), 30
        ),
        holiday_api=(env.get("HOLIDAY_API") or "https://timor.tech/api/holiday"),
        holiday_live=_as_bool(env.get("HOLIDAY_LIVE"), True),
        holiday_cache_days=_as_int(
            "HOLIDAY_CACHE_DAYS", env.get("HOLIDAY_CACHE_DAYS"), 30
        ),
    )
