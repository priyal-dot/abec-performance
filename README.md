# ABEC Performance

A static, self-contained dashboard for exhibition-stall salespeople: for each person, it surfaces
their **repeat accounts** (clients booked in 2+ different years) and compares the **rate charged per
square metre (SQM)** against the standard rate card — the approved **discounted target** rate and the
**card (ceiling) rate** — to flag accounts sold below the approved floor. Salary is never displayed.

## How it works

1. Four source `.xlsx` files live in `/data/` (not committed — see `.gitignore`):
   - `Master till 6 june.xlsx` — booking history through 2026-06-04 (`Master` sheet) and the
     employee master (`Sheet1`).
   - `June month.xlsx` — bookings for June 2026 (`june` sheet); only rows after 2026-06-04 are used,
     to avoid double-counting with Master.
   - `5 year targets 2022 - 2026.xlsx` — the authoritative list of current employees (`Sheet2`).
   - `Standard_Rates_2022-2026.xlsx` — one sheet per year, giving the Standard Card Rate (ceiling)
     and Discounted Rate (approved target) per event/city. Bookings are matched to a row by event
     city (Bangalore / Mumbai [+ Ceramics / ACE Surfaces] / Delhi / Hyderabad); anything else
     (sponsorships, branding, regional shows) falls back to the `ACE REFLECT` "other cities" rate.
2. `python build_data.py` reads the four files, aggregates bookings per employee and per repeat
   client, computes the weighted actual/target/card rate per SQM per year (weighted by stall size),
   and writes `data.json`.
3. `data.json` and Chart.js 4.4.1 (`vendor/chart.umd.js`) are embedded inline into `index.html`, so
   the page is fully self-contained and works offline / on mobile with no build step or server.

## Regenerating the data

```
pip install pandas openpyxl
python build_data.py
```

Then re-embed the refreshed `data.json` into `index.html` (replace the `const DATA = {...}` literal
in the second inline `<script>` block with the new file's contents).

## Local preview

Just open `index.html` in a browser — no server required.

## Deploy

- **Render.com**: connect this repo as a Static Site (or use the included `render.yaml` Blueprint).
  No build command needed; it serves `index.html` directly.
- **GitHub Pages**: enable Pages on the repo, deploying from `main` / root.
