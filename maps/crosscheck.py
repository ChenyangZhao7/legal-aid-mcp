from __future__ import annotations

import re
from difflib import SequenceMatcher

from coord import haversine_m
from maps.base import Place

_PREFIXES = ("中华人民共和国", "山东省", "济南市")
_PUNCT = re.compile(r"[\s（）()\[\]【】·,，。.;；:：、\-—_]+")


def normalize_name(name: str | None) -> str:
    value = _PUNCT.sub("", name or "")
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            if value.startswith(prefix):
                value = value[len(prefix) :]
                changed = True
    return value


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def name_similarity(a: str | None, b: str | None) -> float:
    return _similarity(normalize_name(a), normalize_name(b))


def _normalize_phone(phone: str | None) -> str:
    return re.sub(r"[^\d]", "", phone or "")


def _point(payload: dict) -> tuple[float, float]:
    return float(payload["lng"]), float(payload["lat"])


def _distance_between(a: dict, b: dict) -> float:
    return haversine_m(_point(a), _point(b))


def match_places(a: Place, b: Place) -> bool:
    name_ok = name_similarity(a.name, b.name) >= 0.8
    na, nb = normalize_name(a.name), normalize_name(b.name)
    if na and nb and (na in nb or nb in na) and min(len(na), len(nb)) >= 3:
        name_ok = True
    if not name_ok:
        return False

    distance = haversine_m((a.point.lng, a.point.lat), (b.point.lng, b.point.lat))
    if distance <= 500:
        return True
    return _similarity(a.address or "", b.address or "") >= 0.5


def place_confidence(sources: list[dict]) -> str:
    if len(sources) < 2:
        return "low"
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            a, b = sources[i], sources[j]
            if name_similarity(a.get("name"), b.get("name")) < 0.5:
                return "conflict"
            distance = _distance_between(a, b)
            if distance > 1000:
                return "conflict"

    names_ok = all(
        name_similarity(sources[0].get("name"), item.get("name")) >= 0.8
        for item in sources[1:]
    )
    location_ok = all(
        _distance_between(sources[0], item) <= 500
        or _similarity(sources[0].get("address") or "", item.get("address") or "") >= 0.5
        for item in sources[1:]
    )
    if not (names_ok and location_ok):
        return "low"

    phones = [_normalize_phone(item.get("telephone")) for item in sources]
    phones = [phone for phone in phones if phone]
    if phones and len(set(phones)) > 1:
        return "medium"
    if len(phones) == len(sources):
        return "high"
    return "medium"


def place_discrepancies(sources: list[dict]) -> list[str]:
    issues: list[str] = []
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            a, b = sources[i], sources[j]
            pa = a.get("provider", f"源{i + 1}")
            pb = b.get("provider", f"源{j + 1}")
            if name_similarity(a.get("name"), b.get("name")) < 0.8:
                issues.append(f"{pa} 与 {pb} 名称不同：{a.get('name')} / {b.get('name')}")
            if (
                a.get("address")
                and b.get("address")
                and _similarity(a["address"], b["address"]) < 0.5
            ):
                issues.append(f"{pa} 与 {pb} 地址不同：{a['address']} / {b['address']}")
            distance = _distance_between(a, b)
            if distance > 500:
                issues.append(f"{pa} 与 {pb} 坐标距离约 {round(distance)} 米")
            phone_a = _normalize_phone(a.get("telephone"))
            phone_b = _normalize_phone(b.get("telephone"))
            if phone_a and phone_b and phone_a != phone_b:
                issues.append(f"{pa} 与 {pb} 电话不同：{a['telephone']} / {b['telephone']}")
    return issues


def route_confidence(sources: list[dict]) -> str:
    if len(sources) < 2:
        return "low"
    base = sources[0]
    max_distance = 0.0
    max_duration = 0.0
    for item in sources[1:]:
        if base["distance_m"]:
            max_distance = max(
                max_distance,
                abs(item["distance_m"] - base["distance_m"]) / base["distance_m"],
            )
        if base["duration_s"]:
            max_duration = max(
                max_duration,
                abs(item["duration_s"] - base["duration_s"]) / base["duration_s"],
            )
    if max_distance <= 0.15 and max_duration <= 0.30:
        return "high"
    if max_distance <= 0.30:
        return "medium"
    return "low"


def route_discrepancies(sources: list[dict]) -> list[str]:
    if len(sources) < 2:
        return []
    base = sources[0]
    issues: list[str] = []
    for item in sources[1:]:
        if base["distance_m"] and item["distance_m"]:
            diff = abs(item["distance_m"] - base["distance_m"]) / base["distance_m"]
            if diff > 0.15:
                issues.append(
                    f"{base.get('provider')} 与 {item.get('provider')} 距离相差 {round(diff * 100)}%"
                )
        if base["duration_s"] and item["duration_s"]:
            diff = abs(item["duration_s"] - base["duration_s"]) / base["duration_s"]
            if diff > 0.30:
                issues.append(
                    f"{base.get('provider')} 与 {item.get('provider')} 时间相差 {round(diff * 100)}%"
                )
    return issues
