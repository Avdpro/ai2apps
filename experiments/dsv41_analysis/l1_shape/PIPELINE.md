# Reproducible L1 shape study

Final execution scope: the user reduced the 240-run performance evaluation to five cases × four runs after eleven completed runs. `limited.py` reuses those results and completes the frozen twenty-run selection; `limited_report.py` performs the reduced final audit and writes the report. The result retains Main40 as default and makes no full statistical adoption claim. Do not restart `pipeline.py`, `evaluate.py`, `retest.py`, or the original full-scope `audit.py` merely to reproduce the completed small study. `pipeline.json` retains the intentional interruption and links to `limited-state.json`.

Run from repository root using `.venv/bin/python`. Only one GPU process at a time.

1. `experiments/dsv41_analysis/l1_shape/dataset.py` freezes the dataset once.
2. `experiments/dsv41_analysis/l1_shape/batch.py pilot`
3. `experiments/dsv41_analysis/l1_shape/batch.py calibrate` checks 20 cases × 3 capacities, 128 steps each. Reads and physical destinations must match replay.
4. `experiments/dsv41_analysis/l1_shape/batch.py collect` captures the 300 frozen samples once at Main40 (completed samples reused).
5. `experiments/dsv41_analysis/l1_shape/fit.py` fits train only, selects on validation route costs and freezes the candidate before held-out A/B.
6. `experiments/dsv41_analysis/l1_shape/qualify.py` checks both languages at approximately 4096 input tokens and 512 Decode steps with full logits, runs paired F_NOCACHE controls, and verifies four-turn persistent incremental sessions across the attention window.
7. `experiments/dsv41_analysis/l1_shape/evaluate.py` runs 60 held-out cases × 2 variants × 2 repetitions, AB/BA, no collector.
8. `experiments/dsv41_analysis/l1_shape/report.py` computes all cases and fixed gates. `retest.py` repeats every >5% case regression twice per variant without retuning; run `report.py` again to include every repetition.
9. `experiments/dsv41_analysis/l1_shape/write_report.py` renders the report and allocation chart only after required outputs exist. Review the result and update the execution plan and release ledger.

`pipeline.py` executes steps 2–9 in order and records failures in `pipeline.json`. Dataset creation is separate and must not overwrite the frozen manifest during a resumed study.

Every command is resumable except dataset creation (intentionally frozen). A failed run is never silently reused. Diagnose and archive a failed directory before retry. SHA256 hashes of all Float32-expanded logits provide bitwise equality checks without retaining massive full-logit files. On a mismatch, retain full logits in an explicit diagnostic rerun and halt adoption.

Long synthetic notebooks share topic family identity with their short parent, hence no cross-split leakage. They qualify input length handling, not a claim of production domain coverage. Cross-topic composites are retained in audit but excluded from fitting because they connect otherwise separated task families. Generic instruction templates are shared; subject matter and translations are grouped. Old sample IDs retain their original split name for provenance; `split` in the frozen manifest is authoritative.

Main40 stays default. The final shape has 1600 total slots, Hot8 per layer; no global mobile pool and no predicted L2. Native loader safety fences remain unchanged.

Route collection may run alongside checkpoint uploads: its TPS is diagnostic only. Pilot/calibration and acceptance measurements pause identified task-owned uploads and restore them in finally.
