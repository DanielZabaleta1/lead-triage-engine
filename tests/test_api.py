"""API + panel tests against a fake in-memory store — no live Supabase.
Verifies routing, template rendering, and the htmx swap responses;
doesn't verify the real Supabase queries in app/db.py themselves (that
needs the live project, see pasos_daniel.md).
"""

import copy

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.seed_rules import DEFAULT_SETTINGS, RULES_V1


class FakeStore:
    def __init__(self):
        self.rules = [{"id": i + 1, **r, "enabled": True} for i, r in enumerate(RULES_V1)]
        self.settings = dict(DEFAULT_SETTINGS)
        self.decisions = []
        self._next_decision_id = 1


@pytest.fixture
def store(monkeypatch):
    s = FakeStore()

    def get_rules(enabled_only=False):
        from app.models import Rule

        rows = s.rules if not enabled_only else [r for r in s.rules if r["enabled"]]
        return [Rule(**r) for r in rows]

    def get_settings():
        from app.models import Settings

        return Settings(**s.settings)

    def toggle_rule(rule_id, enabled):
        for r in s.rules:
            if r["id"] == rule_id:
                r["enabled"] = enabled

    def update_rule_points(rule_id, points):
        for r in s.rules:
            if r["id"] == rule_id:
                r["points"] = points

    def update_setting(key, value):
        s.settings[key] = value

    def count_ai_calls_today():
        return sum(1 for d in s.decisions if d["source"] == "ai")

    def log_decision(lead_snapshot, decision):
        row = {"id": s._next_decision_id, "lead_snapshot": lead_snapshot, "reviewed_priority": None, **decision.model_dump()}
        s.decisions.append(row)
        s._next_decision_id += 1
        return row["id"]

    def list_decisions(needs_review_only=False, limit=50):
        rows = s.decisions if not needs_review_only else [d for d in s.decisions if d["needs_review"]]
        return copy.deepcopy(list(reversed(rows)))[:limit]

    def set_reviewed_priority(decision_id, priority):
        for d in s.decisions:
            if d["id"] == decision_id:
                d["reviewed_priority"] = priority
                d["needs_review"] = False

    monkeypatch.setattr(db, "get_rules", get_rules)
    monkeypatch.setattr(db, "get_settings", get_settings)
    monkeypatch.setattr(db, "toggle_rule", toggle_rule)
    monkeypatch.setattr(db, "update_rule_points", update_rule_points)
    monkeypatch.setattr(db, "update_setting", update_setting)
    monkeypatch.setattr(db, "count_ai_calls_today", count_ai_calls_today)
    monkeypatch.setattr(db, "log_decision", log_decision)
    monkeypatch.setattr(db, "list_decisions", list_decisions)
    monkeypatch.setattr(db, "set_reviewed_priority", set_reviewed_priority)
    return s


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_triage_endpoint_returns_p1_for_a_clear_lead(client, store):
    resp = client.post(
        "/triage",
        json={"channel": "referral", "company_size": 120, "role": "COO", "country": "United States"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority"] == "P1"
    assert body["source"] == "rules"
    assert len(store.decisions) == 1  # logged exactly once


def test_triage_batch_logs_every_lead(client, store):
    resp = client.post(
        "/triage/batch",
        json=[
            {"channel": "referral", "company_size": 120, "role": "COO", "country": "United States"},
            {"channel": "upwork", "company_size": 8, "role": "Other"},
        ],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert len(store.decisions) == 2


def test_panel_rules_renders_all_seeded_rules(client, store):
    resp = client.get("/panel/rules")
    assert resp.status_code == 200
    assert "Channel: referral" in resp.text


def test_toggle_rule_flips_state_and_returns_updated_row(client, store):
    rule_id = store.rules[0]["id"]
    assert store.rules[0]["enabled"] is True
    resp = client.post(f"/panel/rules/{rule_id}/toggle")
    assert resp.status_code == 200
    assert store.rules[0]["enabled"] is False
    assert f'id="rule-row-{rule_id}"' in resp.text
    assert "disabled" in resp.text  # the <tr class="disabled"> from the template


def test_update_rule_points_persists_new_value(client, store):
    rule_id = store.rules[0]["id"]
    resp = client.post(f"/panel/rules/{rule_id}/points", data={"points": "99"})
    assert resp.status_code == 200
    assert store.rules[0]["points"] == 99
    assert 'value="99"' in resp.text


def test_panel_settings_get_and_save(client, store):
    get_resp = client.get("/panel/settings")
    assert get_resp.status_code == 200

    save_resp = client.post(
        "/panel/settings",
        data={
            "band_low": "35",
            "band_high": "75",
            "confidence_threshold": "0.6",
            "ai_enabled": "true",
            "ai_daily_cap": "10",
        },
    )
    assert save_resp.status_code == 200
    assert store.settings["band_low"] == 35
    assert store.settings["ai_daily_cap"] == 10
    assert "Saved" in save_resp.text


def test_decisions_log_and_review_flow(client, store):
    # ambiguous-ish lead with AI disabled -> falls back to needs_review
    client.post("/panel/settings", data={
        "band_low": "40", "band_high": "70", "confidence_threshold": "0.7",
        "ai_daily_cap": "15",  # ai_enabled omitted -> False
    })
    client.post("/triage", json={"channel": "linkedin", "company_size": 120, "role": "Operations Manager", "country": "Germany"})

    all_resp = client.get("/panel/decisions")
    assert all_resp.status_code == 200

    review_resp = client.get("/panel/decisions?needs_review=true")
    assert "fallback" in review_resp.text or "Confirm" in review_resp.text

    decision_id = store.decisions[0]["id"]
    confirm_resp = client.post(f"/panel/decisions/{decision_id}/review", data={"reviewed_priority": "P2"})
    assert confirm_resp.status_code == 200
    assert "reviewed" in confirm_resp.text.lower()
    assert store.decisions[0]["reviewed_priority"] == "P2"
