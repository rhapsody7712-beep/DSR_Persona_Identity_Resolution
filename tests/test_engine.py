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
    assert split_name("Smith, Bob") == ("robert", "smith")
    assert split_name("Bob Smith") == ("robert", "smith")


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
