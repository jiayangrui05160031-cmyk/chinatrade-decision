"""Tests for api/main.py — FastAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from wto_policy.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_root(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert "WTO Policy" in body["name"]

    def test_healthz(self, client: TestClient) -> None:
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["tariff_measures"] > 0


class TestDecisionCard:
    def test_basic_led_lamp(self, client: TestClient) -> None:
        r = client.post(
            "/api/decision-card",
            json={
                "hs_code": "9405408000",
                "cif_value_usd": 17200.0,
                "quantity": 1000,
                "profile": {
                    "name": "中山灯具厂",
                    "sector": "灯具",
                    "annual_export_usd": 2_000_000,
                    "main_destinations": ["US"],
                    "trade_mode": "general_trade",
                },
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["hs_code"] == "9405408000"
        assert body["total_tax"] > 0
        assert body["net_landed_cost"] > body["cif_value_usd"]
        assert len(body["risks"]) >= 2  # 301 + IEEPA
        assert len(body["sources"]) >= 1

    def test_missing_field_400(self, client: TestClient) -> None:
        r = client.post("/api/decision-card", json={"hs_code": "9405408000"})
        assert r.status_code == 422  # Pydantic validation

    def test_negative_value_400(self, client: TestClient) -> None:
        r = client.post(
            "/api/decision-card",
            json={"hs_code": "9405408000", "cif_value_usd": -1.0},
        )
        assert r.status_code == 422
