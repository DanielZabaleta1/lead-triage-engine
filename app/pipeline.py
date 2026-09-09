"""Wires the deterministic engine to the AI layer. Kept separate from
main.py so it can be unit-tested against fake rules/settings without a
FastAPI app or a live database in the loop — see tests/test_pipeline.py,
in particular the fail-safe tests, which never touch a real Gemini key.
"""

from app.ai_judge import AIJudgeError, judge
from app.engine import evaluate_rules
from app.models import LeadInput, Rule, Settings, TriageDecision


def run_pipeline(
    lead: LeadInput,
    rules: list[Rule],
    settings: Settings,
    ai_calls_today: int,
) -> TriageDecision:
    rule_result = evaluate_rules(lead, rules, settings)

    if rule_result.verdict in ("P1", "P3"):
        return TriageDecision(
            score=rule_result.score,
            matched_rules=rule_result.matched_rules,
            source="rules",
            priority=rule_result.verdict,
            needs_review=False,
        )

    # ambiguous from here down
    if not settings.ai_enabled:
        return _fallback(rule_result, reason="AI judge is disabled (kill switch is off)")

    if ai_calls_today >= settings.ai_daily_cap:
        return _fallback(rule_result, reason=f"Daily AI cap reached ({settings.ai_daily_cap} calls)")

    try:
        result = judge(lead, rule_result)
    except AIJudgeError as exc:
        return _fallback(rule_result, reason=str(exc))

    return TriageDecision(
        score=rule_result.score,
        matched_rules=rule_result.matched_rules,
        source="ai",
        priority=result.priority,
        confidence=result.confidence,
        rationale=result.rationale,
        needs_review=result.confidence < settings.confidence_threshold,
    )


def _fallback(rule_result, reason: str) -> TriageDecision:
    """Fail-safe, never fail-silent: whatever stopped the AI layer from
    running, the lead still gets a priority (P2) and a human still sees
    it — the exact same outcome as before this system existed."""
    return TriageDecision(
        score=rule_result.score,
        matched_rules=rule_result.matched_rules,
        source="fallback",
        priority="P2",
        rationale=reason,
        needs_review=True,
    )
