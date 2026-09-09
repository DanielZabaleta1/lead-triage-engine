import pytest

from app.engine import bucket_company_size, evaluate_rules
from app.models import LeadInput, Rule, Settings
from app.seed_rules import DEFAULT_SETTINGS, RULES_V1

RULES = [Rule(**r) for r in RULES_V1]
SETTINGS = Settings(**DEFAULT_SETTINGS)


def test_clear_p1_strong_lead():
    lead = LeadInput(
        channel="referral",
        company_size=120,
        role="COO",
        country="United States",
        message="Would love to talk this month, it's fairly urgent for us.",
    )
    result = evaluate_rules(lead, RULES, SETTINGS)
    # referral(30) + company 50-300(20) + role(20) + urgency(15) + country(10) = 95
    assert result.score == 95
    assert result.verdict == "P1"


def test_clear_p3_weak_lead():
    lead = LeadInput(
        channel="upwork",
        company_size=8,
        role="Marketing Coordinator",
        country="Germany",
    )
    result = evaluate_rules(lead, RULES, SETTINGS)
    # upwork(5) + company 1-49(5) + no role match + no country match = 10
    assert result.score == 10
    assert result.verdict == "P3"


def test_ambiguous_band_lands_in_the_middle():
    lead = LeadInput(channel="linkedin", company_size=120, role="Operations Manager", country="Germany")
    result = evaluate_rules(lead, RULES, SETTINGS)
    # linkedin(10) + company 50-300(20) + role(20), no country match = 50 -> between 41 and 69
    assert result.score == 50
    assert result.verdict == "ambiguous"


@pytest.mark.parametrize(
    "score, expected_verdict",
    [
        (70, "P1"),   # exactly band_high -> P1
        (69, "ambiguous"),
        (40, "P3"),   # exactly band_low -> P3
        (41, "ambiguous"),
    ],
)
def test_band_edges_are_inclusive_correctly(score, expected_verdict):
    # Build a synthetic single custom rule so the score lands exactly where we want,
    # rather than fighting RULES_V1's combinations for every edge value.
    custom_rule = Rule(name="synthetic", field="channel", operator="equals", value="synthetic", points=score)
    lead = LeadInput(channel="synthetic", company_size=100, role="COO", country="United States")
    result = evaluate_rules(lead, [custom_rule], SETTINGS)
    assert result.score == score
    assert result.verdict == expected_verdict


def test_missing_data_forces_ambiguous_even_with_a_high_scoring_field():
    # Only channel present (a referral, which alone would be worth +30) — but
    # that's only 1 of 4 presence fields plus no message/notes, well under
    # the threshold of 3. Missing data wins over the raw score.
    lead = LeadInput(channel="referral")
    result = evaluate_rules(lead, RULES, SETTINGS)
    assert result.verdict == "ambiguous"
    assert result.forced_ambiguous_reason is not None
    assert result.score == 0  # scoring is skipped entirely when data is this thin


def test_exactly_at_threshold_is_not_forced_ambiguous():
    # channel + company_size + role = 3 of 4 presence fields -> meets the
    # threshold, so the real score (not the missing-data override) decides.
    lead = LeadInput(channel="referral", company_size=120, role="COO")
    result = evaluate_rules(lead, RULES, SETTINGS)
    assert result.forced_ambiguous_reason is None


def test_disabled_rule_does_not_contribute():
    rules = [Rule(**r) for r in RULES_V1]
    for r in rules:
        if r.field == "channel" and r.value == "referral":
            r.enabled = False
    lead = LeadInput(channel="referral", company_size=120, role="COO", country="United States")
    enabled_result = evaluate_rules(lead, RULES, SETTINGS)
    disabled_result = evaluate_rules(lead, rules, SETTINGS)
    assert disabled_result.score == enabled_result.score - 30
    assert not any(m.name.startswith("Channel: referral") for m in disabled_result.matched_rules)


@pytest.mark.parametrize("keyword_variant", ["urgent", "URGENT", "Urgent", "asap", "ASAP", "this month"])
def test_urgency_keyword_matching_is_case_insensitive(keyword_variant):
    lead = LeadInput(channel="referral", company_size=120, role="COO", message=f"Need this {keyword_variant}!")
    result = evaluate_rules(lead, RULES, SETTINGS)
    assert any("Urgency" in m.name for m in result.matched_rules)


def test_no_urgency_keyword_means_no_match():
    lead = LeadInput(channel="referral", company_size=120, role="COO", message="Just checking in, no rush.")
    result = evaluate_rules(lead, RULES, SETTINGS)
    assert not any("Urgency" in m.name for m in result.matched_rules)


@pytest.mark.parametrize(
    "size, expected_bucket",
    [
        (1, "1-49"),
        (49, "1-49"),
        (50, "50-300"),
        (300, "50-300"),
        (301, "301-500"),
        (500, "301-500"),
        (501, "500+"),
        (10_000, "500+"),
        (None, None),
    ],
)
def test_company_size_bucketing_edges(size, expected_bucket):
    assert bucket_company_size(size) == expected_bucket


def test_role_not_in_target_list_scores_zero_for_that_dimension():
    lead = LeadInput(channel="referral", company_size=120, role="Marketing Coordinator", country="United States")
    result = evaluate_rules(lead, RULES, SETTINGS)
    assert not any("Role:" in m.name for m in result.matched_rules)


def test_notes_alone_can_satisfy_urgency_without_a_message():
    lead = LeadInput(channel="referral", company_size=120, role="COO", notes="Client said asap on the call.")
    result = evaluate_rules(lead, RULES, SETTINGS)
    assert any("Urgency" in m.name for m in result.matched_rules)


def test_matched_rules_list_is_auditable():
    lead = LeadInput(channel="referral", company_size=120, role="COO", country="United States")
    result = evaluate_rules(lead, RULES, SETTINGS)
    names = {m.name for m in result.matched_rules}
    assert "Channel: referral" in names
    assert "Company size: 50-300 (sweet spot)" in names
    assert "Role: target buyer (COO/Ops Manager/Finance Director)" in names
    assert "Country in target list (PLACEHOLDER pending sign-off)" in names
