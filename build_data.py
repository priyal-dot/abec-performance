"""Build data.json for the ABEC PP Analysis dashboard from the raw xlsx exports.

Flags individual deals closed below that year's discounted rate (a "PP deal")
that fall OUTSIDE the show's pre-show risk period, i.e. have no timing
justification for the discount.
"""
import calendar
import json
from datetime import date

import pandas as pd

MASTER_XLSX = "data/Master till 6 june.xlsx"
JUNE_XLSX = "data/June month.xlsx"
TARGETS_XLSX = "data/5 year targets 2022 - 2026.xlsx"
RATES_XLSX = "data/Standard_Rates_2022-2026.xlsx"

YEARS = ["2022", "2023", "2024", "2025", "2026"]
JUNE_CUTOFF = pd.Timestamp("2026-06-04")
OTHER_BUCKET = "ACE REFLECT"

# Manual fixes for resolving 5-year-targets employee names to booking short names.
MANUAL_EMPLOYEE_FIX = {"Abhishek S": "Abhishek G"}

# Booking-name aliases: unify spelling variants before aggregating.
BOOKING_ALIASES = {
    "Sebestian D": "Sebastian D",
    "Saloni J": "Salonee J",
    "Khusbhoo K": "Khushboo K",
    "Abhishek S": "Abhishek G",
}

# Pre-show risk period: (start_month, end_month, display_style), applied within
# the deal's own booking Year. "short" -> "Jul-Sep"; "long" -> "Jul 2024 - Oct 2024".
RISK_WINDOWS = {
    "Bangalore": (7, 9, "short"),
    "Mumbai": (7, 10, "short"),
    "Mumbai CERAMICS": (7, 10, "short"),
    "Mumbai ACE SURFACES": (7, 10, "short"),
    "Delhi": (8, 11, "short"),
    "Hyderabad": (10, 12, "short"),
    "Goa": (1, 2, "long"),
    "Ahmedabad": (1, 2, "long"),
    "Indore": (4, 6, "long"),
    "Chennai": (4, 6, "long"),
    "Raipur": (4, 6, "long"),
    "Jaipur": (5, 7, "long"),
    "Coimbatore": (6, 8, "long"),
}
RISK_CITY_KEYWORDS = ["Goa", "Ahmedabad", "Indore", "Chennai", "Raipur", "Jaipur", "Coimbatore"]


def load_employee_master():
    s1 = pd.read_excel(MASTER_XLSX, sheet_name="Sheet1")
    s1["Short Name"] = s1["Short Name"].astype(str).str.strip()
    s1["Full Name"] = s1["Full Name"].astype(str).str.strip()
    by_short = {r["Short Name"]: r for _, r in s1.iterrows()}
    by_full = {r["Full Name"]: r for _, r in s1.iterrows()}
    return by_short, by_full


def load_current_employees():
    by_short, by_full = load_employee_master()
    t = pd.read_excel(TARGETS_XLSX, sheet_name="Sheet2")
    raw_names = t.iloc[1:, 0].dropna().astype(str).str.strip().tolist()

    employees = {}
    for raw in raw_names:
        name = MANUAL_EMPLOYEE_FIX.get(raw, raw)
        row = by_short.get(name)
        if row is None:
            row = by_full.get(name)
        if row is None:
            raise ValueError(f"Could not resolve current employee {raw!r}")
        short = row["Short Name"]
        employees[short] = {
            "full": row["Full Name"],
            "designation": row["Designation"],
            "location": row["Location"],
        }
    return employees


def load_rate_card():
    """year -> {bucket_name: {'card': float, 'target': float|None}}"""
    card = {}
    for year in YEARS:
        df = pd.read_excel(RATES_XLSX, sheet_name=year)
        buckets = {}
        for _, r in df.iterrows():
            event = str(r["Event"]).strip()
            target = r["Discounted Rate (Rs./sq. mt)"]
            buckets[event] = {
                "card": float(r["Standard Card Rate (Rs./sq. mt + 18% GST)"]),
                "target": float(target) if pd.notna(target) else None,
            }
        card[year] = buckets
    return card


def classify_bucket(event_city):
    if pd.isna(event_city):
        return OTHER_BUCKET
    c = str(event_city).strip().lower()
    if "bangalore" in c:
        return "Bangalore"
    if "delhi" in c:
        return "Delhi"
    if "hyderabad" in c:
        return "Hyderabad"
    if "mumbai" in c:
        if "ceramic" in c:
            return "Mumbai CERAMICS"
        if "surface" in c:
            return "Mumbai ACE SURFACES"
        return "Mumbai"
    return OTHER_BUCKET


def classify_risk_city(event_city):
    """Which named show (if any) governs this row's risk-period window."""
    if pd.isna(event_city):
        return None
    bucket = classify_bucket(event_city)
    if bucket in ("Bangalore", "Mumbai", "Mumbai CERAMICS", "Mumbai ACE SURFACES", "Delhi", "Hyderabad"):
        return bucket
    c = str(event_city).strip().lower().replace("coimabtore", "coimbatore")
    for name in RISK_CITY_KEYWORDS:
        if name.lower() in c:
            return name
    return None


def get_risk_window(risk_city, year):
    if risk_city not in RISK_WINDOWS:
        return None
    start_month, end_month, style = RISK_WINDOWS[risk_city]
    y = int(year)
    start = date(y, start_month, 1)
    end = date(y, end_month, calendar.monthrange(y, end_month)[1])
    return start, end, style


def fmt_window(start, end, style):
    if style == "short":
        return f"{start.strftime('%b')}-{end.strftime('%b')}"
    return f"{start.strftime('%b %Y')} - {end.strftime('%b %Y')}"


COLS = [
    "Booking Date",
    "Exhibitor Name (Billing)",
    "Other Name",
    "Event City",
    "Stall Size",
    "Deal Value",
    "Booked by",
    "Year",
    "RB/NB",
]


def load_master_rows():
    df = pd.read_excel(MASTER_XLSX, sheet_name="Master")
    df = df.rename(columns={"Other Name\n(Branding)": "Other Name"})
    df["Booking Date"] = pd.to_datetime(df["Booking Date"], errors="coerce")
    return df[COLS]


def load_june_rows():
    df = pd.read_excel(JUNE_XLSX, sheet_name="june")
    df = df.rename(columns={"Other Name ": "Other Name"})
    df["Booking Date"] = pd.to_datetime(df["Booking Date"], errors="coerce")
    df["Year"] = 2026
    df = df[df["Booking Date"] > JUNE_CUTOFF]
    return df[COLS]


def apply_booking_alias(x):
    if pd.isna(x):
        return None
    x = str(x).strip()
    return BOOKING_ALIASES.get(x, x)


def client_key(row):
    billing = row["Exhibitor Name (Billing)"]
    if pd.notna(billing) and str(billing).strip():
        return str(billing).strip()
    other = row["Other Name"]
    if pd.notna(other) and str(other).strip():
        return str(other).strip()
    return "—"


def compact_inr(n):
    sign = "-" if n < 0 else ""
    a = abs(n)
    if a >= 1e7:
        s = f"{a/1e7:.2f}".rstrip("0").rstrip(".") + " Cr"
    elif a >= 1e5:
        s = f"{a/1e5:.2f}".rstrip("0").rstrip(".") + " L"
    elif a >= 1e3:
        s = f"{a/1e3:.1f}".rstrip("0").rstrip(".") + "k"
    else:
        s = f"{round(a):,}"
    return sign + "₹" + s


def build():
    current_employees = load_current_employees()
    rate_card = load_rate_card()

    combined = pd.concat([load_master_rows(), load_june_rows()], ignore_index=True)
    combined["Booked by"] = combined["Booked by"].apply(apply_booking_alias)
    combined = combined[combined["Booked by"].isin(current_employees.keys())].copy()
    combined["Year"] = combined["Year"].astype(int).astype(str)
    combined["client_key"] = combined.apply(client_key, axis=1)

    all_time_rev = combined.groupby("Booked by")["Deal Value"].sum()

    result_employees = []
    for short, info in current_employees.items():
        emp_rows = combined[combined["Booked by"] == short]

        # Deal-level: find every PP deal (rate strictly below that year's
        # discounted rate) that falls outside its show's risk period.
        out_deals = []  # each: dict with client + deal fields
        for _, r in emp_rows.iterrows():
            ssize = r["Stall Size"]
            ssize = float(ssize) if pd.notna(ssize) else 0.0
            deal_val = r["Deal Value"]
            deal_val = float(deal_val) if pd.notna(deal_val) else 0.0
            if ssize <= 0:
                continue
            rate = deal_val / ssize
            if rate <= 0:
                continue

            year = r["Year"]
            bucket = classify_bucket(r["Event City"])
            bucket_info = rate_card.get(year, {}).get(bucket)
            if bucket_info is None or bucket_info["target"] is None:
                continue
            discounted = bucket_info["target"]
            if rate >= discounted:
                continue  # not a PP deal

            booking_date = r["Booking Date"]
            if pd.isna(booking_date):
                continue
            booking_date = booking_date.date()

            risk_city = classify_risk_city(r["Event City"])
            window = get_risk_window(risk_city, year) if risk_city else None
            if window is not None:
                w_start, w_end, style = window
                if w_start <= booking_date <= w_end:
                    continue  # inside risk period: benefit of the doubt
                window_label = fmt_window(w_start, w_end, style)
            else:
                window_label = "—"

            impact = (discounted - rate) * ssize
            out_deals.append(
                {
                    "client": r["client_key"],
                    "booked": booking_date,
                    "show": str(r["Event City"]).strip() if pd.notna(r["Event City"]) else "—",
                    "edition": year,
                    "rate": round(rate),
                    "disc_rate": round(discounted),
                    "gap": round(rate - discounted),
                    "sqm": round(ssize, 2),
                    "deal_value": round(deal_val, 2),
                    "impact": round(impact, 2),
                    "risk_window": window_label,
                    "rb_nb": str(r["RB/NB"]).strip() if pd.notna(r["RB/NB"]) else None,
                }
            )

        clients = {}
        for d in out_deals:
            clients.setdefault(d["client"], []).append(d)

        flagged_clients = []
        for client, deals in clients.items():
            deals.sort(key=lambda d: d["booked"])
            editions = sorted({d["edition"] for d in deals})
            rb_count = sum(1 for d in deals if d["rb_nb"] == "RB")
            nb_count = sum(1 for d in deals if d["rb_nb"] == "NB")
            rb_nb = "RB" if rb_count >= nb_count and rb_count > 0 else ("NB" if nb_count > 0 else None)
            total_impact = sum(d["impact"] for d in deals)
            flagged_clients.append(
                {
                    "client": client,
                    "deals": [
                        {
                            "booked": d["booked"].strftime("%d-%b-%y"),
                            "show": d["show"],
                            "edition": d["edition"],
                            "rate": d["rate"],
                            "disc_rate": d["disc_rate"],
                            "gap": d["gap"],
                            "sqm": d["sqm"],
                            "deal_value": d["deal_value"],
                            "impact": d["impact"],
                            "risk_window": d["risk_window"],
                        }
                        for d in deals
                    ],
                    "n_deals": len(deals),
                    "total_impact": round(total_impact, 2),
                    "total_sqm": round(sum(d["sqm"] for d in deals), 2),
                    "total_deal_value": round(sum(d["deal_value"] for d in deals), 2),
                    "editions": editions,
                    "rb_nb": rb_nb,
                }
            )

        flagged_clients.sort(key=lambda c: (-c["n_deals"], -c["total_impact"]))

        result_employees.append(
            (
                float(all_time_rev.get(short, 0.0)),
                {
                    "name": short,
                    "full": info["full"],
                    "designation": info["designation"],
                    "location": info["location"],
                    "n_flagged": len(flagged_clients),
                    "total_impact": round(sum(c["total_impact"] for c in flagged_clients), 2),
                    "flagged_clients": flagged_clients,
                },
            )
        )

    result_employees.sort(key=lambda e: e[0], reverse=True)
    return {"years": YEARS, "employees": [e[1] for e in result_employees]}


if __name__ == "__main__":
    data = build()
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=None, separators=(",", ":"), default=str)
    n_flagged_total = sum(e["n_flagged"] > 0 for e in data["employees"])
    total_impact = sum(e["total_impact"] for e in data["employees"])
    print(
        f"Wrote data.json: {len(data['employees'])} employees, "
        f"{n_flagged_total} with flagged clients, total impact {compact_inr(total_impact)}"
    )
