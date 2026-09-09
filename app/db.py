"""All Supabase I/O lives here, and nowhere else — main.py's pipeline logic
never imports the supabase client directly, so it can be exercised in
tests against a fake implementation of this module's functions instead of
a live database. Schema `triage`, isolated from the rest of the Power
Flow OS project sharing this same Supabase instance.
"""

import os
from datetime import datetime, timezone
from functools import lru_cache

from supabase import Client, create_client

from app.models import Rule, Settings, TriageDecision


@lru_cache
def _client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def get_rules(enabled_only: bool = False) -> list[Rule]:
    q = _client().schema("triage").table("rules").select("*").order("id")
    if enabled_only:
        q = q.eq("enabled", True)
    rows = q.execute().data
    return [Rule(**row) for row in rows]


def get_settings() -> Settings:
    rows = _client().schema("triage").table("settings").select("*").execute().data
    values = {row["key"]: row["value"] for row in rows}
    return Settings(**values)


def toggle_rule(rule_id: int, enabled: bool) -> None:
    _client().schema("triage").table("rules").update(
        {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", rule_id).execute()


def update_rule_points(rule_id: int, points: int) -> None:
    _client().schema("triage").table("rules").update(
        {"points": points, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", rule_id).execute()


def update_setting(key: str, value) -> None:
    _client().schema("triage").table("settings").update(
        {"value": value, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("key", key).execute()


def count_ai_calls_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    rows = (
        _client()
        .schema("triage")
        .table("decisions")
        .select("id", count="exact")
        .eq("source", "ai")
        .gte("created_at", today)
        .execute()
    )
    return rows.count or 0


def log_decision(lead_snapshot: dict, decision: TriageDecision) -> int:
    row = {
        "lead_snapshot": lead_snapshot,
        "score": decision.score,
        "matched_rules": [m.model_dump() for m in decision.matched_rules],
        "source": decision.source,
        "priority": decision.priority,
        "confidence": decision.confidence,
        "rationale": decision.rationale,
        "needs_review": decision.needs_review,
    }
    result = _client().schema("triage").table("decisions").insert(row).execute()
    return result.data[0]["id"]


def list_decisions(needs_review_only: bool = False, limit: int = 50) -> list[dict]:
    q = (
        _client()
        .schema("triage")
        .table("decisions")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if needs_review_only:
        q = q.eq("needs_review", True)
    return q.execute().data


def set_reviewed_priority(decision_id: int, priority: str) -> None:
    _client().schema("triage").table("decisions").update(
        {"reviewed_priority": priority, "needs_review": False}
    ).eq("id", decision_id).execute()
