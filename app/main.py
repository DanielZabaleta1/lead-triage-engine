"""Fase 5 — the API + the 3-screen admin panel (Jinja2 + htmx, no SPA).

Why no SPA: this is an internal 3-screen panel, not a product surface with
its own users — React would be solving a problem this panel doesn't have.
The portfolio's other product piece (Ask Your Data) is already an SPA;
this project deliberately isn't, so the portfolio shows both calls, not
just one default.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db
from app.models import LeadInput
from app.pipeline import run_pipeline

app = FastAPI(title="Lead Triage Engine")
templates = Jinja2Templates(directory="templates")


# --- core API ---

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/triage")
def triage(lead: LeadInput):
    rules = db.get_rules(enabled_only=True)
    settings = db.get_settings()
    ai_calls_today = db.count_ai_calls_today() if settings.ai_enabled else 0
    decision = run_pipeline(lead, rules, settings, ai_calls_today)
    decision_id = db.log_decision(lead.model_dump(), decision)
    return {"id": decision_id, **decision.model_dump()}


@app.post("/triage/batch")
def triage_batch(leads: list[LeadInput]):
    rules = db.get_rules(enabled_only=True)
    settings = db.get_settings()
    results = []
    ai_calls_today = db.count_ai_calls_today() if settings.ai_enabled else 0
    for lead in leads:
        decision = run_pipeline(lead, rules, settings, ai_calls_today)
        if decision.source == "ai":
            ai_calls_today += 1  # keep the running cap accurate within one batch
        decision_id = db.log_decision(lead.model_dump(), decision)
        results.append({"id": decision_id, **decision.model_dump()})
    return results


# --- panel: rules screen ---

@app.get("/panel/rules", response_class=HTMLResponse)
def panel_rules(request: Request):
    rules = db.get_rules()
    return templates.TemplateResponse(request, "rules.html", {"rules": rules, "active": "rules"})


@app.post("/panel/rules/{rule_id}/toggle", response_class=HTMLResponse)
def toggle_rule(request: Request, rule_id: int):
    rules = {r.id: r for r in db.get_rules()}
    rule = rules[rule_id]
    db.toggle_rule(rule_id, not rule.enabled)
    rule.enabled = not rule.enabled
    return templates.TemplateResponse(request, "_rule_row.html", {"rule": rule})


@app.post("/panel/rules/{rule_id}/points", response_class=HTMLResponse)
def update_rule_points(request: Request, rule_id: int, points: int = Form(...)):
    db.update_rule_points(rule_id, points)
    rules = {r.id: r for r in db.get_rules()}
    rule = rules[rule_id]
    rule.points = points
    return templates.TemplateResponse(request, "_rule_row.html", {"rule": rule})


# --- panel: settings screen ---

@app.get("/panel/settings", response_class=HTMLResponse)
def panel_settings(request: Request):
    settings = db.get_settings()
    return templates.TemplateResponse(
        request, "settings.html", {"settings": settings, "saved": False, "active": "settings"}
    )


@app.post("/panel/settings", response_class=HTMLResponse)
def save_settings(
    request: Request,
    band_low: int = Form(...),
    band_high: int = Form(...),
    confidence_threshold: float = Form(...),
    ai_enabled: bool = Form(False),
    ai_daily_cap: int = Form(...),
):
    db.update_setting("band_low", band_low)
    db.update_setting("band_high", band_high)
    db.update_setting("confidence_threshold", confidence_threshold)
    db.update_setting("ai_enabled", ai_enabled)
    db.update_setting("ai_daily_cap", ai_daily_cap)
    settings = db.get_settings()
    return templates.TemplateResponse(
        request, "settings.html", {"settings": settings, "saved": True, "active": "settings"}
    )


# --- panel: decisions log ---

@app.get("/panel/decisions", response_class=HTMLResponse)
def panel_decisions(request: Request, needs_review: bool = False):
    decisions = db.list_decisions(needs_review_only=needs_review)
    return templates.TemplateResponse(
        request,
        "decisions.html",
        {"decisions": decisions, "needs_review_only": needs_review, "active": "decisions"},
    )


@app.post("/panel/decisions/{decision_id}/review", response_class=HTMLResponse)
def review_decision(request: Request, decision_id: int, reviewed_priority: str = Form(...)):
    db.set_reviewed_priority(decision_id, reviewed_priority)
    decisions = db.list_decisions(needs_review_only=False)
    row = next(d for d in decisions if d["id"] == decision_id)
    return templates.TemplateResponse(request, "_decision_row.html", {"d": row})
