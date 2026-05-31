"""
Generate synthetic, multi-source customer records that mimic the fan-in
shown in the Customer Identity Flow: Network/Device DB, Billing/Account DB,
3rd-Party DB, IAM/Profile, plus inbound DSR (Data Subject Request) records.

No real customer data. Everything here is randomly generated and safe to publish.
"""
import csv
import json
import random
import os
import uuid
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
         "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
         "Joseph", "Jessica", "Thomas", "Sarah", "Chris", "Karen", "Daniel", "Nancy"]
# Common nicknames -> canonical, used to inject the "NickNames Library" loop case
NICK = {
    "James": ["Jim", "Jamie"], "Robert": ["Bob", "Rob", "Bobby"],
    "William": ["Will", "Bill", "Billy"], "Richard": ["Rick", "Dick", "Rich"],
    "Michael": ["Mike", "Mikey"], "Joseph": ["Joe", "Joey"],
    "Thomas": ["Tom", "Tommy"], "Christopher": ["Chris"],
    "Daniel": ["Dan", "Danny"], "Elizabeth": ["Liz", "Beth", "Eliza"],
    "Jennifer": ["Jen", "Jenny"], "Patricia": ["Pat", "Patty", "Tricia"],
    "Jessica": ["Jess"], "Susan": ["Sue", "Susie"], "Barbara": ["Barb"],
}
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
STATES = ["WA", "CA", "TX", "NY", "FL", "IL", "OR", "AZ", "CO", "GA"]
DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "proton.me"]

N_IDENTITIES = 500


def make_phone():
    return f"{random.randint(200,989)}{random.randint(200,989)}{random.randint(1000,9999)}"


def typo(s):
    """Inject a realistic transcription error into a string."""
    if len(s) < 3:
        return s
    i = random.randint(1, len(s) - 2)
    ops = [
        s[:i] + s[i + 1:],                       # drop a char
        s[:i] + s[i] + s[i] + s[i:],             # double a char
        s[:i] + random.choice("abcdefghijklmnopqrstuvwxyz") + s[i + 1:],  # swap
    ]
    return random.choice(ops)


def make_email(first, last):
    sep = random.choice([".", "_", ""])
    num = random.choice(["", "", str(random.randint(1, 99))])
    return f"{first.lower()}{sep}{last.lower()}{num}@{random.choice(DOMAINS)}"


def build():
    identities = []
    for _ in range(N_IDENTITIES):
        first = random.choice(FIRST)
        last = random.choice(LAST)
        identities.append({
            "person_id": str(uuid.uuid4()),
            "first": first,
            "last": last,
            "email": make_email(first, last),
            "phone": make_phone(),
            "state": random.choice(STATES),
            "country": "US",
        })

    network, billing, third_party, iam = [], [], [], []

    for p in identities:
        # Network/Device DB: phone is primary, name often abbreviated/nickname
        disp_first = p["first"]
        if p["first"] in NICK and random.random() < 0.55:
            disp_first = random.choice(NICK[p["first"]])
        network.append({
            "device_id": "DEV-" + uuid.uuid4().hex[:10],
            "msisdn": p["phone"],
            "subscriber_name": f"{disp_first} {p['last']}",
            "imei": str(random.randint(10**14, 10**15 - 1)),
            "_truth": p["person_id"],
        })

        # Billing/Account DB: legal name + email, sometimes typo'd email
        email = p["email"]
        if random.random() < 0.15:
            local, dom = email.split("@")
            email = typo(local) + "@" + dom
        billing.append({
            "account_id": "ACC-" + uuid.uuid4().hex[:8],
            "full_name": f"{p['first']} {p['last']}",
            "email": email,
            "billing_phone": p["phone"] if random.random() < 0.8 else make_phone(),
            "state": p["state"],
            "_truth": p["person_id"],
        })

        # 3rd-Party DB: lower quality, monthly pipeline, missing fields, noise
        if random.random() < 0.7:
            tp_email = p["email"] if random.random() < 0.6 else ""
            tp_phone = p["phone"] if random.random() < 0.5 else ""
            third_party.append({
                "vendor_ref": "TP-" + uuid.uuid4().hex[:8],
                "name": f"{p['first']} {p['last']}" if random.random() < 0.85
                        else f"{p['last']}, {p['first']}",
                "email_hash_seed": tp_email,
                "contact_phone": tp_phone,
                "_truth": p["person_id"],
            })

        # IAM/Profile: SSO verified identity, JWT subject
        if random.random() < 0.85:
            iam.append({
                "sub": "jwt|" + uuid.uuid4().hex,
                "given_name": p["first"],
                "family_name": p["last"],
                "email": p["email"],
                "phone_number": p["phone"],
                "email_verified": random.random() < 0.9,
                "_truth": p["person_id"],
            })

    def dump_csv(rows, name):
        path = DATA_DIR / name
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    dump_csv(network, "network_device_db.csv")
    dump_csv(billing, "billing_account_db.csv")
    dump_csv(third_party, "third_party_db.csv")
    dump_csv(iam, "iam_profile.csv")

    # DSR inbound requests: a sample of people submit erase/rectify/access asks,
    # using partial / imperfect identifiers (what a real privacy webform yields)
    dsr = []
    for p in random.sample(identities, 120):
        provide_email = random.random() < 0.8
        provide_phone = random.random() < 0.7
        name_first = p["first"]
        if p["first"] in NICK and random.random() < 0.4:
            name_first = random.choice(NICK[p["first"]])
        dsr.append({
            "request_id": "DSR-" + uuid.uuid4().hex[:8],
            "request_type": random.choice(["ERASE", "REMOVE", "RECTIFY", "ACCESS"]),
            "name": f"{name_first} {p['last']}",
            "email": p["email"] if provide_email else "",
            "phone": p["phone"] if provide_phone else "",
            "state": p["state"] if random.random() < 0.6 else "",
            "country": "US",
            "_truth": p["person_id"],
        })

    with open(DATA_DIR / "dsr_requests.json", "w") as f:
        json.dump(dsr, f, indent=2)

    # Persist ground truth separately for scoring (never used by the matcher)
    with open(DATA_DIR / "_ground_truth.json", "w") as f:
        json.dump({p["person_id"]: p for p in identities}, f, indent=2)

    print(f"identities={len(identities)} network={len(network)} "
          f"billing={len(billing)} third_party={len(third_party)} "
          f"iam={len(iam)} dsr={len(dsr)}")


if __name__ == "__main__":
    build()
