import pytest

from coord import (
    bd09_to_gcj02,
    bd09_to_wgs84,
    gcj02_to_bd09,
    gcj02_to_wgs84,
    haversine_m,
    wgs84_to_bd09,
    wgs84_to_gcj02,
)


def test_gcj02_bd09_roundtrip():
    lng, lat = 116.404, 39.915
    back = bd09_to_gcj02(*gcj02_to_bd09(lng, lat))
    assert back == pytest.approx((lng, lat), abs=1e-6)


def test_gcj02_wgs84_roundtrip():
    lng, lat = 116.404, 39.915
    back = gcj02_to_wgs84(*wgs84_to_gcj02(lng, lat))
    assert back == pytest.approx((lng, lat), abs=1e-6)


def test_bd09_wgs84_roundtrip():
    lng, lat = 116.404, 39.915
    back = bd09_to_wgs84(*wgs84_to_bd09(lng, lat))
    assert back == pytest.approx((lng, lat), abs=1e-5)


def test_haversine_jinan():
    # 济南西站到济南中院直线约 11km
    meters = haversine_m((116.890, 36.670), (117.013, 36.672))
    assert 9000 < meters < 13000
