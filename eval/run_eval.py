"""Fase 6 — the measurable result.

Runs the 30 golden leads through three configurations and reports agreement
against Daniel's hand labels plus a confusion matrix:

  A. rules only        — ambiguous band defaults to P2, no AI
  B. rules + AI hybrid  — the real pipeline (needs GEMINI_API_KEY)
  C. AI for everything  — every lead judged by the LLM, ignoring the rules
                          (needs GEMINI_API_KEY; the "why not just use AI"
                          baseline)

Expected reading, to be confirmed by the real numbers: A misses in the
middle band, C is expensive/slower/less explainable, B wins. If the real
numbers say otherwise, the README reports that and the rules or prompt get
one iteration — not a number touch-up.

Run: python eval/run_eval.py
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai_judge import AIJudgeError, judge  # noqa: E402
from app.engine import evaluate_rules  # noqa: E402
from app.models import LeadInput, Rule, Settings  # noqa: E402
from app.seed_rules import DEFAULT_SETTINGS, RULES_V1  # noqa: E402

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_leads.json"
PRIORITIES = ["P1", "P2", "P3"]


def load_golden() -> list[dict]:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    leads = data["leads"]
    unlabeled = [ld["id"] for ld in leads if ld.get("label") not in PRIORITIES]
    if unlabeled:
        sys.exit(
            f"Leads not labeled yet (need P1/P2/P3): {unlabeled}\n"
            f"Edit eval/golden_leads.json - Daniel's labels are the ground truth."
        )
    return leads


def _lead_input(row: dict) -> LeadInput:
    return LeadInput(**{k: v for k, v in row.items() if k in LeadInput.model_fields})


def config_a_rules_only(lead: LeadInput, rules, settings) -> str:
    r = evaluate_rules(lead, rules, settings)
    return "P2" if r.verdict == "ambiguous" else r.verdict


def config_b_hybrid(lead: LeadInput, rules, settings) -> str:
    r = evaluate_rules(lead, rules, settings)
    if r.verdict != "ambiguous":
        return r.verdict
    try:
        return judge(lead, r).priority
    except AIJudgeError:
        return "P2"  # same fail-safe as the real pipeline


def config_c_ai_only(lead: LeadInput, rules, settings) -> str:
    r = evaluate_rules(lead, rules, settings)
    try:
        return judge(lead, r).priority
    except AIJudgeError:
        return "P2"


def score_config(name: str, fn, leads, rules, settings) -> None:
    matrix = Counter()  # (truth, predicted) -> count
    agree = 0
    for row in leads:
        truth = row["label"]
        pred = fn(_lead_input(row), rules, settings)
        matrix[(truth, pred)] += 1
        agree += truth == pred

    pct = 100 * agree / len(leads)
    print(f"\n=== {name} ===")
    print(f"agreement: {agree}/{len(leads)} = {pct:.1f}%")
    print("confusion matrix (rows = your label, cols = predicted):")
    header = "        " + "".join(f"{p:>6}" for p in PRIORITIES)
    print(header)
    for truth in PRIORITIES:
        cells = "".join(f"{matrix[(truth, p)]:>6}" for p in PRIORITIES)
        print(f"  {truth:<5}{cells}")


def main() -> None:
    leads = load_golden()
    rules = [Rule(**r) for r in RULES_V1]
    settings = Settings(**DEFAULT_SETTINGS)

    score_config("A — rules only (ambiguous -> P2)", config_a_rules_only, leads, rules, settings)

    if not os.environ.get("GEMINI_API_KEY"):
        print("\n(GEMINI_API_KEY not set — configs B and C skipped. Set a key from a")
        print(" GCP project NOT shared with n8n/powerflow-insights, then rerun.)")
        return

    score_config("B — rules + AI hybrid", config_b_hybrid, leads, rules, settings)
    score_config("C — AI only", config_c_ai_only, leads, rules, settings)


if __name__ == "__main__":
    main()
