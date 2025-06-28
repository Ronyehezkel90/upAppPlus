#!/usr/bin/env python3
"""
usage:
    python filter_upapp.py activities.json 22 08:00 11:30

positional arguments
    1. path to the JSON file shown above
    2. day-of-month to match: the value found in calendar_dates[0]["date"]
    3. range-start  (HH:MM, 24-h)
    4. range-end    (HH:MM, 24-h)

prints the matching activities + schedule_items in JSON.
"""

import json
import sys
from datetime import datetime


def hhmm(t: str):
    """Return a datetime.time from 'HH:MM'."""
    return datetime.strptime(t.strip(), "%H:%M").time()


def schedule_in_range(item_time: str, range_start, range_end):
    """
    item_time comes as 'END - START' e.g. '09:00 - 08:00'.
    We want items whose START >= range_start and END <= range_end.
    """
    end_str, start_str = (part.strip() for part in item_time.split("-"))
    start, end = hhmm(start_str), hhmm(end_str)
    return start >= range_start and end <= range_end


def aaa(item, day_str):
    return item['day_number'] == day_str


def filter_activities(data, day_str, range_start, range_end):
    wanted = []
    for act in data["activities"]:
        # keep only schedule_items in time-window
        filtered_items = [
            item for item in act["all_schedule_items"]
            if schedule_in_range(item["time"], range_start, range_end) and aaa(item, day_str)
        ]
        if filtered_items:  # keep activity only if any slot fits
            # act_copy = {k: v for k, v in act.items() if k != "schedule_items"}
            # act_copy["schedule_items"] = filtered_items
            filtered_items.append({'who':act['activity_name']})
            wanted.append(filtered_items)
    return wanted


def main():
    path = '/Users/ronyehezkel/Downloads/apk_analysis/maccabi_activities_20250623_010818.json'
    day = '24'
    start_s = '19:31'
    end_s = '22:35'

    # if len(sys.argv) != 5:
    #     print(__doc__)
    #     sys.exit(1)
    # path, day, start_s, end_s = sys.argv[1:]

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    start_t, end_t = hhmm(start_s), hhmm(end_s)
    result = filter_activities(data, day, start_t, end_t)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
