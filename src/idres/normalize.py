"""Field normalization + nickname expansion (the 'NickNames Library' loop)."""
import re

NICKNAMES = {
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
    """Handle 'First Last' and 'Last, First'."""
    full = (full or "").strip()
    if "," in full:
        last, first = [x.strip() for x in full.split(",", 1)]
        return canon_first(first), norm_text(last)
    parts = norm_text(full).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return canon_first(parts[0]), ""
    return canon_first(parts[0]), parts[-1]
