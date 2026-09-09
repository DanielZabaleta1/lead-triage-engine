"""Pydantic models shared across the engine, the AI judge, and the API.

Kept dependency-free (no Supabase/Gemini imports here) so `engine.py` stays
pure and unit-testable without any I/O — that's the whole point of Fase 3.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Priority = Literal["P1", "P2", "P3"]
Operator = Literal["equals", "in", "contains_any", "gte", "lte"]
Source = Literal["rules", "ai", "fallback"]


class LeadInput(BaseModel):
    """Everything optional except channel — real-world leads arrive with
    incomplete data, and that incompleteness is itself a signal (see
    MISSING_DATA_THRESHOLD in engine.py), not something to paper over."""

    name: Optional[str] = None
    company: Optional[str] = None
    channel: str
    company_size: Optional[int] = None
    role: Optional[str] = None
    country: Optional[str] = None
    message: Optional[str] = None
    notes: Optional[str] = None


class Rule(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    field: str
    operator: Operator
    value: object  # str | list[str] | int | float, shape depends on operator
    points: int
    enabled: bool = True


class MatchedRule(BaseModel):
    rule_id: Optional[int]
    name: str
    points: int


class Settings(BaseModel):
    band_low: int = 40
    band_high: int = 70
    confidence_threshold: float = 0.7
    ai_enabled: bool = True
    ai_daily_cap: int = 15


class RuleResult(BaseModel):
    score: int
    matched_rules: list[MatchedRule]
    verdict: Literal["P1", "P3", "ambiguous"]
    forced_ambiguous_reason: Optional[str] = None


class TriageDecision(BaseModel):
    """What actually gets written to triage.decisions."""

    score: int
    matched_rules: list[MatchedRule]
    source: Source
    priority: Priority
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    needs_review: bool = False
