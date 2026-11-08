from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import urlencode

import httpx

from config import Settings
from errors import ToolError

BASE = "https://api.map.baidu.com"

_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}


def _thread_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Serialize read-modify-write across threads and processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with _thread_lock(lock_path):
        with lock_path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                handle.write(b"\0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class BudgetStore:
    def __init__(
        self,
        path: Path,
        limit: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self.limit = limit
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _read(self) -> dict:
        if not self.path.exists():
            return {"used": 0, "limit": self.limit}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raise ToolError(
                "BUDGET_EXHAUSTED",
                f"预算文件损坏或不可读：{self.path}；为避免超额调用，已停止真实请求",
            )

    def check_and_increment(self) -> None:
        with _file_lock(self.path):
            data = self._read()
            used = int(data.get("used", 0))
            if used >= self.limit:
                raise ToolError(
                    "BUDGET_EXHAUSTED",
                    "真实调用额度已用完，本次请求未发送；请改用缓存/样本或调高 LIVE_BUDGET",
                )
            data["used"] = used + 1
            data["limit"] = self.limit
            data["updated_at"] = self.now().isoformat()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            temp.replace(self.path)


class CacheStore:
    def __init__(
        self,
        directory: Path,
        ttl_hours: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.directory = directory
        self.ttl_hours = ttl_hours
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(payload["fetched_at"])
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if self.now() - fetched > timedelta(hours=self.ttl_hours):
            return None
        return payload.get("data")

    def set(self, key: str, data: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": self.now().isoformat(), "data": data}
        self._path(key).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


class BaiduClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.cache = CacheStore(settings.cache_dir, settings.cache_ttl_hours, self.now)
        self.budget = BudgetStore(
            settings.cache_dir / "budget.json",
            settings.live_budget,
            self.now,
        )

    def _fixture(self, name: str) -> dict:
        path = self.settings.fixtures_dir / name
        if not path.exists():
            raise ToolError("NO_RESULTS", f"没有可用的样本：{name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _cache_key(self, path: str, params: dict) -> str:
        stable = {k: v for k, v in params.items() if k != "ak"}
        raw = path + "?" + urlencode(sorted(stable.items()))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _live_get(self, path: str, params: dict) -> dict:
        request_params = {**params, "output": "json", "ak": self.settings.baidu_ak}
        key = self._cache_key(path, request_params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        self.budget.check_and_increment()
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.settings.request_timeout_s,
            ) as client:
                response = client.get(BASE + path, params=request_params)
                response.raise_for_status()
        except httpx.TimeoutException:
            raise ToolError("UPSTREAM_TIMEOUT", "地图服务超时，请稍后重试")
        except httpx.HTTPError:
            raise ToolError("UPSTREAM_ERROR", "地图服务请求失败，请稍后重试")

        try:
            data = response.json()
        except ValueError:
            raise ToolError(
                "UPSTREAM_ERROR",
                "地图服务返回了非 JSON 响应，请稍后重试",
            )
        if not isinstance(data, dict):
            raise ToolError("UPSTREAM_ERROR", "地图服务返回格式异常，请稍后重试")

        try:
            status = int(data.get("status", -1))
        except (TypeError, ValueError):
            status = -1
        if status != 0:
            message = data.get("message") or ""
            if self.settings.baidu_ak:
                message = message.replace(self.settings.baidu_ak, "***")
            message = re.sub(r"ak=[^&\s]+", "ak=***", message)
            if status in {203, 210, 211, 302}:
                raise ToolError(
                    "AK_INVALID",
                    f"百度地图 AK 权限不足（status={status}）：{message}",
                )
            if status == 220:
                raise ToolError(
                    "QUOTA_EXCEEDED",
                    f"百度地图配额已用尽（status={status}）：{message}",
                )
            raise ToolError(
                "UPSTREAM_ERROR",
                f"百度地图返回错误（status={status}）：{message}",
            )

        self.cache.set(key, data)
        return data

    def place_search(self, query: str, region: str, page_size: int) -> list[dict]:
        if not self.settings.use_live:
            normalized = region.replace("济南市", "济南")
            if query in {"人民法院", "法院"}:
                name = (
                    "place_court_lixia.json"
                    if normalized in {"历下区", "济南历下区"}
                    else "place_court.json"
                )
            elif query == "律师事务所":
                name = "place_law_firm.json"
            elif query in {"法律援助", "法律援助中心"}:
                name = "place_legal_aid.json"
            else:
                raise ToolError("NO_RESULTS", f"没有可用的样本：{query}")
            return self._fixture(name).get("results") or []

        data = self._live_get(
            "/place/v2/search",
            {
                "query": query,
                "region": region,
                "scope": 2,
                "page_size": page_size,
            },
        )
        return data.get("results") or []

    def geocode(self, address: str) -> tuple[float, float]:
        if not self.settings.use_live:
            if "中级人民法院" in address:
                name = "geocode_court.json"
            elif "西站" in address:
                name = "geocode_west_station.json"
            else:
                raise ToolError("GEOCODE_FAILED", f"没有可用的样本：{address}")
            data = self._fixture(name)
        else:
            data = self._live_get("/geocoding/v3/", {"address": address})

        try:
            location = data["result"]["location"]
            return float(location["lng"]), float(location["lat"])
        except (KeyError, TypeError, ValueError):
            raise ToolError("GEOCODE_FAILED", f"无法解析地址：{address}")

    def route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        mode: str,
    ) -> dict:
        if not self.settings.use_live:
            data = self._fixture("route_west_station.json")
        else:
            data = self._live_get(
                f"/direction/v2/{mode}",
                {
                    "origin": f"{origin[0]},{origin[1]}",
                    "destination": f"{destination[0]},{destination[1]}",
                },
            )

        try:
            route = data["result"]["routes"][0]
            steps = []
            for step in route.get("steps", []):
                road_name = step.get("road_name") or ""
                instruction = step.get("instruction") or (
                    f"沿{road_name}" if road_name else "继续行驶"
                )
                steps.append(
                    {
                        "instruction": instruction,
                        "road_name": road_name,
                        "distance_m": int(step.get("distance", 0)),
                        "duration_s": int(step.get("duration", 0)),
                    }
                )
            return {
                "distance_m": int(route["distance"]),
                "duration_s": int(route["duration"]),
                "steps": steps,
            }
        except (KeyError, IndexError, TypeError, ValueError):
            raise ToolError("NO_ROUTE", "未找到可用路线，请检查起点和终点")
