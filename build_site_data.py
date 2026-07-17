#!/usr/bin/env python3
"""Generate GitHub Pages data (leads.json) from the A+B outreach queue.

Reads out/outreach_queue_*.csv (most recent) and writes site/leads.json
with a small summary + the lead array. The site/index.html loads this.
"""
import csv, json, glob, os
from pathlib import Path
from datetime import datetime

REPO = Path("/root/maricopa_research")
SITE = REPO / "site"
SITE.mkdir(exist_ok=True)

queues = sorted(glob.glob(str(REPO / "out" / "outreach_queue_*.csv")))
if not queues:
    print("no outreach queue found"); raise SystemExit(1)
latest = queues[-1]
print("source:", latest)

rows = []
with open(latest, newline="") as f:
    for r in csv.DictReader(f):
        rows.append({
            "parcel": r["PARCEL"],
            "address": r["ADDRESS"],
            "city": r["CITY"],
            "zip": r["ZIP"],
            "price": r["PRICE"],
            "type": r["PROPERTY_TYPE"],
            "occ": r["OWNER_OCCUPANCY"],
            "buyer": r["BUYER_NAME"].strip(),
            "state": r["BUYER_STATE"],
            "mailing": r["BUYER_MAILING_ADDR"],
            "buyer_type": r["BUYER_TYPE"],
            "seller": r["SELLER_NAME"].strip(),
            "deed": r["DEED_DATE_MMDDYYYY"],
            "move_in": r["MOVE_IN_TARGET"],
            "segment": r["SEGMENT"],
        })

seg_a = sum(1 for r in rows if r["segment"] == "A")
seg_b = sum(1 for r in rows if r["segment"] == "B")
cities = {}
for r in rows:
    cities[r["city"]] = cities.get(r["city"], 0) + 1
top_cities = sorted(cities.items(), key=lambda x: -x[1])[:10]

payload = {
    "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "count": len(rows),
    "segment_a": seg_a,
    "segment_b": seg_b,
    "top_cities": [{"city": c, "n": n} for c, n in top_cities],
    "source": "Maricopa County Assessor — Sales Affidavits (public bulk download)",
    "leads": rows,
}
(SITE / "leads.json").write_text(json.dumps(payload, indent=1))
print(f"wrote site/leads.json: {len(rows)} leads (A={seg_a}, B={seg_b})")
