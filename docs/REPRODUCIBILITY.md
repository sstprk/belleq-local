# Reproducing the research artifact

There are three separate tasks: running the frozen simulator, rebuilding the
recorded analysis and collecting new physical measurements. None substitutes for
the others. The repository release is v0.2.0; the calibrated model remains v0.1.0.

## 1 Freeze the software and install

Use a separate clone for regeneration because training writes derived files:

```bash
git clone https://github.com/sstprk/belleq-local.git belleq-reproduction
cd belleq-reproduction
git checkout v0.2.0
git rev-parse HEAD
python3.12 scripts/fetch_research_data.py
cd simulator
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
```

The fetcher verifies the release asset and its 89 public inputs. Their checksums
and the original archived checksums are both in `data/source_manifest.json`.
Do not rerun the original acquisition scripts or reconstruct machine paths.
The public input differs only in shortened `source_csv` provenance paths.

## 2 Rebuild the analysis and frozen-test evaluation

```bash
# From simulator/:
PYTHONPATH=src .venv/bin/python -m belleq_sim train
PYTHONPATH=src .venv/bin/python scripts/figures.py
PYTHONPATH=src .venv/bin/python scripts/verify.py
```

The pipeline audits 2,000 main observations, assigns question groups, compares
Ridge with a method-mean baseline, refits calibration, evaluates the frozen test,
validates replay and enumerates derived visit permutations. It saves:

| Output | Expected meaning |
|---|---|
| `data/processed/observations.csv` | 2,000 real attempts plus derived fields and split |
| `artifacts/split.json` | 300 train, 100 validation, 100 held-out test questions |
| `artifacts/calibration.json` | First 400 questions, excluding every test derivative |
| `artifacts/regressors.json` | Selected native-setting point predictors |
| `artifacts/trace_library.json` | Calibration candidate traces, not new search results |
| `results/model_validation.json` | Candidate selection and frozen-test errors, including negative results |
| `results/monte_carlo_validation.csv` | Distribution means/p95 versus 100 unseen questions per method |
| `results/replay_validation.csv` | 1,998 successful historical replays |
| `data/augmented/order_permutations.csv` | 3,000 labeled derived rows, not real extra trials |
| `figures/` | Five PNG/PDF charts with captions and source tables |
| `research/journal.jsonl` | New reproduction-stage records |

Set seed 20261020. Group all policy records and derivatives by `case_id` so the
same question cannot leak across training and test partitions. Hyperparameter
selection uses 300/100 questions and deployed calibration uses the first 400;
the final 100 questions are excluded. Do not repeatedly use the frozen test to
choose another version's hyperparameters.

Ridge uses policy indicators, question UTF-8 byte count and word count only.
Realized hits, visit count, response length and answer length are not predictors.
Alpha candidates are .1, 1, 10, 100 and 1000. A method mean wins for retrieval and
traffic; client-time Ridge is weak. Monte Carlo samples complete records to retain
metric dependence. Mean CIs use 2,000 question-bootstrap repeats; these do not
cover between-session or extrapolation uncertainty.

The plots use 10,000 draws for native validation, 3,000 per virtual-worker setting
and 5,000 per threshold replay. Both line charts consistently use blue stars for
semantic, green squares for broadcast and orange triangles for random order.
The threshold grid spans 0.0 through 1.0 at 0.1 steps. This is replay of saved
top-five candidates, not new ANN searches or generated answers.

## 3 Independently check captured traffic

Install TShark/Wireshark, then from `simulator/`:

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_pcap.py --tshark tshark
```

On macOS the executable may instead be
`/Applications/Wireshark.app/Contents/MacOS/tshark`. The script recomputes all
2,000 coordinator frame-byte windows from the selected two PCAPs. The historical
audit found zero mismatches. This verifies accounting against the capture, not
that every physical wire byte was captured.

The old PCAP's trailing incomplete record was removed in a preserved copy; its
kernel-drop count is unknown. The restarted .70 capture reported zero kernel
drops and all 1,672 worker request/response pairs were matched. Clocks were not
synchronized across hosts; same-host capture/evaluator windows avoid subtracting
unrelated wall clocks. Query windows include generation and possibly late ACKs.

## 4 Rebuild the editable report

The existing report PDF/DOCX and five figures are preserved in
`paper_report_20261022/`. This is the report prepared before public repository
assembly, with the 2026-10-23 visual revision. It describes the original 132-file
private acquisition archive; the publication subset has 89 necessary inputs.

After the previous analysis steps:

```bash
.venv/bin/python -m pip install -r requirements-report.txt
.venv/bin/python paper_report_20261022/build_report.py
```

This regenerates the editable DOCX and extracted tables from the current local
results. Open/export it with Word or LibreOffice to create a new PDF and visually
inspect all pages. The private Codex renderer is not a prerequisite of this public
repo. Do not mistake a rebuilt document timestamp for a new experiment date.

## 5 Collect new hardware data

Follow [lab installation](LAB_SETUP.md) and [the experiment protocol](EXPERIMENTS.md).
Pin model digests and software versions, preserve canonical content and record
the actual interface/link speeds. The provided categorical configs are deployment
recipes; private per-machine acquisition settings are not silently recreated.

Exact old latency, embedding weights behind mutable tags, ANN layouts, host caches
and session conditions are not guaranteed by this archive. Regeneration of the
saved analysis is supported independently of those external model downloads.
Physical scaling beyond the measured one/three-worker settings, random chunk
placement and concurrent-load behavior require new experiments.

## 6 Archive a journal version

Use the release tag, commit and asset checksum in code/data availability statements.
Do not cite a moving branch as an immutable artifact. GitHub releases do not create
a DOI; archive the reviewed release with Zenodo or another appropriate repository
and add its actual DOI to `CITATION.cff` once assigned. Confirm the publication
author list separately; the current software citation credits the contributors
collectively and does not invent a paper title, acceptance or DOI.
