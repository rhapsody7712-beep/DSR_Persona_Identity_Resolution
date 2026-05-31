"""
FastAPI service mirroring the Privacy Middleware in the Customer Identity Flow.

Endpoints:
  POST /v1/search-data-subject   -> resolve a DSR against the Customer DB
  POST /v1/dsr                    -> resolve + return an actionable DSR plan
  GET  /v1/health
  GET  /v1/stats
"""
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from idres.loader import build_resolver
from idres.feedback import confirm_match

app = FastAPI(title="Customer Identity Resolution", version="1.0.0")
RESOLVER = build_resolver()


class SubjectQuery(BaseModel):
    request_id: Optional[str] = None
    name: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    state: Optional[str] = ""
    country: Optional[str] = "US"


class DSRQuery(SubjectQuery):
    request_type: str = "ACCESS"  # ERASE | REMOVE | RECTIFY | ACCESS


class MatchOut(BaseModel):
    decision: str
    confidence: float
    matched_sources: List[str]
    evidence: dict


@app.get("/v1/health")
def health():
    return {"status": "ok", "customer_db_records": len(RESOLVER.pool)}


@app.get("/v1/stats")
def stats():
    by_source = {}
    for e in RESOLVER.pool:
        by_source[e.source] = by_source.get(e.source, 0) + 1
    return {"records_by_source": by_source, "total": len(RESOLVER.pool)}


@app.post("/v1/search-data-subject", response_model=MatchOut)
def search(q: SubjectQuery):
    r = RESOLVER.search(q.model_dump())
    return MatchOut(decision=r.decision, confidence=r.confidence,
                    matched_sources=r.matched_sources, evidence=r.evidence)


@app.post("/v1/dsr")
def dsr(q: DSRQuery):
    r = RESOLVER.search(q.model_dump())
    actionable = r.decision == "AUTO_MERGE"
    plan = {
        "ERASE": "Tombstone subject across all fused sources; emit deletion receipts.",
        "REMOVE": "Suppress subject from active processing; retain legal-hold only.",
        "RECTIFY": "Open correction workflow on golden record; propagate downstream.",
        "ACCESS": "Compile data export across all fused sources for subject.",
    }.get(q.request_type, "Manual triage.")
    return {
        "request_type": q.request_type,
        "decision": r.decision,
        "confidence": r.confidence,
        "auto_actionable": actionable,
        "matched_sources": r.matched_sources,
        "evidence": r.evidence,
        "next_action": plan if actionable else "Route to privacy analyst for review.",
    }


class FeedbackIn(BaseModel):
    request_name: str        # first name (or full name) from the inbound request
    matched_name: str        # first name (or full name) from the matched record
    evidence: dict           # the evidence breakdown from the original search
    analyst_id: str = "analyst"


@app.post("/v1/feedback")
def feedback(f: FeedbackIn):
    """Record an analyst's confirmation of a REVIEW-band match. May stage or
    promote a learned nickname pair, which improves future resolutions."""
    return confirm_match(f.request_name, f.matched_name, f.evidence, f.analyst_id)
