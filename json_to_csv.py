#!/usr/bin/env python3
"""
Convert UpApp / Maccabi activities JSON → CSV

✓ Matches the schema:
    activity_name, date, start_time, end_time, city, instructor,
    activity_type, spots_left, is_full, availability_status,
    booking_url, description
✓ Extracts every individual schedule item as its own row
✓ Infers month + year from the file's extraction timestamp when
  only the day ("22", "23", ...) is supplied in calendar_dates
✓ Saves UTF-8 CSV alongside the source JSON
"""

from pathlib import Path
import json, re, pandas as pd
from datetime import datetime

# ---------- helpers --------------------------------------------------------- #
def normalize_time(t: str | None) -> str | None:
    """Return HH:MM with a leading zero if needed (e.g., '9:00' → '09:00')."""
    if not t:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})", t.strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else t.strip()

def parse_availability(text: str | None):
    """
    Return (spots_left, is_full, availability_status)
    Examples:
        'נשארו 5 מקומות' → (5, False, same text)
        'כבר מלא'        → (0, True,  same text)
        None              → (None, False, 'Available (no specific info)')
    """
    if not text:
        return None, False, "Available (no specific info)"
    text = text.strip()
    is_full = any(word in text for word in ("מלא", "כבר מלא"))
    m = re.search(r"(\d+)", text)
    spots_left = 0 if is_full else (int(m.group(1)) if m else None)
    return spots_left, is_full, text

def make_iso_date(day: str, stamp: str) -> str:
    """
    Compose YYYY-MM-DD from:
        * day  – e.g. "23"
        * stamp – e.g. "2025-06-21T19:29:56.869541"
    """
    ts = datetime.fromisoformat(stamp)
    return f"{ts.year}-{ts.month:02d}-{int(day):02d}"

# ---------- main ------------------------------------------------------------ #
INPUT = Path("maccabi_activities_20250623_010818.json")
OUTPUT = INPUT.with_suffix(".csv")

with INPUT.open(encoding="utf-8") as fh:
    blob = json.load(fh)

rows = []
timestamp = blob.get("extraction_info", {}).get("timestamp", "")

for activity in blob.get("activities", []):
    # Base‐level attributes
    base = {
        "location": activity.get("activity_name"),
        "city":          activity.get("city"),
        "instructor":    activity.get("instructor"),
        "activity_type": activity.get("activity_type"),
        "booking_url":   activity.get("booking_url"),
        "description":   activity.get("description"),
    }

    # Schedule items might be paired with calendar_dates by position
    # dates = [d.get("date") for d in activity.get("calendar_dates", [])]
    schedules = activity.get("all_schedule_items", [])
    # pairs = list(zip(dates, schedules)) if dates and len(dates) == len(schedules) else [(None, s) for s in schedules]
    for sched in schedules:
        day = sched.get("day_number")
        # Date: from schedule item, matching calendar_dates, or inferred
        date_val =  (make_iso_date(day, timestamp) if day else None) # inferred

        # Extract start and end times
        time_range = sched.get("time")
        if time_range and "-" in time_range:
            # Split on ' - ' or '-'
            parts = [p.strip() for p in re.split(r"\s*-\s*", time_range)]
            if len(parts) == 2:
                start, end = normalize_time(parts[1]), normalize_time(parts[0])
            else:
                start = normalize_time(time_range)
                end = None
        else:
            start = normalize_time(time_range)
            end = None

        spots, full, avail = parse_availability(sched.get("availability_status"))

        rows.append({
            **base,
            "date":                 date_val,
            "start_time":           start,
            "end_time":             end,
            "spots_left":           spots,
            "is_full":              full,
            "availability_status":  avail,
            "instructor":           sched.get("instructor") or base["instructor"],
            "raw_description":      sched.get("raw_description"),
        })

# Assemble DataFrame in the exact column order requested
cols = [
    "location", "date", "start_time", "end_time", "city", "instructor",
    "activity_type", "spots_left", "is_full", "availability_status",
    "booking_url", "description", "raw_description"
]
df = pd.DataFrame(rows)[cols]

df.to_csv(OUTPUT, index=False, encoding="utf-8")
print(f"Wrote {len(df)} rows → {OUTPUT}")

# Debug: count total schedule items in JSON
schedule_items_count = sum(len(a.get("all_schedule_items", [])) for a in blob.get("activities", []))
print(f"Total schedule items in JSON: {schedule_items_count}")
