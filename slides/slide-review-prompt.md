# Prompt: review whether the workshop slide deck needs updating

Copy everything in the fenced block below into your other session (Claude Fable5)
that has this repository checked out with shell access.

---

````text
You are reviewing the slide deck for the "Microsoft Foundry Evaluations" workshop
in this repository. Your job is to decide whether the deck needs updating to match
the current state of the repo, and if so, to PROPOSE concrete slide edits. Do NOT
edit the binary .pptx yourself — deliver your recommendations as text/markdown.

## Repository context (read these first, in this order)
1. `README.md` — repo overview and structure.
2. `docs/facilitator-guide.md` — the delivery source of truth (four-module arc,
   talk tracks, appendices). The deck mirrors this.
3. `docs/gxp-extension.md` — the pharma/life-sciences GxP delivery variant.
4. `docs/gxp-disciplines.md` — **the newest content**: expands the GxP variant into
   four discipline tracks (GMP / GLP / GCP / GDP).
5. `lab/README.md` and the `lab/` scripts (esp. `create_agent_*.py`,
   `run_cloud_eval.py`, `generate_synthetic_dataset.py`).
6. `examples/` (CI/CD gates) and `git log --oneline -15`.

The content baseline is **July 2026** (post-Build 2026): trace-based evaluation,
the Rubric evaluator (preview), and Agent Optimizer. Keep GA/preview feature
labels consistent with that baseline — do NOT silently upgrade or downgrade a
feature's status. If unsure about a feature's GA/preview status or any regulatory
claim, verify against Microsoft Learn (`learn.microsoft.com`) before asserting it.

## The deck
`slides/foundry-evals-workshop-deck.pptx` — a 21-slide PowerPoint (single slide
layout, every slide has speaker notes). Extract its text yourself so you review the
real content, not an assumption:

```bash
python3 - <<'PY'
import zipfile, re
z = zipfile.ZipFile("slides/foundry-evals-workshop-deck.pptx")
slides = sorted([n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
                key=lambda n: int(re.search(r"(\d+)", n).group(1)))
for n in slides:
    xml = z.read(n).decode("utf-8", "ignore")
    texts = [t for t in re.findall(r"<a:t>(.*?)</a:t>", xml) if t.strip()]
    num = re.search(r"(\d+)", n).group(1)
    print(f"--- slide {num} ---")
    print(" | ".join(texts))
# speaker notes live in ppt/notesSlides/notesSlideN.xml if you want them too
PY
```

### Current slide map (as of this prompt — re-verify against your extraction)
- 1 Title · 2 Agenda (four modules, two labs)
- 3–8 Module 1 (why evals matter, the loop, evaluator taxonomy, system vs process,
  LLM-as-judge, targets & execution surfaces)
- 9–10 Lab 1 (portal then SDK; data-mapping syntax)
- 11 Lab 2 (live agent, custom evaluators, trace-based demo)
- 12 Module 3 — trace-based evaluation (the Build 2026 shift)
- 13–15 Module 4 (CI/CD gate, continuous evaluation, the trust-stack map)
- **16–20 OPTIONAL GxP delivery variant** (16 regulatory anchors, 17 pillar
  mapping, 18 synthetic datasets, 19 scenario & limits, **20 the four discipline
  tracks — GMP/GLP/GCP/GDP**)
- 21 Five things to take home

## The specific thing to check hardest
The most recent repo change added **four GxP discipline tracks** — GMP
(manufacturing), GLP (lab / product testing), GCP (clinical studies), GDP (supply
chain / distribution) — see `docs/gxp-disciplines.md`,
`lab/create_agent_{gmp,glp,gcp,gdp}.py`, `lab/dataset_{gmp,glp,gcp,gdp}_sample.jsonl`,
and the `--discipline` flag on `generate_synthetic_dataset.py`.

As of this deck version, the GxP module was **just updated** to cover the four
disciplines: slide 18 now mentions `--discipline {gmp,glp,gcp,gdp}`, slide 19
points to the discipline tracks, and a new **slide 20** ("FOUR DISCIPLINES")
summarizes GMP/GLP/GCP/GDP against the shared 5-category matrix. Verify that this
new content is:
- accurate and consistent with `docs/gxp-disciplines.md` and the lab scripts,
- correctly styled/ordered (takeaways must remain the final slide), and
- not over- or under-claiming any feature status vs the July 2026 baseline.

Also do a broader accuracy pass: does every slide still match the facilitator
guide and lab scripts (evaluator names, `run_cloud_eval.py` behaviour, the
data-mapping syntax `{{item.X}}` / `{{sample.output_text}}` / `{{sample.output_items}}`,
CI/CD gate task name, feature-status labels)? Note anything stale.

## Deliverable (produce all three)
1. **Verdict** — one line: does the deck need updating? (yes / no / minor).
2. **Per-slide findings table** — columns: slide #, current gist, issue found (or
   "OK"), severity (blocker / should-fix / nice-to-have).
3. **Proposed edits** — for each slide you'd change: the new/edited title, the
   exact bullet text, and speaker-notes text, in markdown ready to hand to whoever
   edits the .pptx. If you recommend a NEW slide, give its position and full
   content. Keep the deck's terse, punchy style (short headline + a few
   substantive bullets).

## Constraints
- Do not edit `slides/foundry-evals-workshop-deck.pptx` — propose only.
- Don't invent Foundry features or regulatory claims; ground every assertion in a
  repo file or a Microsoft Learn page, and cite it.
- Keep the July 2026 baseline; don't change GA/preview labels without a Learn cite.
- Keep proposals consistent with `docs/facilitator-guide.md` (the source of truth)
  and with `docs/gxp-disciplines.md`.
````
