
"""Build data.json for the ABEC Performance dashboard from the raw xlsx exports."""
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


COLS = [
    "Booking Date",
    "Exhibitor Name (Billing)",
    "Other Name",
    "Event City",
    "Stall Size",
    "Deal Value",
    "Booked by",
    "Year",
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


def build():
    current_employees = load_current_employees()
    rate_card = load_rate_card()

    combined = pd.concat([load_master_rows(), load_june_rows()], ignore_index=True)
    combined["Booked by"] = combined["Booked by"].apply(apply_booking_alias)
    combined = combined[combined["Booked by"].isin(current_employees.keys())].copy()
    combined["Year"] = combined["Year"].astype(int).astype(str)
    combined["client_key"] = combined.apply(client_key, axis=1)

    # All-time booked revenue per employee (for ranking), across all clients/years.
    all_time_rev = combined.groupby("Booked by")["Deal Value"].sum()

    employees_out = []
    for short in current_employees:
        info = current_employees[short]
        rev = float(all_time_rev.get(short, 0.0))
        employees_out.append((short, info, rev))

    employees_out.sort(key=lambda e: e[2], reverse=True)

    result_employees = []
    for short, info, _rev in employees_out:
        emp_rows = combined[combined["Booked by"] == short]

        repeat_accounts = []
        for client, crows in emp_rows.groupby("client_key"):
            kept = []
            for year in YEARS:
                yrows = crows[crows["Year"] == year]
                if yrows.empty:
                    continue
                sqm = float(yrows["Stall Size"].sum())
                rev_y = float(yrows["Deal Value"].sum())
                if sqm <= 0:
                    continue
                rate = rev_y / sqm
                if rate <= 0:
                    continue
                n = int(yrows["Deal Value"].count())

                year_card = rate_card[year]
                target_dollar = target_sqm_sum = 0.0
                card_dollar = card_sqm_sum = 0.0
                city_rev = {}
                for _, r in yrows.iterrows():
                    ssize = r["Stall Size"]
                    ssize = float(ssize) if pd.notna(ssize) else 0.0
                    bucket = classify_bucket(r["Event City"])
                    bucket_info = year_card.get(bucket)
                    if bucket_info is not None and ssize:
                        if bucket_info["target"] is not None:
                            target_dollar += ssize * bucket_info["target"]
                            target_sqm_sum += ssize
                        card_dollar += ssize * bucket_info["card"]
                        card_sqm_sum += ssize
                    city_raw = str(r["Event City"]).strip() if pd.notna(r["Event City"]) else "—"
                    deal_val = r["Deal Value"]
                    deal_val = float(deal_val) if pd.notna(deal_val) else 0.0
                    city_rev[city_raw] = city_rev.get(city_raw, 0.0) + deal_val

                target = round(target_dollar / target_sqm_sum) if target_sqm_sum > 0 else None
                card = round(card_dollar / card_sqm_sum) if card_sqm_sum > 0 else None
                below_target = (rate < target) if target is not None else None
                cities_sorted = sorted(city_rev.keys(), key=lambda c: -city_rev[c])

                kept.append(
                    {
                        "year": year,
                        "rate": round(rate),
                        "rev": round(rev_y, 2),
                        "sqm": round(sqm, 2),
                        "n": n,
                        "target": target,
                        "card": card,
                        "below_target": below_target,
                        "cities": cities_sorted,
                    }
                )

            if len(kept) < 2:
                continue

            first_rate = kept[0]["rate"]
            last_rate = kept[-1]["rate"]
            drop_pct = round((last_rate - first_rate) / first_rate * 100, 1)
            vs_target_last = kept[-1]["below_target"]
            if vs_target_last is True:
                direction = "down"
            elif vs_target_last is False:
                direction = "up"
            else:
                direction = "flat"

            below_target_years = sum(1 for k in kept if k["below_target"] is True)
            years_with_target = sum(1 for k in kept if k["target"] is not None)
            discounts = [(k["card"] - k["rate"]) / k["card"] * 100 for k in kept if k["card"]]
            avg_discount_vs_card = round(sum(discounts) / len(discounts), 1) if discounts else None

            repeat_accounts.append(
                {
                    "client": client,
                    "series": kept,
                    "first_rate": first_rate,
                    "last_rate": last_rate,
                    "drop_pct": drop_pct,
                    "direction": direction,
                    "total_rev": round(sum(k["rev"] for k in kept), 2),
                    "years": len(kept),
                    "last_target": kept[-1]["target"],
                    "last_card": kept[-1]["card"],
                    "vs_target_last": vs_target_last,
                    "below_target_years": below_target_years,
                    "years_with_target": years_with_target,
                    "avg_discount_vs_card": avg_discount_vs_card,
                }
            )

        direction_rank = {"down": 0, "flat": 1, "up": 2}
        repeat_accounts.sort(key=lambda a: (direction_rank[a["direction"]], -a["total_rev"]))

        result_employees.append(
            {
                "name": short,
                "full": info["full"],
                "designation": info["designation"],
                "location": info["location"],
                "n_repeat": len(repeat_accounts),
                "repeat_accounts": repeat_accounts,
            }
        )

    return {"years": YEARS, "employees": result_employees}


if __name__ == "__main__":
    data = build()
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    n_repeat_total = sum(e["n_repeat"] > 0 for e in data["employees"])
    print(f"Wrote data.json: {len(data['employees'])} employees, {n_repeat_total} with repeat accounts")
