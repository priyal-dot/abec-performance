"""Build data.json for the ABEC Performance dashboard from the raw xlsx exports."""
import json
from datetime import date

import pandas as pd

MASTER_XLSX = "data/Master till 6 june.xlsx"
JUNE_XLSX = "data/June month.xlsx"
TARGETS_XLSX = "data/5 year targets 2022 - 2026.xlsx"

YEARS = ["2022", "2023", "2024", "2025", "2026"]
JUNE_CUTOFF = pd.Timestamp("2026-06-04")

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


COLS = [
    "Booking Date",
    "Exhibitor Name (Billing)",
    "Other Name",
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
            per_year = crows.groupby("Year").agg(
                rev=("Deal Value", "sum"), sqm=("Stall Size", "sum"), n=("Deal Value", "count")
            )
            kept = []
            for year in YEARS:
                if year not in per_year.index:
                    continue
                row = per_year.loc[year]
                sqm = float(row["sqm"])
                rev_y = float(row["rev"])
                if sqm <= 0:
                    continue
                rate = rev_y / sqm
                if rate <= 0:
                    continue
                kept.append(
                    {
                        "year": year,
                        "rate": round(rate),
                        "rev": round(rev_y, 2),
                        "sqm": round(sqm, 2),
                        "n": int(row["n"]),
                    }
                )

            if len(kept) < 2:
                continue

            first_rate = kept[0]["rate"]
            last_rate = kept[-1]["rate"]
            drop_pct = round((last_rate - first_rate) / first_rate * 100, 1)
            if drop_pct <= -5:
                direction = "down"
            elif drop_pct >= 5:
                direction = "up"
            else:
                direction = "flat"

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
                }
            )

        repeat_accounts.sort(key=lambda a: a["total_rev"], reverse=True)

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
