"""Interactive labeling helper for eval/golden_leads.json.

Shows one lead at a time (no engine score, no hints) and asks for a P1/P2/P3
judgment. Writes back to the JSON after every answer, so you can quit and
resume anytime without losing progress. Run it from the repo root:

    python eval/label_leads.py
"""

import json
from pathlib import Path

PATH = Path(__file__).parent / "golden_leads.json"


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    leads = data["leads"]
    remaining = [lead for lead in leads if not lead.get("label")]

    if not remaining:
        print("All 30 leads are already labeled.")
        return

    print(f"{len(remaining)} of {len(leads)} leads left to label.")
    print("For each one: type 1 (P1, top priority), 2 (P2, worth a look), 3 (P3, low priority).")
    print("Type 's' to skip, 'q' to save and quit.\n")

    for lead in remaining:
        print("-" * 60)
        print(f"[{lead['id']}] {lead.get('name') or '(no name)'} — {lead.get('company') or '(no company)'}")
        print(f"  channel: {lead.get('channel')}   size: {lead.get('company_size')}   role: {lead.get('role')}   country: {lead.get('country')}")
        print(f"  message: {lead.get('message') or '(none)'}")
        if lead.get("notes"):
            print(f"  notes: {lead['notes']}")

        while True:
            answer = input("  label (1/2/3/s/q): ").strip().lower()
            if answer == "q":
                PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print("Saved. Resume anytime by running this again.")
                return
            if answer == "s":
                break
            if answer in ("1", "2", "3"):
                lead["label"] = f"P{answer}"
                PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                break
            print("  invalid, type 1, 2, 3, s, or q")

    labeled_count = sum(1 for lead in leads if lead.get("label"))
    print("-" * 60)
    print(f"Done. {labeled_count}/{len(leads)} leads labeled.")


if __name__ == "__main__":
    main()
