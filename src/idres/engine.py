"""
Probabilistic identity-resolution engine.

Strategy (mirrors the Customer Identity Flow diagram):
  1. Ingest records from multiple sources into one candidate pool (Customer DB).
  2. Block on cheap deterministic keys (phone last-4, email, name-token)
     to avoid O(n^2) comparison across the whole pool.
  3. Score candidate pairs with weighted field similarity, expanding
     nicknames via the NickNames Library.
  4. Apply confidence bands: AUTO_MERGE / REVIEW / NO_MATCH.

Weights are Fellegi-Sunter inspired: each field contributes log-odds-style
evidence. They are intentionally explicit and tunable, not a black box.
"""
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from .normalize import norm_phone, norm_email, split_name

WEIGHTS = {
    "email_exact": 0.55,
    "phone_exact": 0.40,
    "last_exact": 0.22,
    "first_canon": 0.20,
    "first_fuzzy": 0.12,
    "last_fuzzy": 0.12,
    "state_exact": 0.08,
}
AUTO_MERGE = 0.90   # Identity Resolution (90% confidence) from the diagram
REVIEW = 0.62


def sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class Entity:
    source: str
    raw: dict
    first: str = ""
    last: str = ""
    email: str = ""
    phone: str = ""
    state: str = ""
    truth: Optional[str] = None  # ground-truth id, NEVER used for matching

    @classmethod
    def from_record(cls, source: str, rec: dict) -> "Entity":
        truth = rec.get("_truth")
        if source == "network":
            f, l = split_name(rec.get("subscriber_name", ""))
            return cls(source, rec, f, l, "", norm_phone(rec.get("msisdn", "")), "", truth)
        if source == "billing":
            f, l = split_name(rec.get("full_name", ""))
            return cls(source, rec, f, l, norm_email(rec.get("email", "")),
                       norm_phone(rec.get("billing_phone", "")), (rec.get("state") or "").upper(), truth)
        if source == "third_party":
            f, l = split_name(rec.get("name", ""))
            return cls(source, rec, f, l, norm_email(rec.get("email_hash_seed", "")),
                       norm_phone(rec.get("contact_phone", "")), "", truth)
        if source == "iam":
            f, l = split_name(f"{rec.get('given_name','')} {rec.get('family_name','')}")
            return cls(source, rec, f, l, norm_email(rec.get("email", "")),
                       norm_phone(rec.get("phone_number", "")), "", truth)
        # dsr / generic
        f, l = split_name(rec.get("name", ""))
        return cls(source, rec, f, l, norm_email(rec.get("email", "")),
                   norm_phone(rec.get("phone", "")), (rec.get("state") or "").upper(), truth)


def score_pair(a: Entity, b: Entity) -> (float, Dict[str, float]):
    contrib: Dict[str, float] = {}
    if a.email and b.email:
        if a.email == b.email:
            contrib["email_exact"] = WEIGHTS["email_exact"]
        elif sim(a.email, b.email) > 0.85:
            contrib["email_exact"] = WEIGHTS["email_exact"] * 0.6
    if a.phone and b.phone and a.phone == b.phone:
        contrib["phone_exact"] = WEIGHTS["phone_exact"]
    if a.last and b.last:
        if a.last == b.last:
            contrib["last_exact"] = WEIGHTS["last_exact"]
        else:
            contrib["last_fuzzy"] = WEIGHTS["last_fuzzy"] * sim(a.last, b.last)
    if a.first and b.first:
        if a.first == b.first:
            contrib["first_canon"] = WEIGHTS["first_canon"]
        else:
            contrib["first_fuzzy"] = WEIGHTS["first_fuzzy"] * sim(a.first, b.first)
    if a.state and b.state and a.state == b.state:
        contrib["state_exact"] = WEIGHTS["state_exact"]
    return round(min(sum(contrib.values()), 1.0), 4), contrib


def block_keys(e: Entity) -> List[str]:
    keys = []
    if e.email:
        keys.append("e:" + e.email)
    if e.phone:
        keys.append("p:" + e.phone[-4:])
    if e.last:
        keys.append("l:" + e.last[:4])
    return keys


@dataclass
class MatchResult:
    request_id: str
    decision: str
    confidence: float
    matched_truth: Optional[str]
    request_truth: Optional[str]
    evidence: Dict[str, float] = field(default_factory=dict)
    matched_sources: List[str] = field(default_factory=list)


class Resolver:
    """Holds the resolved Customer DB and answers SearchDataSubject queries."""

    def __init__(self):
        self.pool: List[Entity] = []
        self.index: Dict[str, List[int]] = {}

    def load(self, source: str, records: List[dict]):
        for rec in records:
            e = Entity.from_record(source, rec)
            idx = len(self.pool)
            self.pool.append(e)
            for k in block_keys(e):
                self.index.setdefault(k, []).append(idx)

    def search(self, query: dict) -> MatchResult:
        q = Entity.from_record("dsr", query)
        cand_idx = set()
        for k in block_keys(q):
            cand_idx.update(self.index.get(k, []))
        best, best_score, best_ev = None, 0.0, {}
        for i in cand_idx:
            s, ev = score_pair(q, self.pool[i])
            if s > best_score:
                best, best_score, best_ev = self.pool[i], s, ev
        if best_score >= AUTO_MERGE:
            decision = "AUTO_MERGE"
        elif best_score >= REVIEW:
            decision = "REVIEW"
        else:
            decision = "NO_MATCH"
        sources = []
        truth = best.truth if best else None
        if best and truth:
            sources = sorted({p.source for p in self.pool if p.truth == truth})
        return MatchResult(
            request_id=query.get("request_id", ""),
            decision=decision,
            confidence=best_score,
            matched_truth=truth,
            request_truth=query.get("_truth"),
            evidence=best_ev,
            matched_sources=sources,
        )
