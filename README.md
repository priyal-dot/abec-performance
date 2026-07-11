# ABEC PP Analysis

A static, self-contained dashboard that audits individual exhibition-stall deals: for each RM, it
flags every deal closed **below that year's discounted rate** ("PP deal") that was booked **outside
the show's pre-show risk period** — i.e. has no timing justification for the discount and is worth a
review. Deals booked inside the risk period get the benefit of the doubt and aren't shown. Salary is
never displayed.

## How it works

1. Four source `.xlsx` files live in `/data/` (not committed — see `.gitignore`):
   - `Master till 6 june.xlsx` — booking history through 2026-06-04 (`Master` sheet) and the
     employee master (`Sheet1`).
   - `June month.xlsx` — bookings for June 2026 (`june` sheet); only rows after 2026-06-04 are used,
     to avoid double-counting with Master.
   - `5 year targets 2022 - 2026.xlsx` — the authoritative list of current employees (`Sheet2`).
   - `Standard_Rates_2022-2026.xlsx` — one sheet per year, giving the Standard Card Rate (ceiling)
     and Discounted Rate per event/city. Bookings are matched to a row by event city (Bangalore /
     Mumbai [+ Ceramics / ACE Surfaces] / Delhi / Hyderabad); anything else (sponsorships, branding,
     regional shows) falls back to the shared `ACE REFLECT` rate.
2. `python build_data.py` reads the four files and, for every individual booking row, checks whether
   its rate is strictly below that year's discounted rate for its bucket (a PP deal) and whether the
   booking date falls inside that show's fixed pre-show risk-period window (see the in-app
   "Methodology" card for the exact month ranges per show — they're hardcoded in `build_data.py` as
   `RISK_WINDOWS`, since they come from business rules rather than the raw data). Deals outside the
   window are grouped by employee and client into `data.json`.
3. `data.json` is embedded inline into `index.html` (no charts in this version, so no Chart.js), so
   the page is fully self-contained and works offline / on mobile with no build step or server.

## Regenerating the data

```
pip install pandas openpyxl
python build_data.py
```

Then re-embed the refreshed `data.json` into `index.html` (replace the `const DATA = {...}` literal
in the inline `<script>` block with the new file's contents).

## Local preview

Just open `index.html` in a browser — no server required.

## Deploy

- **Render.com**: connect this repo as a Static Site (or use the included `render.yaml` Blueprint).
  No build command needed; it serves `index.html` directly.
- **GitHub Pages**: enable Pages on the repo, deploying from `main` / root.
