# Quick pre-launch check: {{APP NAME}}

Checked: {{DATE}} · URL: {{URL}} · Pages: {{n}} · Devices: desktop + mobile

## Verdict
{{"Looks ready" / "Fix the high items before launch" / "Not ready: core pages are broken"}}
{{1–2 plain-English sentences.}}

## Findings

### {{ID}} · {{High / Medium / Low}} · {{Short title users would understand}}
**Where:** {{page}} ({{desktop / mobile / both}})
**What happens:** {{plain-English description and who it affects}}
**Evidence:** {{screenshot path or error text}}

**Fix prompt** (paste into your AI builder):
```
{{Specific, self-contained instruction: what's wrong, what correct behaviour looks like,
how to verify the fix. One bug per prompt.}}
```

(repeat for each finding)

## Re-run
```
python scripts/smoke_crawl.py {{URL}} --out qa-results
```

---
High = crashes or core pages broken · Medium = wrong or broken for some users/devices · Low = polish.
This quick check covers page loading and display only. Forms, user journeys and security
were not tested.
