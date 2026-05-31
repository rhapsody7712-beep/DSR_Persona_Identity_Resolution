"""
Human-in-the-loop learning for the NickNames Library.

When a privacy analyst confirms that a REVIEW-band candidate is the same person,
this module decides what (if anything) the system should learn. It does NOT blindly
pair the two first names: it inspects the evidence so it only proposes a nickname
when a first-name disagreement was the actual gap, and it requires repeated
confirmation before a pair is promoted into the active library. Everything is
written with provenance so a learned mapping can be audited or rolled back.

Files (under data/):
  nicknames.json          active learned pairs, merged on top of the seed library
  nickname_proposals.json  staged pairs awaiting enough confirmations + audit log
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .normalize import norm_text, NICKNAMES, reload_nicknames

DATA = Path(__file__).resolve().parent.parent.parent / "data"
ACTIVE = DATA / "nicknames.json"
PROPOSALS = DATA / "nickname_proposals.json"

PROMOTE_AT = 2  # distinct confirmations required before a pair goes live


def _read(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return default
    return default


def _write(path, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def _is_first_name_gap(evidence: dict) -> bool:
    """A nickname is only the right lesson when the first name failed to match
    exactly while strong identifiers (email or phone) carried the match."""
    strong = ("email_exact" in evidence) or ("phone_exact" in evidence)
    first_matched_exactly = "first_canon" in evidence
    return strong and not first_matched_exactly


def confirm_match(request_name: str, matched_name: str, evidence: dict,
                  analyst_id: str = "analyst") -> dict:
    """Record an analyst confirmation. Returns what the system learned, if anything.

    request_name / matched_name are the raw first names (or first tokens) from the
    two records the analyst confirmed as one person.
    """
    a = norm_text(request_name).split()
    b = norm_text(matched_name).split()
    a = a[0] if a else ""
    b = b[0] if b else ""

    result = {"learned": False, "status": "no_action", "pair": None}

    if not a or not b or a == b:
        result["status"] = "names_already_equal"
        return result
    if not _is_first_name_gap(evidence):
        # The gap was something else (typo'd surname, stale phone). Not a nickname.
        result["status"] = "gap_not_first_name"
        return result
    # Already known?
    if NICKNAMES.get(a) == b or NICKNAMES.get(b) == a:
        result["status"] = "already_known"
        return result

    # Canonical direction: map the shorter form to the longer (nickname -> legal).
    nick, canon = (a, b) if len(a) <= len(b) else (b, a)
    key = f"{nick}->{canon}"

    proposals = _read(PROPOSALS, {})
    entry = proposals.get(key, {"nick": nick, "canon": canon,
                                "confirmations": 0, "by": [], "log": []})
    entry["confirmations"] += 1
    if analyst_id not in entry["by"]:
        entry["by"].append(analyst_id)
    entry["log"].append({"at": datetime.now(timezone.utc).isoformat(),
                         "analyst": analyst_id})
    proposals[key] = entry
    _write(PROPOSALS, proposals)

    # Promote on enough DISTINCT confirmers (guards against one analyst's error).
    if len(entry["by"]) >= PROMOTE_AT:
        active = _read(ACTIVE, {})
        active[nick] = canon
        _write(ACTIVE, active)
        reload_nicknames()
        result.update(learned=True, status="promoted", pair=[nick, canon])
    else:
        result.update(status="staged", pair=[nick, canon],
                      confirmations=len(entry["by"]), needed=PROMOTE_AT)
    return result
