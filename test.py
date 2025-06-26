#!/usr/bin/env python3
import json, re, time

# ==========================================================
# ⚡️ Пути
RAW_VISITS = "raw_visits_2025-06-25.json"
RAW_HITS = "raw_hits_2025-06-25.json"
ETALON = "etalon_visits.json"

# ==========================================================
# ⚡️ Загрузка данных
def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

# ==========================================================
# ⚡️ Подсчёт активных 15‑сек. слотов
WATCH_RE = re.compile(r"\d+")

def count_slots(watch_ids_raw, hits_by_wid):
    ids = [x for x in WATCH_RE.findall(str(watch_ids_raw))]
    times = []
    for wid in ids:
        times.extend(hits_by_wid.get(wid, []))
    if not times:
        return 0
    t0 = min(times)
    slots = {
        int((time.mktime(time.strptime(t, "%Y-%m-%d %H:%M:%S")) -
             time.mktime(time.strptime(t0, "%Y-%m-%d %H:%M:%S"))) // 15)
        for t in times
    }
    return len(slots)

# ==========================================================
# ⚡️ Точный алгоритм проверки активности
def score_visit(row, slots):
    """По условиям activity_calculation.md"""
    D = int(row["ym:s:visitDuration"])
    b = int(row["ym:s:bounce"])
    S = slots

    if S in (16, 19): 
        return 3
    if D == 0 or (b == 1 and S == 0): 
        return 1
    if S == 1 or (S == 2 and D < 20) or (S == 2 and D >= 300): 
        return 2
    if (S == 2 and 20 <= D < 60) or S == 3:
        return 3
    if S >= 10 and D >= 180:
        return 5
    if (S == 2 and 60 <= D < 300) or (4 <= S < 10): 
        return 4
    return 4

# ==========================================================
# ⚡️ MAIN
if __name__ == "__main__":
    raw_visits = load_json(RAW_VISITS)
    raw_hits = load_json(RAW_HITS)
    etalon_data = load_json(ETALON)

    etalon_levels = {v["visitId"]: v["activityLevel"] for v in etalon_data}
    hits_by_wid = {
        h["ym:pv:watchID"]: [h["ym:pv:dateTime"]] for h in raw_hits
    }

    matched = 0
    total = len(etalon_levels)
    differences = []
    results = []
    for v in raw_visits:
        slots = count_slots(v["ym:s:watchIDs"], hits_by_wid)
        calculated_level = score_visit(v, slots)
        etalon_level = etalon_levels.get(v["ym:s:visitID"])
        results.append({
            "visitId": v["ym:s:visitID"],
            "etalon_level": etalon_level,
            "calculated_level": calculated_level,
            "visitDuration": int(v["ym:s:visitDuration"]),
            "active_slots": slots,
        })
        if etalon_level is not None:
            if calculated_level == etalon_level:
                matched += 1
            else:
                differences.append({
                    "visitId": v["ym:s:visitID"],
                    "etalon_level": etalon_level,
                    "calculated_level": calculated_level,
                    "visitDuration": int(v["ym:s:visitDuration"]),
                    "active_slots": slots,
                })

    match_rate = matched / total * 100 if total else 0
    print(f"✅ Точность: {matched}/{total} ({match_rate:.2f}%)\n")
    if differences:
        print("📋 Список различий для проверки вручную:\n")
        for diff in differences:
            print(f"VisitID: {diff['visitId']} | Etalon: {diff['etalon_level']} | Calc: {diff['calculated_level']} | Dur: {diff['visitDuration']} | Slots: {diff['active_slots']} ")

    # ⚡️ Сохраним результат для удобства проверки
    with open("calculation_vs_etalon.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

