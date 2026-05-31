import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from idres.engine import Resolver, Entity, score_pair  # noqa: E402
from idres.normalize import canon_first, norm_phone, split_name  # noqa: E402


def test_nickname_canonicalization():
    assert canon_first("Bob") == "robert"
    assert canon_first("Jim") == "james"
    assert canon_first("Liz") == "elizabeth"


def test_phone_normalization():
    assert norm_phone("+1 (425) 633-6071") == "4256336071"


def test_name_split_variants():
    assert split_name("Smith, Bob") == ("robert", "smith", "")
    assert split_name("Bob Smith") == ("robert", "smith", "")


def test_middle_name_extraction():
    assert split_name("Mary Ann Gonzalez") == ("mary", "gonzalez", "ann")
    assert split_name("Smith, Mary Ann") == ("mary", "smith", "ann")
    # trailing suffix must not be mistaken for the surname
    assert split_name("Robert James Smith Jr") == ("robert", "smith", "james")


def test_middle_match_scoring():
    from idres.normalize import middle_match
    assert middle_match("ann", "ann") == 1.0
    assert middle_match("ann", "a") == 0.7      # initial vs full
    assert middle_match("ann", "beth") == -1.0  # active disagreement
    assert middle_match("ann", "") == 0.0       # absence is not evidence


def test_feedback_learns_then_resolves():
    import os
    from idres import normalize, feedback
    # clean slate
    for p in (feedback.ACTIVE, feedback.PROPOSALS):
        if p.exists():
            os.remove(p)
    normalize.reload_nicknames()
    ev = {"email_exact": 0.55, "last_exact": 0.22}
    assert normalize.canon_first("Kate") == "kate"
    r1 = feedback.confirm_match("Kate", "Katherine", ev, "analyst_A")
    assert r1["status"] == "staged"
    r2 = feedback.confirm_match("Kate", "Katherine", ev, "analyst_B")
    assert r2["status"] == "promoted" and r2["learned"]
    assert normalize.canon_first("Kate") == "katherine"


def test_feedback_rejects_non_nickname_gap():
    import os
    from idres import normalize, feedback
    for p in (feedback.ACTIVE, feedback.PROPOSALS):
        if p.exists():
            os.remove(p)
    normalize.reload_nicknames()
    # first names already matched exactly -> nothing to learn
    ev = {"email_exact": 0.55, "first_canon": 0.20, "last_fuzzy": 0.09}
    assert not feedback.confirm_match("John", "John", ev, "A")["learned"]
    # no strong identifier carried the match -> refuse to learn
    ev2 = {"last_exact": 0.22, "first_fuzzy": 0.06}
    res = feedback.confirm_match("Kate", "Katherine", ev2, "A")
    assert res["status"] == "gap_not_first_name"


def test_exact_email_phone_auto_merges():
    a = Entity.from_record("dsr", {"name": "Bob Smith", "email": "b@x.com", "phone": "4250000000"})
    b = Entity.from_record("billing", {"full_name": "Robert Smith", "email": "b@x.com",
                                       "billing_phone": "4250000000", "state": "WA"})
    score, _ = score_pair(a, b)
    assert score >= 0.90


def test_name_only_lands_in_review_band_not_auto():
    a = Entity.from_record("dsr", {"name": "Bob Smith"})
    b = Entity.from_record("billing", {"full_name": "Robert Smith"})
    score, _ = score_pair(a, b)
    assert 0.30 <= score < 0.90


def test_resolver_blocking_returns_match():
    r = Resolver()
    r.load("billing", [{"account_id": "A1", "full_name": "Jim Jones",
                        "email": "jim@x.com", "billing_phone": "4251112222",
                        "state": "WA", "_truth": "p1"}])
    res = r.search({"request_id": "D1", "name": "James Jones",
                    "email": "jim@x.com", "phone": "4251112222", "_truth": "p1"})
    assert res.decision == "AUTO_MERGE"
    assert res.matched_truth == "p1"
