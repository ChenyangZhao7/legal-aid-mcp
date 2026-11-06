from pathlib import Path
import pytest
from config import load_settings, ConfigError

ROOT = Path(__file__).resolve().parents[1]

def test_defaults(tmp_path):
    s = load_settings(env={}, base_dir=tmp_path)
    assert s.use_mock is True
    assert s.use_live is False
    assert s.live_budget == 20
    assert s.cache_ttl_hours == 24
    assert s.law_data_dir == tmp_path / "data" / "laws"
    assert s.fixtures_dir == tmp_path / "fixtures" / "baidu"

def test_live_requires_ak(tmp_path):
    with pytest.raises(ConfigError):
        load_settings(env={"USE_LIVE": "1"}, base_dir=tmp_path)

def test_live_wins_over_mock(tmp_path, capsys):
    s = load_settings(env={"USE_LIVE": "1", "USE_MOCK": "1", "BAIDU_AK": "test-ak"}, base_dir=tmp_path)
    assert s.use_live is True
    assert "USE_LIVE=1" in capsys.readouterr().err

def test_create_server_factory():
    from server import create_server
    s = load_settings(env={}, base_dir=ROOT)
    assert create_server(s).name == "legal-aid-mcp"
