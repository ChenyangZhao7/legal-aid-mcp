from pathlib import Path

import httpx

from config import load_settings
from divisions import DivisionIndex
from legal_aid import LegalAidClient, sign_payload

ROOT = Path(__file__).resolve().parents[1]


def settings(tmp_path, **env):
    base = {
        "USE_LIVE": "0",
        "USE_MOCK": "1",
        "CACHE_DIR": str(tmp_path / "cache"),
        "FIXTURES_DIR": str(ROOT / "fixtures" / "baidu"),
        "LAW_DATA_DIR": str(ROOT / "data" / "laws"),
    }
    base.update(env)
    return load_settings(env=base, base_dir=tmp_path)


def handler(request):
    return httpx.Response(
        200,
        json={
            "total": 1,
            "page": 1,
            "list": [
                {
                    "xzqh": "370102",
                    "dh": "0531-88580775",
                    "mc": "山东省济南市历下区法律援助中心",
                    "dz": "济南市历下区历山路151号",
                    "jd": "117.041801",
                    "wd": "36.677819",
                    "id": "942AF0ED26C34CB3B8A9E3CDC6501682",
                }
            ],
        },
    )


def failing_handler(request):
    return httpx.Response(
        200,
        json={"success": False, "errormsg": "反爬虫策略中", "errorcode": "411"},
    )


def test_number_signature():
    payload = sign_payload(1, 14, "370102", "", v_key="a", guid="b")
    assert payload["number"] == 503


def test_search_lixia_live(tmp_path):
    divisions = DivisionIndex.load(ROOT / "data" / "divisions" / "jinan.json")
    client = LegalAidClient(
        settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak", LEGAL_AID_LIVE="1"),
        divisions,
        transport=httpx.MockTransport(handler),
    )
    result = client.search(district="历下区")
    assert result.centers[0].name == "山东省济南市历下区法律援助中心"
    assert result.source == "12348"


def test_411_falls_back_to_snapshot(tmp_path):
    divisions = DivisionIndex.load(ROOT / "data" / "divisions" / "jinan.json")
    client = LegalAidClient(
        settings(tmp_path, USE_LIVE="1", USE_MOCK="1", BAIDU_AK="test-ak", LEGAL_AID_LIVE="1"),
        divisions,
        transport=httpx.MockTransport(failing_handler),
    )
    result = client.search(district="历下区")
    assert result.source == "snapshot"
    assert result.centers
    assert any("PARTIAL" in warning.get("code", "") for warning in result.warnings)


def test_search_offline_uses_snapshot(tmp_path):
    divisions = DivisionIndex.load(ROOT / "data" / "divisions" / "jinan.json")
    client = LegalAidClient(settings(tmp_path), divisions)
    result = client.search(district="历下区")
    assert result.source == "snapshot"
    assert result.centers[0].name.startswith("山东省济南市历下区")
