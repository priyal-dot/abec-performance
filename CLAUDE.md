# Prompt for Claude Code — ABEC Repeat-Account Price Dashboard

---

Build a static, self-contained, mobile-responsive web dashboard called **ABEC Performance**,
put it in a Git repo, push it to GitHub, and deploy it so it renders publicly. Work in this
folder. The three `.xlsx` files in this folder are the data source.

## 1. What the app does
It analyses exhibition-stall salespeople and, for each person, shows their **repeat accounts**
(clients booked in 2+ different years) and whether the **rate they charge per square metre (SQM)
has dropped or grown** over the years. This surfaces price erosion on renewed accounts. Salary
is never displayed.

## 2. Project structure
```
/data/                     <- move the three .xlsx files here
build_data.py              <- Python: reads the xlsx, writes data.json
data.json                  <- generated
index.html                 <- the whole app, self-contained (Chart.js embedded inline)
vendor/chart.umd.js        <- Chart.js 4.4.1 UMD, embedded into index.html at build time
render.yaml                <- Render.com static-site config
README.md
```
Use only vanilla HTML/CSS/JS (no framework, no build tooling beyond the Python data step).
Chart.js MUST be embedded inline inside `index.html` (not a CDN link) so the page works fully
offline / on mobile.

## 3. Data model (columns in the Excel files)
`Master` sheet in *Master till 6 june.xlsx* and the `june` sheet in *June month.xlsx* share:
`Booking Date, Exhibitor Name (Billing), Other Name (Branding), Event City, Stall Rate per SQM,
Stall Size, Deal Value, Booked by, Team, Involvement, RB/NB, Closed by Lead, Year, Event`.
- `Sheet1` in *Master till 6 june.xlsx* is the employee master: `Short Name, Full Name, DOJ,
  Location, Designation, ...targets`.
- `Sheet2` in *5 year targets 2022 - 2026.xlsx* is the **authoritative current-employee list**
  (`Employee Name`, DOJ, then per-year `Target SQM / Target Revenue / Actual Revenue` blocks for
  2022-23 … 2026-27).

## 4. build_data.py logic (implement exactly)
1. **Current employees** = the names in *5 year targets* Sheet2. Some are full names; resolve each
   to the booking "short name" via Sheet1 (match on Short Name, else on Full Name). Manual name
   fixes: `"Abhishek S" -> "Abhishek G"`.
2. **Booking-name aliases** (unify the same person / spelling variants before aggregating):
   `"Sebestian D"->"Sebastian D"`, `"Saloni J"->"Salonee J"`, `"Khusbhoo K"->"Khushboo K"`,
   `"Abhishek S"->"Abhishek G"`.
3. **Combine rows**: all `Master` rows + only the `june` rows with Booking Date **after 2026-06-04**
   (Master already covers up to 2026-06-04; this avoids double-counting the overlap). June rows get
   `Year = 2026`.
4. Aggregate bookings by `Booked by` (after aliasing), keeping only people in the current list.
   Numbers can be negative (cancellations) — keep them; they net out.
5. **Years axis** = `["2022","2023","2024","2025","2026"]`.
6. **Repeat (PP) account** = a client booked in ≥2 distinct years. Client key = `Exhibitor Name
   (Billing)`, falling back to `Other Name (Branding)`, else "—".
   - For each client-year: weighted rate = `sum(Deal Value) / sum(Stall Size)`.
   - Keep only years where sqm > 0 and rate > 0. Need ≥2 such years to qualify.
   - `first_rate` = earliest kept year's rate, `last_rate` = latest.
   - `drop_pct = round((last_rate - first_rate)/first_rate*100, 1)`.
   - Direction: `down` if drop_pct ≤ -5, `up` if ≥ +5, else `flat`.
   - Also store per-year series: `{year, rate, rev, sqm, n(deals)}`, plus `total_rev`, `years`(count).
7. Per employee also store: `name, full, designation, location, n_repeat, repeat_accounts[]`
   (sorted by total_rev desc). Sort employees by all-time booked revenue desc.
8. Write `data.json`: `{ years, employees:[...] }`.

## 5. Front-end filtering (in index.html JS)
- Show only employees with `n_repeat > 0`.
- Additionally EXCLUDE these names entirely:
  `['Jasmeet V','Mohan K','Nikhil D','Digvijay S','Swasti S','Vaishak S','Riamei K','Prapti P','Akshay M']`.

## 6. UI spec
Light theme. Background `#f4f6f9`, white cards `#ffffff`, border `#e3e7ec`, text `#1a1e24`,
muted `#606771`; accent lime `#c6f24e` / green `#5b8a00`; down = red `#e23c4a`, up = teal `#12b39a`.
Font: Inter / system-ui. Large, readable type. `₹` amounts compact (Cr / L / k). Indian digit grouping.

Layout top → bottom:
- **Top bar**: title `ABEC. Performance` (the dot in lime). Controls on the right: `‹` prev,
  a search box, a `<select>` of employee **names only** (no revenue), `›` next. Search filters the
  select; prev/next step through it.
- **ID card**: circular/rounded avatar (first initial, lime→teal gradient), full name, `Designation ·
  Location`, and a tag `Rank #X of N by revenue`.
- **Repeat (PP) accounts** card:
  - Header `Repeat (PP) accounts` + two filter chips: **Price dropped** (default active) and
    **Price grew**. `down` shows drop_pct ≤ -5, `up` shows ≥ +5.
  - **Side-by-side** (`grid` 2 col, stacks on mobile):
    - **Left = accounts table**: sticky header, own vertical scroll. Columns: `Account`,
      `Start ₹/SQM`, `Now ₹/SQM`. Each row has a 4px left border colored red (down) or teal (up);
      the "Now" value is bold and colored. Row click selects it.
    - **Right = detail panel**: account name; a row of pills `Start ₹X → Now ₹Y` and
      `±Z% per SQM` colored by direction; a **line chart** of rate/SQM by year with the **value
      printed above each point** (white label box, so no hover needed); a **year-by-year table**
      (`Year, Rate/SQM, Revenue, SQM, Deals`); and a one-line note (e.g. "Selling lower now: rate
      per SQM fell ₹X → ₹Y. Worth a margin review.").
  - Selecting a person auto-selects their first account. Tooltips off — everything is displayed.
- Fully responsive: at ≤900px stack the two columns; at ≤640px shrink type/padding, make the search
  and select full-width, reduce chart height. Include `<meta viewport>`.

## 7. Embedding Chart.js
Download Chart.js 4.4.1 UMD (`npm i chart.js@4.4.1`, copy `dist/chart.umd.js` to `vendor/`).
Inline its full contents inside a `<script>` tag in `index.html` (verify the file contains no
`</script>` sequence). Draw the point-value labels with a small custom Chart.js plugin
(`afterDatasetsDraw`) rather than an external plugin.

## 8. Verify before deploying
- `python build_data.py` regenerates `data.json` with no errors.
- Spot-check: a known employee's per-year weighted rate matches a hand calc from the raw rows.
- Open `index.html` with the network disabled — the chart and tables still render.
- Check the layout at 375px width (mobile) and desktop.

## 9. GitHub + deploy (render)
1. `git init`, add a sensible `.gitignore` (ignore `vendor/` and the raw `.xlsx` if they shouldn't
   be public — but DO commit `data.json` and `index.html`). Commit.
2. Create the GitHub repo and push (GitHub CLI):
   `gh repo create <your-github-username>/abec-performance --public --source=. --push`
3. **Deploy so it renders** — do BOTH-friendly, pick one:
   - **Render.com (static site)**: add `render.yaml`:
     ```yaml
     services:
       - type: web
         name: abec-performance
         runtime: static
         buildCommand: ""
         staticPublishPath: .
     ```
     Then connect the repo on render.com → New → Static Site (or Blueprint). No build step needed;
     it just serves `index.html`.
   - **GitHub Pages (simplest, free)**: `gh` → repo Settings → Pages → deploy from `main` / root,
     or run `gh api` to enable Pages. The site renders at
     `https://<your-github-username>.github.io/abec-performance/`.
4. Print the final live URL.

## 10. Deliverable
A public GitHub repo and a live URL rendering the dashboard, behaving exactly as specified above,
working offline and on mobile.