from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlencode

import httpx

from baidu import BudgetStore, CacheStore
from config import Settings
from errors import ToolError

_REDACTED_PARAMS = {"ak", "key", "tk"}


class LiveJsonClient:
    """Small shared HTTP client with provider-scoped cache and budget."""

    def __init__(
        self,
        name: str,
        base_url: str,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        now: Callable[[], datetime] | None = None,
        budget_limit: int = 20,
        budget_path=None,
    ) -> None:
        self.name = name
        self.base_url = base_url
        self.settings = settings
        self.transport = transport
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.cache = CacheStore(settings.cache_dir, settings.cache_ttl_hours, self.now)
        if budget_path is None:
            budget_path = settings.cache_dir / f"budget_{name}.json"
        self.budget = BudgetStore(budget_path, budget_limit, self.now)

    def _cache_key(self, path: str, params: dict) -> str:
        stable = {k: v for k, v in params.items() if k not in _REDACTED_PARAMS}
        raw = f"{self.name}:{path}?{urlencode(sorted(stable.items()))}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, path: str, params: dict) -> dict:
        key = self._cache_key(path, params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        self.budget.check_and_increment()
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.settings.request_timeout_s,
            ) as client:
                response = client.get(self.base_url + path, params=params)
                response.raise_for_status()
        except httpx.TimeoutException:
            raise ToolError("UPSTREAM_TIMEOUT", "地图服务超时，请稍后重试")
        except httpx.HTTPError:
            raise ToolError("UPSTREAM_ERROR", "地图服务请求失败，请稍后重试")

        try:
            data = response.json()
        except ValueError:
            raise ToolError("UPSTREAM_ERROR", "地图服务返回了非 JSON 响应，请稍后重试")
        if not isinstance(data, dict):
            raise ToolError("UPSTREAM_ERROR", "地图服务返回格式异常，请稍后重试")

        self.cache.set(key, data)
        return data
