"""Load synthetic source data into a Resolver (the Customer DB fan-in)."""
import csv
import json
from pathlib import Path

from .engine import Resolver

DATA = Path(__file__).resolve().parent.parent.parent / "data"


def read_csv(name):
    with open(DATA / name) as f:
        return list(csv.DictReader(f))


def read_json(name):
    with open(DATA / name) as f:
        return json.load(f)


def build_resolver() -> Resolver:
    r = Resolver()
    r.load("network", read_csv("network_device_db.csv"))
    r.load("billing", read_csv("billing_account_db.csv"))
    r.load("third_party", read_csv("third_party_db.csv"))
    r.load("iam", read_csv("iam_profile.csv"))
    return r


def load_dsr():
    return read_json("dsr_requests.json")
