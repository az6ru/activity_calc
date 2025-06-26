#!/usr/bin/env python3
import time, re, requests, csv, gzip, json
from datetime import datetime

# ==========================================================
# ⚡️ КОНФИГУРАЦИЯ
TOKEN = "y0__xCT9MGJCBjaxDggqOGQ0hMUlEeVbEduRi757cwE0_qAtaI5xw"
COUNTER = 45047126
DATE = "2025-06-25"
HEADERS = {"Authorization": f"OAuth {TOKEN}"}
WATCH_RE = re.compile(r"\d+")

# ==========================================================
# ⚡️ СОЗДАНИЕ ЗАПРОСА
def create_request(source):
    url = f"https://api-metrika.yandex.net/management/v1/counter/{COUNTER}/logrequests"
    fields = (
        "ym:s:visitID,ym:s:clientID,ym:s:watchIDs,ym:s:dateTime,ym:s:visitDuration,ym:s:bounce,ym:s:pageViews"
        if source == "visits"
        else "ym:pv:watchID,ym:pv:dateTime"
    )
    params = {"date1": DATE, "date2": DATE, "fields": fields, "source": source}
    r = requests.post(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()["log_request"]["request_id"]

# ==========================================================
# ⚡️ ЖДЁМ СТАТУС
def wait_processed(request_id):
    url = f"https://api-metrika.yandex.net/management/v1/counter/{COUNTER}/logrequest/{request_id}"
    while True:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        status = r.json()["log_request"]["status"]
        if status == "processed":
            return
        if status not in ("created", "awaiting_retry"):
            raise RuntimeError(f"Error status: {status}")
        time.sleep(10)

# ==========================================================
# ⚡️ СКАЧИВАЕМ ДАННЫЕ
def download(request_id):
    url = f"https://api-metrika.yandex.net/management/v1/counter/{COUNTER}/logrequest/{request_id}/part/0/download"
    r = requests.get(url, headers=HEADERS, stream=True)
    r.raise_for_status()
    with gzip.open(r.raw, mode="rt") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)

# ==========================================================
# ⚡️ УДАЛЯЕМ ЗАПРОС
def delete_request(request_id):
    url = f"https://api-metrika.yandex.net/management/v1/counter/{COUNTER}/logrequest/{request_id}/clean"
    r = requests.post(url, headers=HEADERS)
    r.raise_for_status()
    print(f"🗑️ Запрос {request_id} успешно очищен.")

# ==========================================================
# ⚡️ РАСЧЁТ ACTIVE_SLOTS
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
# ⚡️ РАСЧЁТ SCORE
def score_visit(row, slots):
    D = int(row["ym:s:visitDuration"])
    b = int(row["ym:s:bounce"])
    S = slots
    if S == 19 or S == 16:
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

# ==========================================================
# ⚡️ ФОРМАТИРОВАНИЕ ДЛИТЕЛЬНОСТИ
def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:02d}"

# ==========================================================
# ⚡️ MAIN
if __name__ == "__main__":
    print(f"🚀 Запускаю обработку для даты: {DATE}")

    request_id_visits = create_request("visits")
    request_id_hits = create_request("hits")
    print(f"✅ Visits request id: {request_id_visits}")
    print(f"✅ Hits request id: {request_id_hits}")

    wait_processed(request_id_visits)
    wait_processed(request_id_hits)

    vis_data = download(request_id_visits)
    hits_data = download(request_id_hits)

    # ➕ Сохраняем сырые данные
    with open(f"raw_visits_{DATE}.json", "w", encoding="utf-8") as fv:
        json.dump(vis_data, fv, ensure_ascii=False, indent=2)

    with open(f"raw_hits_{DATE}.json", "w", encoding="utf-8") as fh:
        json.dump(hits_data, fh, ensure_ascii=False, indent=2)

    print(f"✅ Сырые данные сохранены в raw_visits_{DATE}.json и raw_hits_{DATE}.json")

    hits_by_wid = {}
    for h in hits_data:
        wid = h["ym:pv:watchID"]
        hits_by_wid.setdefault(wid, []).append(h["ym:pv:dateTime"])
    print(f"✅ Сгруппировано {len(hits_by_wid)} уникальных watchID")

    results = []
    activity_levels = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for v in vis_data:
        slots = count_slots(v["ym:s:watchIDs"], hits_by_wid)
        sc = score_visit(v, slots)
        activity_levels[sc] += 1
        results.append({
            "visitID": v["ym:s:visitID"],
            "clientID": v["ym:s:clientID"],
            "dateTime": v["ym:s:dateTime"],
            "visitDuration": int(v["ym:s:visitDuration"]),
            "duration": format_duration(v["ym:s:visitDuration"]),
            "pageViews": int(v["ym:s:pageViews"]),
            "active_slots": slots,
            "score": sc
        })

    # Сохраняем обработанную активность
    filename = f"activity_{DATE}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_visits = len(results)
    print("\n=== СТАТИСТИКА ПО УРОВНЯМ АКТИВНОСТИ ===")
    for level in sorted(activity_levels.keys()):
        count = activity_levels[level]
        percentage = (count / total_visits) * 100 if total_visits else 0
        print(f"Уровень {level}: {count} визитов ({percentage:.1f}%)")
    print(f"\n✅ Готово! Итоговый результат сохранён в {filename}")

    delete_request(request_id_visits)
    delete_request(request_id_hits)

