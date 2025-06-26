import json
import re
from datetime import datetime
from collections import defaultdict

WATCH_RE = re.compile(r"\d+")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def group_hits_by_wid(hits):
    grouped = defaultdict(list)
    for h in hits:
        wid = h["ym:pv:watchID"]
        grouped[wid].append(h["ym:pv:dateTime"])
    return grouped


def count_slots(watch_ids_raw, hits_by_wid):
    ids = WATCH_RE.findall(str(watch_ids_raw))
    times = []
    for wid in ids:
        times.extend(hits_by_wid.get(wid, []))
    if not times:
        return 0
    t0 = min(times)
    t0_dt = datetime.strptime(t0, "%Y-%m-%d %H:%M:%S")
    slots = set()
    for t in times:
        dt = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
        delta = (dt - t0_dt).total_seconds()
        slots.add(int(delta // 15))
    return len(slots)


def score_visit(visit, slots):
    D = int(visit["ym:s:visitDuration"])
    b = int(visit["ym:s:bounce"])
    S = slots

    if S in (19, 16):
        return 3

    if D == 0 or (b == 1 and S == 0):
        return 1

    if S == 1 and D < 10 and b == 1:
        return 1

    if S == 1 or (S == 2 and D < 20):
        return 2

    if S == 2 and D >= 300:
        return 2

    if (S == 2 and 20 <= D < 60) or S == 3:
        return 3

    if S >= 10 and D >= 180:
        return 5

    if (S == 2 and 60 <= D < 300) or (4 <= S < 10):
        return 4

    return 4


def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}:{s:02d}"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


def calculate_activity(visits_file, hits_file):
    visits = load_json(visits_file)
    hits = load_json(hits_file)
    hits_by_wid = group_hits_by_wid(hits)

    results = []
    for v in visits:
        slots = count_slots(v["ym:s:watchIDs"], hits_by_wid)
        score = score_visit(v, slots)
        results.append({
            "visitId": v["ym:s:visitID"],
            "dateTime": datetime.strptime(v["ym:s:dateTime"], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%y %H:%M:%S"),
            "duration": format_duration(v["ym:s:visitDuration"]),
            "activityLevel": score,
        })
    return results


def main():
    visits = "raw_visits_2025-06-25.json"
    hits = "raw_hits_2025-06-25.json"
    output = "activity_2025-06-25.json"
    results = calculate_activity(visits, hits)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
