"""Field normalization + nickname expansion (the 'NickNames Library' loop).

The nickname library is seeded with common pairs and then loaded from
data/nicknames.json if present, so the human-feedback loop (feedback.py) can
extend it persistently across runs.
"""
import json
import re
from pathlib import Path

_SEED_NICKNAMES = {
    "jim": "james", "jamie": "james",
    "bob": "robert", "rob": "robert", "bobby": "robert",
    "will": "william", "bill": "william", "billy": "william",
    "rick": "richard", "dick": "richard", "rich": "richard",
    "mike": "michael", "mikey": "michael",
    "joe": "joseph", "joey": "joseph",
    "tom": "thomas", "tommy": "thomas",
    "chris": "christopher",
    "dan": "daniel", "danny": "daniel",
    "liz": "elizabeth", "beth": "elizabeth", "eliza": "elizabeth",
    "jen": "jennifer", "jenny": "jennifer",
    "pat": "patricia", "patty": "patricia", "tricia": "patricia",
    "jess": "jessica", "sue": "susan", "susie": "susan", "barb": "barbara",
}

_NICK_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "nicknames.json"

# Name suffixes that should never be treated as a surname.
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _load_nicknames() -> dict:
    table = dict(_SEED_NICKNAMES)
    if _NICK_FILE.exists():
        try:
            learned = json.loads(_NICK_FILE.read_text())
            table.update({k.lower(): v.lower() for k, v in learned.items()})
        except (json.JSONDecodeError, OSError):
            pass
    return table


NICKNAMES = _load_nicknames()


def reload_nicknames():
    """Re-read the persisted library (call after feedback writes to it)."""
    global NICKNAMES
    NICKNAMES = _load_nicknames()
    return NICKNAMES


def norm_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def canon_first(name: str) -> str:
    n = norm_text(name)
    return NICKNAMES.get(n, n)


def norm_phone(p: str) -> str:
    if not p:
        return ""
    d = re.sub(r"\D", "", p)
    return d[-10:] if len(d) >= 10 else d


def norm_email(e: str) -> str:
    return e.strip().lower() if e else ""


def split_name(full: str):
    """Parse a name into (first, last, middle).

    Handles:
      - 'First Last'                       -> (first, last, '')
      - 'First Middle Last'                -> (first, last, middle)
      - 'First M. Last' / 'F. Robert Last' -> initials kept as single letters
      - 'Last, First Middle'               -> reordered correctly
      - trailing suffixes (Jr, Sr, III)    -> stripped, not treated as surname

    First name is canonicalized through the nickname library.
    """
    full = (full or "").strip()

    if "," in full:
        last_part, rest = [x.strip() for x in full.split(",", 1)]
        last = norm_text(last_part)
        given = [g for g in norm_text(rest).split() if g not in _SUFFIXES]
        if not given:
            return "", last, ""
        first = canon_first(given[0])
        middle = " ".join(given[1:])
        return first, last, middle

    parts = [p for p in norm_text(full).split() if p not in _SUFFIXES]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return canon_first(parts[0]), "", ""

    first = canon_first(parts[0])
    last = parts[-1]
    middle = " ".join(parts[1:-1])
    return first, last, middle


def middle_match(a: str, b: str) -> float:
    """Compatibility score for two middle-name strings in [-1, 1].

    - either empty          -> 0.0 (absence is not evidence either way)
    - exact first token      -> 1.0
    - initial vs full name   -> 0.7 ('a' vs 'ann')
    - mismatch               -> -1.0 (active disagreement: ann vs beth)
    """
    if not a or not b:
        return 0.0
    x, y = a.split()[0], b.split()[0]
    if x == y:
        return 1.0
    if (len(x) == 1 or len(y) == 1) and x[0] == y[0]:
        return 0.7
    return -1.0
