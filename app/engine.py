"""Fase 3 — the deterministic engine. Pure function, no I/O, no network,
no database — this is the piece that gets unit-tested, not evaluated.

("What's deterministic gets tested. What's probabilistic gets evaluated." —
that split, and being able to say it out loud, is half of this project's
pitch.)
"""

from app.models import LeadInput, MatchedRule, Rule, RuleResult, Settings

# How many of these 5 ICP dimensions must be present before the rules engine
# trusts its own score. Below this, missing data IS the signal — see PRD
# section 3, item 6.
PRESENCE_FIELDS = ("channel", "company_size", "role", "country")
MISSING_DATA_THRESHOLD = 3

COMPANY_SIZE_BUCKETS = (
    (49, "1-49"),
    (300, "50-300"),
    (500, "301-500"),
    (None, "500+"),
)


def bucket_company_size(size: int | None) -> str | None:
    """Turns a raw employee count into the named tier the rules actually
    match on (field `company_size_bucket`). Keeps the rule operator set to
    equals/in/contains_any/gte/lte — no need for a bespoke 'between'
    operator just to express a range."""
    if size is None:
        return None
    for upper, label in COMPANY_SIZE_BUCKETS:
        if upper is None or size <= upper:
            return label
    return None  # unreachable, satisfies type checkers


def _presence_count(lead: LeadInput) -> int:
    count = sum(1 for f in PRESENCE_FIELDS if getattr(lead, f) not in (None, ""))
    if (lead.message or lead.notes):
        count += 1
    return count


def _field_value(lead: LeadInput, field: str):
    if field == "company_size_bucket":
        return bucket_company_size(lead.company_size)
    if field == "message_or_notes":
        return " ".join(filter(None, [lead.message, lead.notes])).lower()
    return getattr(lead, field, None)


def _rule_matches(lead: LeadInput, rule: Rule) -> bool:
    value = _field_value(lead, rule.field)
    if value is None:
        return False

    if rule.operator == "equals":
        return value == rule.value
    if rule.operator == "in":
        return value in rule.value
    if rule.operator == "contains_any":
        return any(str(kw).lower() in str(value) for kw in rule.value)
    if rule.operator == "gte":
        return value >= rule.value
    if rule.operator == "lte":
        return value <= rule.value
    raise ValueError(f"Unknown operator: {rule.operator}")  # pragma: no cover


def evaluate_rules(lead: LeadInput, rules: list[Rule], settings: Settings) -> RuleResult:
    """Sums points from every enabled rule that matches, then classifies
    into P1 / P3 / ambiguous per the settings bands — unless the lead is
    missing too much data to trust the score at all, in which case it's
    ambiguous regardless of what the score says."""

    if _presence_count(lead) < MISSING_DATA_THRESHOLD:
        return RuleResult(
            score=0,
            matched_rules=[],
            verdict="ambiguous",
            forced_ambiguous_reason=(
                f"fewer than {MISSING_DATA_THRESHOLD} of {PRESENCE_FIELDS + ('message/notes',)} present"
            ),
        )

    matched = [
        MatchedRule(rule_id=r.id, name=r.name, points=r.points)
        for r in rules
        if r.enabled and _rule_matches(lead, r)
    ]
    score = sum(m.points for m in matched)

    if score >= settings.band_high:
        verdict = "P1"
    elif score <= settings.band_low:
        verdict = "P3"
    else:
        verdict = "ambiguous"

    return RuleResult(score=score, matched_rules=matched, verdict=verdict)
