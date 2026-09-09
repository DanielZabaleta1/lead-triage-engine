"""Fase 4 — the AI layer, invoked ONLY when the deterministic engine
returns 'ambiguous' and ai_enabled is true and the daily cap isn't spent.

NOT independently tested against a live Gemini call yet — the two keys
already in CREDENTIALS.md share a 20-request/day quota with n8n (WF1/WF4)
and powerflow-insights in production. Burning that quota here would risk
breaking systems that are actually live. This needs its own GCP project's
key before Fase 6's eval can run for real (see pasos_daniel.md).

What IS verified without a real key: the fail-safe path in main.py — any
exception here (including "no API key configured") degrades to
source='fallback', priority=P2, needs_review=True. That's tested in
tests/test_pipeline.py by deliberately breaking this module's client call.
"""

import os
from typing import Literal

from pydantic import BaseModel, Field

from app.models import LeadInput, RuleResult

SYSTEM_PROMPT = """You are the AI judge for Power Flow's lead triage system. \
You only ever see leads the deterministic rules engine could not confidently \
classify — a score in the ambiguous band, or a lead missing enough of its \
data that the rules refused to trust their own score.

Power Flow's ICP: operations automation for 50-300 employee companies, sold \
to COOs, Operations Managers, and Finance Directors. Channels in use: \
referral, warm/content-driven inbound, cold LinkedIn outreach, Upwork.

You classify into exactly one of P1 (contact today), P2 (this week), or P3 \
(when there's time). If key ICP fields are missing from the lead, lower your \
confidence accordingly and name exactly which fields you'd have wanted — \
that list feeds the human review queue with something actionable, not just \
a low number.

Respond ONLY in the given JSON schema. Keep the rationale to 2-3 sentences, \
in plain business language a non-technical operator would read in a queue, \
not engineering-speak."""


class TriageResult(BaseModel):
    priority: Literal["P1", "P2", "P3"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    missing_info: list[str] = Field(default_factory=list)


class AIJudgeError(Exception):
    """Raised for anything that should trigger the fail-safe path in
    main.py — a missing key, an API error, a timeout, an empty response.
    Deliberately one exception type: main.py doesn't need to know why the
    AI layer failed, only that it did, and to degrade accordingly."""


def _build_lead_context(lead: LeadInput, rule_result: RuleResult) -> str:
    fields = "\n".join(f"- {k}: {v}" for k, v in lead.model_dump().items() if v not in (None, ""))
    matched = ", ".join(m.name for m in rule_result.matched_rules) or "none"
    return (
        f"Lead fields present:\n{fields}\n\n"
        f"Deterministic engine's partial score: {rule_result.score} "
        f"(matched rules: {matched})\n"
        f"The rules engine could not confidently resolve this lead alone — that's why you're seeing it."
    )


def judge(lead: LeadInput, rule_result: RuleResult) -> TriageResult:
    """Raises AIJudgeError on anything that should fall back to P2 +
    needs_review in the caller — never raises the underlying SDK exception
    directly, so main.py has exactly one failure mode to handle."""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise AIJudgeError("GEMINI_API_KEY not configured")

    try:
        # Import deferred to here so the rest of the app (and its tests)
        # never need the google-genai package installed just to run.
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_build_lead_context(lead, rule_result),
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_schema": TriageResult,
                "temperature": 0.1,
            },
        )
        parsed = response.parsed
        if parsed is None:
            raise AIJudgeError("Gemini returned no parseable structured output")
        return parsed
    except AIJudgeError:
        raise
    except Exception as exc:  # noqa: BLE001 — intentionally broad, see docstring
        raise AIJudgeError(f"Gemini call failed: {exc}") from exc
