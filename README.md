# MicroVerse

A scientific desktop platform for **microbiology simulation, prediction and visualization**, in English and Arabic.
Workflow: *Hypothesis → Prediction → Visualization → Explanation → Laboratory validation → Model improvement.*

## Run
Double-click `MicroVerse.bat`, or:
```bash
.venv/Scripts/python -m microverse.ui.app
```
Tests: `.venv/Scripts/python -m pytest -q` · Screenshots: `.venv/Scripts/python scripts/ui_smoke.py`
On another PC: `python -m venv .venv` then `.venv/Scripts/pip install -r requirements.txt`.

## How to use it
1. **Start screen** — choose a lab, a ready-made community, or build your own from 2–5 organisms.
2. **Scenario** — each one is a research question.
3. **In the lab** — parameters on the left (the coloured dot shows how trustworthy each value is), microscope view
   and graphs in the middle, and the **"Why?"** panel on the right with everything the model computed.
4. **Measure interactions** (community labs) — re-runs each organism alone and each pair together to find out who
   helps or harms whom, and why.
5. **Freeze prediction** — stores the prediction permanently *before* you do the real experiment.
6. **Language** — switch English / العربية at the top of the start screen.

## Labs
| Lab | What it is | Status |
|---|---|---|
| Chemostat Microcosm | *Chlorella* + *Brachionus* predator–prey in a diluted vessel | Mechanistic; literature parameters pending source check |
| Yoghurt Fermentation | *S. thermophilus* + *L. bulgaricus* in milk | Exploratory; illustrative parameters |
| Community Builder | Any 2–5 organisms from the database, 9 presets | Exploratory; traits are textbook estimates |

## What each organism does
- **Library → By Function**: 20 functions explained (what it means, how the simulation represents it, what to try),
  each listing the organisms that perform it.
- **Library → By Organism**: every card starts with coloured function chips and a "What it does" table.
- **Who's Who** tab inside every lab: the organisms in that lab and what their traits predict between them.
- **Printable guide (PDF)** and **spreadsheet (CSV)** from the Library, in English or Arabic.

## Organism database
30 organisms, all biosafety level 1. Every record drives both the library card (classification, NCBI Taxonomy ID,
size, shape, metabolism, reproduction, role, uses, references — English and Arabic) and the simulation
(growth rate, half-saturation, yield, cardinal temperature and pH, oxygen requirement, substrates, products,
enzyme activity, grazing limits). It is also stored in SQLite (`data/microverse.sqlite`: tables `organism_db`,
`functions`, `organism_functions`), rebuilt at every start or with `scripts/build_database.py`.

## Scientific status
Equations **verified** by 76 automated tests. **No model is validated** against laboratory data yet.
See `docs/VERIFICATION_VS_VALIDATION.md`.

## Docs
`docs/ARCHITECTURE.md` · `docs/MILESTONE_1.md` · `docs/models/` (chemostat, yogurt, community) ·
`docs/RESEARCH_IDEAS.md` (أفكار بحثية) · `ROADMAP.md` · `CHANGELOG.md`
