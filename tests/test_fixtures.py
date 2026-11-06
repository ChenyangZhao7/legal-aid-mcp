import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "baidu"

def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

def test_all_fixtures_ok():
    for path in FIXTURES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["status"] == 0, path.name

def test_court_fixture_has_jinan_intermediate():
    names = [r["name"] for r in load("place_court.json")["results"]]
    assert any("济南市中级人民法院" in n for n in names)

def test_lixia_fixture_has_lixia_court():
    names = [r["name"] for r in load("place_court_lixia.json")["results"]]
    assert any("历下区人民法院" in n for n in names)

def test_law_firm_fixture_not_empty():
    assert load("place_law_firm.json")["results"]

def test_legal_aid_fixture_is_valid():
    data = load("place_legal_aid.json")
    assert data["status"] == 0
    assert isinstance(data.get("results"), list)

def test_route_fixture_has_distance():
    route = load("route_west_station.json")["result"]["routes"][0]
    assert route["distance"] > 0 and route["duration"] > 0
