from pathlib import Path

from divisions import DivisionIndex

ROOT = Path(__file__).resolve().parents[1]


def test_jinan_districts():
    index = DivisionIndex.load(ROOT / "data" / "divisions" / "jinan.json")
    assert len(index.districts()) == 12
    assert index.adcode6("历下区") == "370102"
    assert index.adcode12("历下区") == "370102000000"
    assert index.find("火星") is None


def test_from_mca_payload():
    payload = {
        "data": {
            "code": "370100000000",
            "name": "济南市",
            "level": 2,
            "type": "地级市",
            "children": [
                {
                    "code": "370102000000",
                    "name": "历下区",
                    "level": 3,
                    "type": "市辖区",
                    "children": [
                        {
                            "code": "370102001000",
                            "name": "解放路街道",
                            "level": 4,
                            "type": "街道",
                            "children": [],
                        }
                    ],
                }
            ],
        }
    }
    index = DivisionIndex.from_mca_payload(payload)
    assert index.districts()[0].name == "历下区"
    assert index.adcode6("历下区") == "370102"
    assert index.find("解放路街道") is not None
