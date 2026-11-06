from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import load_settings  # noqa: E402

BASE = "https://api.map.baidu.com"


def _get(ak: str, path: str, params: dict) -> dict:
    query = {**params, "output": "json", "ak": ak}
    url = BASE + path + "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _checked(data: dict, label: str) -> dict:
    if data.get("status") != 0:
        raise RuntimeError(f"{label} 失败: status={data.get('status')} message={data.get('message')}")
    return data


def place(ak: str, query: str, region: str, page_size: int = 5) -> dict:
    return _checked(
        _get(
            ak,
            "/place/v2/search",
            {"query": query, "region": region, "scope": 2, "page_size": page_size},
        ),
        f"place({query}, {region})",
    )


def geocode(ak: str, address: str) -> dict:
    return _checked(_get(ak, "/geocoding/v3/", {"address": address}), f"geocode({address})")


def driving(ak: str, origin: str, destination: str) -> dict:
    return _checked(
        _get(ak, "/direction/v2/driving", {"origin": origin, "destination": destination}),
        "driving",
    )


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="录制百度地图样本")
    parser.add_argument("--out", default="fixtures/baidu")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.baidu_ak:
        print("ERROR: 需要 BAIDU_AK")
        return 1
    ak = settings.baidu_ak
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    court = place(ak, "法院", "济南", 10)
    write_json(out_dir / "place_court.json", court)
    print(f"place_court: {len(court.get('results') or [])} 条")

    lixia = place(ak, "人民法院", "历下区", 5)
    names = [item.get("name", "") for item in lixia.get("results") or []]
    if not any("历下区人民法院" in name for name in names):
        lixia = place(ak, "历下区人民法院", "济南", 5)
        names = [item.get("name", "") for item in lixia.get("results") or []]
    if not any("历下区人民法院" in name for name in names):
        print(f"ERROR: 没有找到历下区人民法院，实际结果: {names}")
        return 1
    write_json(out_dir / "place_court_lixia.json", lixia)
    print(f"place_court_lixia: {len(lixia.get('results') or [])} 条")

    law_firm = place(ak, "律师事务所", "济南", 5)
    write_json(out_dir / "place_law_firm.json", law_firm)
    print(f"place_law_firm: {len(law_firm.get('results') or [])} 条")

    legal_aid = place(ak, "法律援助", "济南", 5)
    write_json(out_dir / "place_legal_aid.json", legal_aid)
    print(f"place_legal_aid: {len(legal_aid.get('results') or [])} 条")

    geo_court = geocode(ak, "济南市中级人民法院")
    write_json(out_dir / "geocode_court.json", geo_court)
    geo_west = geocode(ak, "济南西站")
    write_json(out_dir / "geocode_west_station.json", geo_west)

    court_loc = geo_court["result"]["location"]
    west_loc = geo_west["result"]["location"]
    origin = f"{west_loc['lat']},{west_loc['lng']}"
    destination = f"{court_loc['lat']},{court_loc['lng']}"
    route = driving(ak, origin, destination)
    write_json(out_dir / "route_west_station.json", route)
    distance = route["result"]["routes"][0]["distance"]
    print(f"route_west_station: {distance} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
