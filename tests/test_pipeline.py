"""Covers the guardrails in PRD section 5 — none of these need a real
Gemini key. The point of this file is exactly that: the fail-safe path
is verifiable without ever making a network call.
"""

import pytest

from app.ai_judge import AIJudgeError, TriageResult
from app.models import LeadInput, Rule, Settings
from app.pipeline import run_pipeline
from app.seed_rules import DEFAULT_SETTINGS, RULES_V1

RULES = [Rule(**r) for r in RULES_V1]
SETTINGS = Settings(**DEFAULT_SETTINGS)

AMBIGUOUS_LEAD = LeadInput(channel="linkedin", company_size=120, role="Operations Manager", country="Germany")


def test_clear_p1_never_calls_the_ai_layer(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("judge() should never be called for a clear P1")

    monkeypatch.setattr("app.pipeline.judge", boom)
    lead = LeadInput(channel="referral", company_size=120, role="COO", country="United States")
    decision = run_pipeline(lead, RULES, SETTINGS, ai_calls_today=0)
    assert decision.source == "rules"
    assert decision.priority == "P1"


def test_ambiguous_lead_calls_ai_judge_when_enabled(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.judge",
        lambda lead, rule_result: TriageResult(priority="P1", confidence=0.9, rationale="looks strong"),
    )
    decision = run_pipeline(AMBIGUOUS_LEAD, RULES, SETTINGS, ai_calls_today=0)
    assert decision.source == "ai"
    assert decision.priority == "P1"
    assert decision.needs_review is False  # confidence 0.9 >= threshold 0.7


def test_low_confidence_ai_decision_forces_human_review(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.judge",
        lambda lead, rule_result: TriageResult(priority="P2", confidence=0.4, rationale="not enough signal"),
    )
    decision = run_pipeline(AMBIGUOUS_LEAD, RULES, SETTINGS, ai_calls_today=0)
    assert decision.source == "ai"
    assert decision.needs_review is True  # confidence 0.4 < threshold 0.7


def test_ai_failure_degrades_to_p2_and_review_not_silent_failure(monkeypatch):
    def raise_error(*a, **kw):
        raise AIJudgeError("simulated timeout")

    monkeypatch.setattr("app.pipeline.judge", raise_error)
    decision = run_pipeline(AMBIGUOUS_LEAD, RULES, SETTINGS, ai_calls_today=0)
    assert decision.source == "fallback"
    assert decision.priority == "P2"
    assert decision.needs_review is True
    assert "simulated timeout" in decision.rationale


def test_ai_disabled_kill_switch_skips_the_ai_layer_entirely(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("judge() should never be called when ai_enabled is False")

    monkeypatch.setattr("app.pipeline.judge", boom)
    settings = Settings(**{**DEFAULT_SETTINGS, "ai_enabled": False})
    decision = run_pipeline(AMBIGUOUS_LEAD, RULES, settings, ai_calls_today=0)
    assert decision.source == "fallback"
    assert decision.priority == "P2"
    assert decision.needs_review is True
    assert "kill switch" in decision.rationale.lower()


def test_daily_cap_reached_skips_the_ai_layer(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("judge() should never be called once the cap is spent")

    monkeypatch.setattr("app.pipeline.judge", boom)
    decision = run_pipeline(AMBIGUOUS_LEAD, RULES, SETTINGS, ai_calls_today=SETTINGS.ai_daily_cap)
    assert decision.source == "fallback"
    assert "cap" in decision.rationale.lower()


def test_every_decision_carries_the_matched_rules_for_auditability():
    lead = LeadInput(channel="referral", company_size=120, role="COO", country="United States")
    decision = run_pipeline(lead, RULES, SETTINGS, ai_calls_today=0)
    assert len(decision.matched_rules) > 0
