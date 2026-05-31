# Architecture

## Flow

```mermaid
flowchart LR
    U([Data Subject]) -->|DSR: Erase/Remove/Rectify| PW[Privacy Webform UI/UX]
    U -->|SSO submit| SSO[SSO Webform]
    PW -->|authenticate| IDA[ID Authenticator]
    PW -->|Search: name, phone, email| MW
    SSO -->|verify via login| IAM[IAM / Profile]
    subgraph MW[Privacy Middleware]
        IDV[ID Verified API]
        SSOAPI[SSO API]
        NICK[(NickNames Library - loop)]
    end
    MW -->|SearchDataSubject: JWT, name, email, phone| CDB[(Customer DB)]
    NET[(Network/Device DB)] -->|daily pipeline| CDB
    BILL[(Billing/Account DB)] -->|daily pipeline| CDB
    TP[(3rd Party DB)] -->|monthly pipeline| CDB
    IAM -->|profile pipeline| CDB
    CDB -->|Identity Resolution 90% confidence| OUT([Resolved Golden Identity])
```

## Components (code mapping)

| Diagram element | Code |
|---|---|
| NickNames Library loop | `normalize.NICKNAMES`, `canon_first` |
| Field normalization | `normalize.py` (`norm_phone`, `norm_email`, `split_name`) |
| Privacy Middleware / SearchDataSubject | `api.py` `/v1/search-data-subject`, `/v1/dsr` |
| Customer DB fan-in | `loader.build_resolver` loads 4 sources into `Resolver.pool` |
| Identity Resolution (90% confidence) | `engine.score_pair` + `AUTO_MERGE` band |
| Daily/monthly data pipelines | `scripts/generate_data.py` simulates source feeds |

## Matching design

The engine is a transparent probabilistic matcher rather than a black-box model, so
every decision is auditable - a hard requirement in a privacy/compliance context.

**Blocking.** Each record is indexed under several cheap keys: full email, phone
last-4, and a 4-char surname prefix. A query is only scored against records sharing
at least one key, turning an O(n²) cross-join into near-linear lookup.

**Scoring.** Field-level evidence is summed with explicit weights (email and phone
dominate; name and state are supporting signals), capped at 1.0. Weights live in one
dict in `engine.py` and are the primary tuning surface.

**Bands.** Confidence maps to AUTO_MERGE (>= 0.90), REVIEW (0.62-0.90), or NO_MATCH.
The gap between bands is deliberate: the system would rather send a borderline case
to a human than risk a wrong merge.

## Scaling notes

- Blocking keys move to a real index (Elasticsearch / a KV store) at production scale.
- Per-source adapters (`Entity.from_record`) isolate schema differences, so adding a
  source is one branch, not an engine rewrite.
- The learned-matcher upgrade path: keep the same evidence features, replace the
  fixed weights with a trained Fellegi-Sunter or gradient-boosted model, keep the
  band-based decision and the evidence output for explainability.
