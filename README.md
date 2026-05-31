# Customer Identity Resolution for Privacy DSRs

A reference implementation of a **probabilistic identity-resolution engine** that
powers Data Subject Requests (DSR: erase / remove / rectify / access) across
fragmented customer data sources. It resolves a single inbound privacy request to
one golden customer identity by fusing records from multiple databases, even when
the request provides only partial or imperfect identifiers.

This repo productizes the workflow in the architecture diagram below: a DSR enters
through a privacy webform, passes through middleware that authenticates and
searches the data subject, and resolves against a Customer DB assembled from
Network/Device, Billing, IAM/Profile, and 3rd-party sources.

> Synthetic data only. Nothing here is derived from any employer's systems. The
> generator produces randomized records that recreate the *shape* of the problem
> (nicknames, typos, missing fields, multi-source fan-in) so the engine and its
> results are reproducible by anyone.

## Results (synthetic, reproducible)

Run `python scripts/benchmark.py` to regenerate these numbers.

| Metric | Value | What it means |
|---|---|---|
| **Precision** | **1.00** | Resolved matches are correct; no wrong identities merged |
| **Recall** | **0.89** | Share of true subjects successfully resolved |
| **F1** | **0.94** | Balanced accuracy |
| **Auto-merge rate** | **85%** | Straight-through processing, no human in the loop |
| **Auto-merge precision** | **1.00** | Every auto-merged decision was correct |
| **Avg sources fused / subject** | **3.6** | Identity stitched across multiple DBs |
| **Latency** | **~3.8 ms / request** | Blocking keeps it sub-linear, not O(n²) |
| Customer DB size | 1,780 records | Fanned in from 4 sources |

Decisions are split into three confidence bands: **AUTO_MERGE** (>= 0.90,
the "90% confidence" target), **REVIEW** (0.62-0.90, routed to a privacy analyst),
and **NO_MATCH** (< 0.62, insufficient evidence).

## How it works

1. **Ingest & normalize** every source into a common entity (phone digits, lowercased
   email, split names).
2. **Nickname expansion** maps `Bob -> robert`, `Liz -> elizabeth`, etc. This is the
   *NickNames Library loop* from the diagram.
3. **Blocking** indexes each record by cheap keys (email, phone last-4, name prefix)
   so a query only compares against plausible candidates.
4. **Weighted scoring** combines field-level evidence (Fellegi-Sunter inspired,
   tunable weights in `engine.py`) into a single confidence in `[0, 1]`.
5. **Banded decision** turns confidence into an action: auto-merge, route to review,
   or no match. A resolved subject returns every source it spans, enabling a complete
   erase/access action.

## Quick start

```bash
pip install -r requirements.txt
python scripts/generate_data.py     # synthetic multi-source data
python scripts/benchmark.py         # measured results -> results/benchmark.json
pytest -q                           # tests

# Run the API
uvicorn idres.api:app --app-dir src --reload
curl -X POST localhost:8000/v1/dsr -H 'content-type: application/json' \
  -d '{"request_type":"ERASE","name":"Bob Smith","email":"bob.smith@gmail.com"}'
```

## Repo layout

```
src/idres/        engine, normalization, loader, FastAPI service
scripts/          data generation + benchmark
data/             generated synthetic sources (gitignored after first run)
results/          benchmark output
docs/             PRD and architecture
tests/            unit + integration tests
```

## Docs

- [`docs/PRD.md`](docs/PRD.md) - product requirements, users, metrics, rollout
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - system design and the flow diagram

## License

Apache-2.0.
