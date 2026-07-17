# UntappedHomes — Maricopa New Homeowners

Public, free lead dashboard for **new homeowners in Maricopa County, AZ** (Phoenix metro).

Data source: **Maricopa County Assessor — Sales Affidavits** (public bulk download, free).
- Filtered to residential sales recorded in the trailing ~60 days.
- Segments kept: **A** (owner-occupied primary residence) + **B** (second home). Investors (C) excluded.
- `MOVE_IN_TARGET` = recording date + 45 days (when the buyer typically takes possession).

## View the dashboard
Published via GitHub Pages — open `index.html` from the site root after Pages is enabled.

## Repo layout
- `site/index.html` — mobile-friendly dashboard (loads `leads.json`)
- `site/leads.json` — the lead data (regenerated monthly)
- `maricopa_pipeline.py` — monthly pull script (downloads affidavits, filters A+B, adds move-in target)
- `out/` — generated CSV queues (outreach-ready)
- `june2026_new_homeowners.csv` — June 2026 full pull (A+B)

## Regenerate
```
python3 maricopa_pipeline.py --days 60 --seg A,B
python3 build_site_data.py
git add -A && git commit -m "refresh" && git push
```

> Note: buyer contact info here is the public mailing address only (direct-mail ready). Phone/email append requires a paid, TCPA-compliant provider.
