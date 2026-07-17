#!/usr/bin/env python3
"""
UntappedHomes — Maricopa County monthly new-homeowner pipeline.

What it does:
  1. Downloads the latest Maricopa Assessor "Sales Affidavits" bulk ZIP (public, free).
  2. Filters to the target window: sales recorded in the last N days
     (default 30), residential property types only.
  3. Segments by OWNER_OCCUPANCY: keeps A (primary resident) + B (second home).
     Drops C (investor) per operator decision.
  4. Computes MOVE_IN_WINDOW = recorded date + ~30-60 days (lead-time shift):
     the buyer typically takes possession 0-30d after close, so outreach should
     land ~30-60d after recording.
  5. Emits:
       - <outdir>/new_homeowners_<YYYYMM>.csv   (current month pull)
       - <outdir>/outreach_queue_<YYYYMMDD>.csv (A+B, with move_in_target date)
  6. Idempotent: skips re-download if ZIP is < 24h old.

Usage:
  python3 maricopa_pipeline.py            # default: last 30 days, A+B
  python3 maricopa_pipeline.py --days 30 --seg A,B
"""
import argparse, csv, os, re, sys, time, zipfile, io
from datetime import datetime, timedelta
from pathlib import Path

import urllib.request

REPO = Path("/root/maricopa_research")
RAW_ZIP = REPO / "sales_affidavits.bin"          # cached download
DATA_DIR = REPO / "data"
OUT_DIR = REPO / "out"
DATA_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

SALES_GUID = "f3484c72a938497286adc4e5de7e9963"   # Sales Affidavits item
ARCGIS_ITEM_URL = f"https://www.arcgis.com/sharing/rest/content/items/{SALES_GUID}/data"
RES_TYPES = ("Single Family Reside", "Condo/Townhouse", "2-4 Plex", "Mobile/Manufactured")

def download_sales_affidavits(force=False):
    if RAW_ZIP.exists() and (time.time() - RAW_ZIP.stat().st_mtime) < 24*3600 and not force:
        print(f"[download] using cached {RAW_ZIP} (<24h old)")
        return RAW_ZIP
    print(f"[download] fetching Sales Affidavits bulk ZIP ...")
    req = urllib.request.Request(ARCGIS_ITEM_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    RAW_ZIP.write_bytes(data)
    print(f"[download] saved {len(data)//1024//1024} MB -> {RAW_ZIP}")
    return RAW_ZIP

def extract_rows(zip_path):
    """Yield parsed rows from the pipe-delimited Sales_Affidavits.txt inside the ZIP."""
    with zipfile.ZipFile(zip_path) as z:
        name = [n for n in z.namelist() if n.lower().endswith("sales_affidavits.txt")][0]
        with z.open(name) as f:
            # stream line by line (272MB file)
            first = True
            for raw in f:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if first:
                    first = False
                    continue
                cols = line.split("|")
                if len(cols) > 43:
                    yield cols

def parse_mmyyyy(s):
    try:
        return datetime.strptime(s, "%m%Y")
    except Exception:
        return None

def parse_mmddyyyy(s):
    try:
        return datetime.strptime(s, "%m%d%Y")
    except Exception:
        return None

def run(days=30, segs=("A", "B")):
    zp = download_sales_affidavits()
    cutoff = datetime.now() - timedelta(days=days)
    now = datetime.now()
    month_tag = now.strftime("%Y%m")
    out_all = OUT_DIR / f"new_homeowners_{month_tag}.csv"
    out_queue = OUT_DIR / f"outreach_queue_{now.strftime('%Y%m%d')}.csv"

    total = 0
    kept = 0
    with out_all.open("w", newline="") as fa, out_queue.open("w", newline="") as fq:
        wa = csv.writer(fa)
        wq = csv.writer(fq)
        wa.writerow(["PARCEL","ADDRESS","CITY","ZIP","PRICE","PROPERTY_TYPE","OWNER_OCCUPANCY",
                     "BUYER_NAME","BUYER_STATE","BUYER_MAILING_ADDR","SELLER_NAME","DEED_DATE_MMDDYYYY","SALE_MONTH"])
        wq.writerow(["PARCEL","ADDRESS","CITY","ZIP","PRICE","PROPERTY_TYPE","OWNER_OCCUPANCY",
                     "BUYER_NAME","BUYER_STATE","BUYER_MAILING_ADDR","BUYER_TYPE","SELLER_NAME",
                     "DEED_DATE_MMDDYYYY","MOVE_IN_TARGET","SEGMENT"])
        for r in extract_rows(zp):
            total += 1
            sale = parse_mmyyyy(r[1])
            if not sale:
                continue
            if sale < cutoff:
                continue
            if not any(t in r[8] for t in RES_TYPES):
                continue
            # build address
            addr = r[10]
            if r[11] and r[11] not in r[10]:
                addr = addr + " " + r[11]
            occ = r[38].strip()
            if occ not in segs:
                continue
            kept += 1
            deed_dt = parse_mmddyyyy(r[4])
            move_in = (deed_dt + timedelta(days=45)).strftime("%Y-%m-%d") if deed_dt else ""
            # buyer mailing address (GRANTEE line1/2 + city/state/zip)
            maddr = " ".join(x for x in [r[22], r[23], r[24], r[25], r[26], r[27]] if x).strip()
            # buyer type: entity (LLC/TRUST/etc) vs individual
            bn = r[21].upper()
            btype = "ENTITY" if any(k in bn for k in ["LLC","TRUST","INC","CORP","COMPANY","PROPERTIES","HOLDINGS","CAPITAL","LP","PARTNERS","GROUP"]) else "INDIVIDUAL"
            wa.writerow([r[0], addr, r[12], r[13], r[2], r[8], occ, r[21], r[25], maddr, r[14], r[4], r[1]])
            wq.writerow([r[0], addr, r[12], r[13], r[2], r[8], occ, r[21], r[25], maddr, btype, r[14], r[4], move_in, occ])
    print(f"[done] scanned {total} rows | window<= {days}d | kept(A+B residential): {kept}")
    print(f"  -> {out_all}")
    print(f"  -> {out_queue}  (with MOVE_IN_TARGET = recording + 45d)")
    return kept

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seg", default="A,B")
    a = ap.parse_args()
    segs = tuple(s.strip().upper() for s in a.seg.split(","))
    run(days=a.days, segs=segs)
