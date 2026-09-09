"""Rules v1 — the single source of truth, referenced by both the pytest
suite (Fase 3) and db/seed.sql's generation (Fase 2), so the rules tests
run against can never silently drift from what actually gets seeded.

Grounded in Power Flow's real ICP (powerflow/strategy.md) per PRD section 3.
The country list is a placeholder pending Daniel's sign-off — see PRD.
"""

RULES_V1 = [
    # --- channel ---
    {"name": "Channel: referral", "field": "channel", "operator": "equals", "value": "referral", "points": 30},
    {"name": "Channel: warm/inbound", "field": "channel", "operator": "equals", "value": "warm", "points": 20},
    {"name": "Channel: LinkedIn cold outreach", "field": "channel", "operator": "equals", "value": "linkedin", "points": 10},
    {"name": "Channel: Upwork", "field": "channel", "operator": "equals", "value": "upwork", "points": 5},

    # --- company size (bucketed from the raw employee count, see engine.py) ---
    {"name": "Company size: 50-300 (sweet spot)", "field": "company_size_bucket", "operator": "equals", "value": "50-300", "points": 20},
    {"name": "Company size: 301-500", "field": "company_size_bucket", "operator": "equals", "value": "301-500", "points": 10},
    {"name": "Company size: 1-49", "field": "company_size_bucket", "operator": "equals", "value": "1-49", "points": 5},
    {"name": "Company size: 500+", "field": "company_size_bucket", "operator": "equals", "value": "500+", "points": 0},

    # --- role seniority ---
    {
        "name": "Role: target buyer (COO/Ops Manager/Finance Director)",
        "field": "role",
        "operator": "in",
        "value": ["COO", "Operations Manager", "Finance Director"],
        "points": 20,
    },

    # --- urgency signal in free text ---
    {
        "name": "Urgency keyword in message/notes",
        "field": "message_or_notes",
        "operator": "contains_any",
        "value": ["urgent", "asap", "this month"],
        "points": 15,
    },

    # --- country — PLACEHOLDER, pending Daniel's sign-off (PRD section 3.5) ---
    {
        "name": "Country in target list (PLACEHOLDER pending sign-off)",
        "field": "country",
        "operator": "in",
        "value": ["United States", "Canada"],
        "points": 10,
    },
]

DEFAULT_SETTINGS = {
    "band_low": 40,
    "band_high": 70,
    "confidence_threshold": 0.7,
    "ai_enabled": True,
    "ai_daily_cap": 15,
}
