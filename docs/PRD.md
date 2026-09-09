# PRD — Lead Triage Engine

**Status:** Draft, pending Daniel's final sign-off on the country list (Section 3, item 5) before Fase 2 seeds real values. Everything else below reflects Power Flow's real ICP (`powerflow/strategy.md`), not invented numbers.

## 1. Problem statement & users

Power Flow's outreach volume is starting to outpace manual triage. Today, every inbound and outbound lead gets the same attention regardless of fit — a referral from a warm contact waits in the same queue as a cold LinkedIn reply from a 5-person company outside the target market. As volume grows, that doesn't scale, and hard-coding a priority order means every ICP tweak needs a developer and a deploy.

**The user is the operator running outreach — today, Daniel.** The system's job is to tell that operator which lead to work next, and *why*, not to act on the lead itself.

## 2. What the system decides / explicitly does not decide

**Decides:** a priority (P1/P2/P3) for a single lead, with a score breakdown and — for leads in the ambiguous band — an AI-generated rationale.

**Never decides, never does:**
- Sends any message to a lead
- Changes CRM/deal status
- Discards or auto-rejects a lead

Blast radius of a wrong call is bounded by design: a lead sorted into the wrong bucket in a list, correctable by a human glancing at the queue. This scope cut is guardrail #1 and isn't negotiable without redoing this PRD.

## 3. Business rules v1

Field → condition → points. Grounded in Power Flow's actual ICP (`powerflow/strategy.md`): target buyer is COO / Operations Manager / Finance Director at 50-300 employee companies; channels in active use are referral, warm/content-driven inbound, cold LinkedIn outreach, and Upwork.

1. **Channel:** referral +30 · warm/inbound (content-driven) +20 · linkedin (cold outreach) +10 · upwork +5
2. **Company size:** 50-300 employees +20 (Power Flow's actual sweet spot — not a generic default) · 301-500 +10 · 1-49 +5 · 500+ +0
3. **Role seniority:** COO / Operations Manager / Finance Director (Power Flow's 3 real target buyers) +20 · any other role +0
4. **Urgency signal** in message/notes (keywords: "urgent", "asap", "this month") +15
5. **Country in target list** +10 — **placeholder pending Daniel:** seeded as `["United States", "Canada"]` based on the site's English-first, USD-priced positioning, but this is a guess, not a confirmed fact, and needs his explicit sign-off before Fase 6's eval treats it as ground truth.
6. **Missing-data rule:** fewer than 3 of the 5 fields above present on a lead → routed straight to `ambiguous`, regardless of score. Incomplete data is itself a signal the rules can't safely resolve alone.

**Bands:** score ≥ 70 → **P1** · score ≤ 40 → **P3** · 41-69 → **ambiguous → AI**

## 4. Success metrics

- Agreement with human judgment on the golden set (30 leads, Daniel-labeled): rules+AI hybrid **≥ 85%**
- % of leads landing in the ambiguous band: **< 30%** (higher says the rule bands themselves are miscalibrated, not that the AI layer is doing too much)
- % of leads sent to human review (`needs_review=true`): tracked, no fixed target — this number tells us how much the confidence gate is actually catching

## 5. Guardrail metrics — what happens when the system is wrong

*(Daniel: this is the section to be able to recite from memory — it's the actual point of the project.)*

| Failure mode | Mitigation |
|---|---|
| False P3 (a good lead triaged too low) | The ambiguous band never resolves straight to P3 without high AI confidence — a low-confidence "looks like P3" always routes to human review instead |
| Low-confidence AI decision | Any AI call with `confidence < 0.7` → `needs_review = true`, queued for a human, never silently trusted |
| Gemini API failure or timeout | Fail-safe, not fail-silent: `source = 'fallback'`, priority defaults to **P2**, `needs_review = true` — degrades to exactly the pre-system state (a human looks at it) |
| Runaway AI cost | Hard daily cap on AI calls (`triage.settings.ai_daily_cap`); once hit, remaining ambiguous leads fall back to P2 + review for the rest of the day |
| Undebuggable decisions | Every single decision — rules-only or AI-assisted — is logged to `triage.decisions` with the full rationale and matched rules. No exceptions, including fallback rows. |

## 6. Out of scope / future

- Trained ML model (no labeled dataset exists yet — this system is what generates one)
- Multi-tenant support
- Any auto-action on the CRM (sending messages, changing deal stage, etc.)

## Sign-off

- [ ] Daniel confirms the country list (Section 3, item 5)
- [ ] Daniel confirms the point values and bands above match his real judgment
- [ ] Daniel can recite Section 5 without looking
