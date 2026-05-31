# PRD: Customer Identity Resolution for Privacy DSRs

## Problem

Privacy regulations (CCPA/CPRA, GDPR, state laws) require an operator to action a
Data Subject Request within a fixed window. The hard part is rarely the deletion
itself; it is *finding the subject*. Customer data is fragmented across network,
billing, IAM, and third-party systems, each keyed differently, with nicknames,
typos, and missing fields. A DSR webform yields partial, imperfect identifiers. If
resolution is manual, cost and SLA risk scale with request volume; if it is naive,
the operator either misses records (compliance gap, regulatory exposure) or merges
the wrong people (privacy breach).

## Goal

Resolve an inbound DSR to a single golden customer identity, spanning every source
that holds the subject, with measurable precision and a high straight-through rate
so analysts only touch the ambiguous minority.

## Users

- **Data subject** submits a request via the privacy webform.
- **Privacy analyst** reviews the ambiguous band; should see *why* a match scored
  what it did (evidence breakdown), not a black box.
- **Privacy/compliance lead** owns SLA and audit posture; needs reporting on
  resolution rate, precision, and exceptions.

## Requirements

- Resolve across >= 4 heterogeneous sources with differing keys and quality.
- Tolerate nicknames, name-order variants (`Last, First`), email typos, and missing
  phone/email.
- Emit a confidence and an explainable evidence breakdown per decision.
- Three-band output: auto-merge / review / no-match, with tunable thresholds.
- Never silently merge below the auto threshold (precision protects the subject).
- Sub-linear lookup via blocking; no full cross-join.

## Non-goals

- Real-time streaming ingestion (batch/daily pipelines are assumed, matching the
  diagram's "Data Pipeline (Daily)" edges).
- ML model training; the scoring is transparent and rule-weighted by design so the
  evidence is auditable. A learned matcher is a future option, not v1.

## Success metrics

| Metric | Target | Current (synthetic) |
|---|---|---|
| Auto-merge precision | >= 0.99 | 1.00 |
| Recall | >= 0.85 | 0.89 |
| Straight-through (auto-merge) rate | >= 0.70 | 0.85 |
| p95 resolution latency | < 50 ms | ~4 ms |

Business framing: every percentage point of straight-through processing removes
manual analyst effort per DSR, and high precision avoids the far costlier failure
modes of a missed deletion (regulatory exposure) or a wrong merge (breach).

## Rollout

1. **Shadow** - run resolution alongside the manual process; compare decisions, tune
   weights and thresholds against analyst ground truth.
2. **Assist** - surface the top candidate + evidence to analysts to cut handle time.
3. **Auto** - enable straight-through for the high-confidence band; analysts own the
   review band only.

## Risks & mitigations

- *Wrong merge* -> conservative auto threshold; precision tracked as the primary guardrail.
- *Source drift / schema change* -> per-source adapters isolate parsing (`Entity.from_record`).
- *Bias in name handling* -> nickname library and fuzzy matching are explicit and
  reviewable, not opaque.
