#!/usr/bin/env python3
import json
import re
from collections import defaultdict
import time
from datetime import datetime

# Функция для конвертации строки длительности в секунды
def duration_to_seconds(duration_str):
    if not duration_str or duration_str == "0:00":
        return 0
    
    # Парсим формат "H:MM" или "MM:SS" или "H:MM:SS"
    parts = duration_str.split(":")
    if len(parts) == 2:
        # Формат "MM:SS" или "H:MM"
        if int(parts[0]) >= 60:  # Если первое число >= 60, это часы
            return int(parts[0]) * 60 * 60 + int(parts[1]) * 60
        else:
            return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        # Формат "H:MM:SS"
        return int(parts[0]) * 60 * 60 + int(parts[1]) * 60 + int(parts[2])
    else:
        return 0

# Функция для расчета активных слотов
def count_slots(hit_times):
    if not hit_times:
        return 0
    
    # Находим начальное время (минимальное)
    try:
        t0 = min(hit_times)
        
        # Считаем уникальные 15-секундные слоты
        slots = {
            int((time.mktime(time.strptime(t, "%Y-%m-%d %H:%M:%S")) -
                 time.mktime(time.strptime(t0, "%Y-%m-%d %H:%M:%S"))) // 15)
            for t in hit_times
        }
        return len(slots)
    except:
        return 0

# Функция для детального анализа визита
def analyze_visit_details(visit_id, raw_visits, raw_hits, etalon_visits, activity_data):
    """
    Проводит детальный анализ конкретного визита
    """
    # Находим визит в разных источниках данных
    etalon_visit = next((v for v in etalon_visits if v["visitId"] == visit_id), None)
    activity_visit = next((v for v in activity_data if v["visitID"] == visit_id), None)
    
    if not etalon_visit or not activity_visit:
        print(f"Визит {visit_id} не найден во всех источниках данных")
        return
    
    # Собираем хиты для этого визита
    visit_hits = []
    for v in raw_visits:
        if v["ym:s:visitID"] == visit_id:
            watch_ids = re.findall(r"\d+", str(v.get("ym:s:watchIDs", "")))
            for h in raw_hits:
                if h["ym:pv:watchID"] in watch_ids:
                    visit_hits.append(h)
    
    # Выводим основную информацию
    print(f"\n=== ДЕТАЛЬНЫЙ АНАЛИЗ ВИЗИТА {visit_id} ===")
    print(f"Длительность: {etalon_visit.get('duration')} ({duration_to_seconds(etalon_visit.get('duration'))}s)")
    print(f"Активные слоты: {activity_visit.get('active_slots')}")
    print(f"Эталонный уровень активности: {etalon_visit.get('activityLevel')}")
    print(f"Рассчитанный уровень: {activity_visit.get('score')}")
    print(f"Bounce: {activity_visit.get('bounce')}")
    
    # Анализ хитов
    print(f"\nВсего хитов: {len(visit_hits)}")
    if visit_hits:
        # Сортируем хиты по времени
        visit_hits.sort(key=lambda h: h["ym:pv:dateTime"])
        
        # Выводим временную шкалу хитов
        print("\nВременная шкала хитов:")
        first_hit_time = visit_hits[0]["ym:pv:dateTime"]
        for i, hit in enumerate(visit_hits):
            hit_time = hit["ym:pv:dateTime"]
            time_diff = 0
            if i > 0:
                prev_time = time.mktime(time.strptime(visit_hits[i-1]["ym:pv:dateTime"], "%Y-%m-%d %H:%M:%S"))
                curr_time = time.mktime(time.strptime(hit_time, "%Y-%m-%d %H:%M:%S"))
                time_diff = int(curr_time - prev_time)
            
            # Рассчитываем слот для этого хита
            first_time = time.mktime(time.strptime(first_hit_time, "%Y-%m-%d %H:%M:%S"))
            curr_time = time.mktime(time.strptime(hit_time, "%Y-%m-%d %H:%M:%S"))
            slot = int((curr_time - first_time) // 15)
            
            print(f"  {i+1}. {hit_time} | +{time_diff}s | Слот: {slot}")
    
    # Предложение по корректировке правил
    print("\nПредложение по корректировке правил:")
    duration = duration_to_seconds(etalon_visit.get('duration'))
    slots = activity_visit.get('active_slots')
    bounce = activity_visit.get('bounce')
    actual_level = etalon_visit.get('activityLevel')
    
    if slots == 1 and duration > 0:
        if actual_level == 1:
            print(f"  Для визитов с 1 слотом и длительностью {duration}s нужно устанавливать уровень 1")
        elif actual_level == 2:
            print(f"  Для визитов с 1 слотом и длительностью {duration}s нужно устанавливать уровень 2")
    
    if slots == 2:
        if actual_level == 1 and duration < 20:
            print(f"  Для визитов с 2 слотами, bounce={bounce} и длительностью {duration}s нужно устанавливать уровень 1")
        elif actual_level == 2 and duration >= 20:
            print(f"  Для визитов с 2 слотами и длительностью {duration}s нужно устанавливать уровень 2 вместо 3/4")
        elif actual_level == 3 and duration >= 60:
            print(f"  Для визитов с 2 слотами и длительностью {duration}s нужно устанавливать уровень 3 вместо 4")
    
    if slots == 3:
        if actual_level == 2:
            print(f"  Для визитов с 3 слотами и длительностью {duration}s нужно устанавливать уровень 2 вместо 3")
        elif actual_level == 4:
            print(f"  Для визитов с 3 слотами и длительностью {duration}s нужно устанавливать уровень 4 вместо 3")

# Загрузка данных
def load_data(date="2025-06-25"):
    print("Загрузка данных...")
    
    # Загружаем эталонные данные
    with open('etalon_visits.json', 'r') as f:
        etalon_visits = json.load(f)
    
    # Загружаем рассчитанные данные активности
    with open(f'activity_{date}.json', 'r') as f:
        activity_data = json.load(f)
    
    # Загружаем сырые данные
    try:
        with open(f'raw_visits_{date}.json', 'r') as f:
            raw_visits = json.load(f)
        
        with open(f'raw_hits_{date}.json', 'r') as f:
            raw_hits = json.load(f)
    except FileNotFoundError:
        print("Сырые данные не найдены. Запустите metrika_activity.py с SAVE_RAW_DATA=True")
        raw_visits = []
        raw_hits = []
    
    print(f"Загружено {len(etalon_visits)} эталонных визитов")
    print(f"Загружено {len(activity_data)} рассчитанных визитов")
    print(f"Загружено {len(raw_visits)} сырых визитов и {len(raw_hits)} сырых хитов")
    
    return etalon_visits, activity_data, raw_visits, raw_hits

# Анализ несоответствий
def analyze_mismatches(etalon_visits, activity_data):
    """
    Анализирует несоответствия между эталонными и рассчитанными уровнями активности
    """
    # Создаем словари для быстрого поиска
    etalon_dict = {visit['visitId']: visit for visit in etalon_visits}
    activity_dict = {visit['visitID']: visit for visit in activity_data}
    
    # Находим общие визиты
    common_visits = []
    for visit_id in etalon_dict:
        if visit_id in activity_dict:
            common_visits.append((etalon_dict[visit_id], activity_dict[visit_id]))
    
    print(f"Найдено {len(common_visits)} общих визитов")
    
    # Проверяем соответствия
    correct = 0
    incorrect = 0
    mismatches = []
    
    for etalon, activity in common_visits:
        if etalon['activityLevel'] == activity['score']:
            correct += 1
        else:
            incorrect += 1
            mismatches.append((etalon, activity))
    
    print(f"\n=== РЕЗУЛЬТАТЫ СРАВНЕНИЯ ===")
    print(f"Правильно предсказано: {correct} из {len(common_visits)} ({correct/len(common_visits)*100:.1f}%)")
    print(f"Неправильно предсказано: {incorrect} из {len(common_visits)} ({incorrect/len(common_visits)*100:.1f}%)")
    
    # Группируем несоответствия по слотам
    slots_mismatches = defaultdict(list)
    for etalon, activity in mismatches:
        slots = activity['active_slots']
        slots_mismatches[slots].append((etalon, activity))
    
    # Анализируем каждую группу
    print("\n=== АНАЛИЗ НЕСООТВЕТСТВИЙ ПО СЛОТАМ ===")
    for slots, visits in sorted(slots_mismatches.items()):
        print(f"\nНесоответствия для {slots} слотов ({len(visits)} визитов):")
        
        # Группируем по фактическому уровню активности
        level_counts = defaultdict(int)
        for etalon, _ in visits:
            level_counts[etalon['activityLevel']] += 1
        
        print("  Распределение по уровням активности:")
        for level, count in sorted(level_counts.items()):
            print(f"    Level {level}: {count} визитов ({count/len(visits)*100:.1f}%)")
        
        # Анализируем длительность
        duration_ranges = [(0, 10), (10, 30), (30, 60), (60, 180), (180, 600), (600, float('inf'))]
        duration_labels = ["0-10s", "10-30s", "30-60s", "1-3min", "3-10min", ">10min"]
        
        duration_counts = {label: [] for label in duration_labels}
        for etalon, _ in visits:
            duration = duration_to_seconds(etalon['duration'])
            for i, (min_dur, max_dur) in enumerate(duration_ranges):
                if min_dur <= duration < max_dur:
                    duration_counts[duration_labels[i]].append(etalon['activityLevel'])
                    break
        
        print("  Распределение по длительности:")
        for label, levels in duration_counts.items():
            if levels:
                level_counts = defaultdict(int)
                for level in levels:
                    level_counts[level] += 1
                
                print(f"    {label}:")
                for level, count in sorted(level_counts.items()):
                    print(f"      Level {level}: {count} визитов ({count/len(levels)*100:.1f}%)")
    
    return mismatches

# Генерация улучшенных правил
def generate_improved_rules(mismatches):
    """
    Генерирует предложения по улучшению правил на основе анализа несоответствий
    """
    print("\n=== ПРЕДЛОЖЕНИЯ ПО УЛУЧШЕНИЮ ПРАВИЛ ===")
    
    # Анализ визитов с 1 слотом
    slots_1_mismatches = [(e, a) for e, a in mismatches if a['active_slots'] == 1]
    if slots_1_mismatches:
        print("\n1. Визиты с 1 слотом:")
        
        level_1_count = sum(1 for e, _ in slots_1_mismatches if e['activityLevel'] == 1)
        level_2_count = sum(1 for e, _ in slots_1_mismatches if e['activityLevel'] == 2)
        level_3_count = sum(1 for e, _ in slots_1_mismatches if e['activityLevel'] == 3)
        
        total = len(slots_1_mismatches)
        print(f"   - Уровень 1: {level_1_count}/{total} ({level_1_count/total*100:.1f}%)")
        print(f"   - Уровень 2: {level_2_count}/{total} ({level_2_count/total*100:.1f}%)")
        print(f"   - Уровень 3: {level_3_count}/{total} ({level_3_count/total*100:.1f}%)")
        
        # Анализ по длительности
        short_visits = [(e, a) for e, a in slots_1_mismatches if duration_to_seconds(e['duration']) < 10]
        if short_visits:
            short_level_1 = sum(1 for e, _ in short_visits if e['activityLevel'] == 1)
            short_level_2 = sum(1 for e, _ in short_visits if e['activityLevel'] == 2)
            print(f"   - Короткие визиты (<10s): Уровень 1 - {short_level_1}, Уровень 2 - {short_level_2}")
        
        # Предложение правила
        if level_1_count > level_2_count:
            print("   🔄 Предлагаемое правило: Все визиты с 1 слотом и длительностью < 10 секунд -> Уровень 1")
        else:
            print("   🔄 Предлагаемое правило: Все визиты с 1 слотом -> Уровень 2")
    
    # Анализ визитов с 2 слотами
    slots_2_mismatches = [(e, a) for e, a in mismatches if a['active_slots'] == 2]
    if slots_2_mismatches:
        print("\n2. Визиты с 2 слотами:")
        
        # Группируем по длительности
        short = [(e, a) for e, a in slots_2_mismatches if duration_to_seconds(e['duration']) < 20]
        medium = [(e, a) for e, a in slots_2_mismatches if 20 <= duration_to_seconds(e['duration']) < 60]
        long = [(e, a) for e, a in slots_2_mismatches if 60 <= duration_to_seconds(e['duration']) < 300]
        very_long = [(e, a) for e, a in slots_2_mismatches if duration_to_seconds(e['duration']) >= 300]
        
        # Анализируем каждую группу
        if short:
            level_1 = sum(1 for e, _ in short if e['activityLevel'] == 1)
            level_2 = sum(1 for e, _ in short if e['activityLevel'] == 2)
            print(f"   - Короткие (<20s): Уровень 1 - {level_1}, Уровень 2 - {level_2}")
            if level_1 > level_2:
                print("   🔄 Предлагаемое правило: Визиты с 2 слотами и длительностью < 20 секунд, bounce=1 -> Уровень 1")
        
        if medium:
            level_2 = sum(1 for e, _ in medium if e['activityLevel'] == 2)
            level_3 = sum(1 for e, _ in medium if e['activityLevel'] == 3)
            print(f"   - Средние (20-60s): Уровень 2 - {level_2}, Уровень 3 - {level_3}")
            if level_2 > level_3:
                print("   🔄 Предлагаемое правило: Визиты с 2 слотами и длительностью 20-60 секунд -> Уровень 2")
        
        if long:
            level_3 = sum(1 for e, _ in long if e['activityLevel'] == 3)
            level_4 = sum(1 for e, _ in long if e['activityLevel'] == 4)
            print(f"   - Длинные (60-300s): Уровень 3 - {level_3}, Уровень 4 - {level_4}")
            if level_3 > level_4:
                print("   🔄 Предлагаемое правило: Визиты с 2 слотами и длительностью 60-300 секунд -> Уровень 3")
        
        if very_long:
            level_2 = sum(1 for e, _ in very_long if e['activityLevel'] == 2)
            level_3 = sum(1 for e, _ in very_long if e['activityLevel'] == 3)
            level_4 = sum(1 for e, _ in very_long if e['activityLevel'] == 4)
            print(f"   - Очень длинные (>300s): Уровень 2 - {level_2}, Уровень 3 - {level_3}, Уровень 4 - {level_4}")
            if level_2 > max(level_3, level_4):
                print("   🔄 Предлагаемое правило: Визиты с 2 слотами и длительностью > 300 секунд -> Уровень 2")
    
    # Анализ визитов с 3 слотами
    slots_3_mismatches = [(e, a) for e, a in mismatches if a['active_slots'] == 3]
    if slots_3_mismatches:
        print("\n3. Визиты с 3 слотами:")
        
        level_2 = sum(1 for e, _ in slots_3_mismatches if e['activityLevel'] == 2)
        level_3 = sum(1 for e, _ in slots_3_mismatches if e['activityLevel'] == 3)
        level_4 = sum(1 for e, _ in slots_3_mismatches if e['activityLevel'] == 4)
        
        total = len(slots_3_mismatches)
        print(f"   - Уровень 2: {level_2}/{total} ({level_2/total*100:.1f}%)")
        print(f"   - Уровень 3: {level_3}/{total} ({level_3/total*100:.1f}%)")
        print(f"   - Уровень 4: {level_4}/{total} ({level_4/total*100:.1f}%)")
        
        # Анализ по длительности
        short = [(e, a) for e, a in slots_3_mismatches if duration_to_seconds(e['duration']) < 60]
        medium = [(e, a) for e, a in slots_3_mismatches if 60 <= duration_to_seconds(e['duration']) < 180]
        long = [(e, a) for e, a in slots_3_mismatches if duration_to_seconds(e['duration']) >= 180]
        
        if short and short:
            short_level_2 = sum(1 for e, _ in short if e['activityLevel'] == 2)
            short_level_3 = sum(1 for e, _ in short if e['activityLevel'] == 3)
            short_level_4 = sum(1 for e, _ in short if e['activityLevel'] == 4)
            print(f"   - Короткие (<60s): Уровень 2 - {short_level_2}, Уровень 3 - {short_level_3}, Уровень 4 - {short_level_4}")
        
        if medium:
            medium_level_2 = sum(1 for e, _ in medium if e['activityLevel'] == 2)
            medium_level_3 = sum(1 for e, _ in medium if e['activityLevel'] == 3)
            medium_level_4 = sum(1 for e, _ in medium if e['activityLevel'] == 4)
            print(f"   - Средние (60-180s): Уровень 2 - {medium_level_2}, Уровень 3 - {medium_level_3}, Уровень 4 - {medium_level_4}")
        
        if long:
            long_level_2 = sum(1 for e, _ in long if e['activityLevel'] == 2)
            long_level_3 = sum(1 for e, _ in long if e['activityLevel'] == 3)
            long_level_4 = sum(1 for e, _ in long if e['activityLevel'] == 4)
            print(f"   - Длинные (>180s): Уровень 2 - {long_level_2}, Уровень 3 - {long_level_3}, Уровень 4 - {long_level_4}")
        
        # Предложение правила
        if level_3 > max(level_2, level_4):
            print("   🔄 Предлагаемое правило: Все визиты с 3 слотами -> Уровень 3")
        elif level_4 > max(level_2, level_3):
            print("   🔄 Предлагаемое правило: Визиты с 3 слотами и длительностью > 180 секунд -> Уровень 4")

# Основная функция
def main():
    # Загружаем данные
    etalon_visits, activity_data, raw_visits, raw_hits = load_data()
    
    # Анализируем несоответствия
    mismatches = analyze_mismatches(etalon_visits, activity_data)
    
    # Генерируем предложения по улучшению правил
    generate_improved_rules(mismatches)
    
    # Предлагаем детальный анализ конкретных визитов
    print("\n=== ДЕТАЛЬНЫЙ АНАЛИЗ ВИЗИТОВ ===")
    print("Выберите визиты для детального анализа:")
    
    # Выводим первые 5 несоответствий
    for i, (etalon, activity) in enumerate(mismatches[:5]):
        visit_id = etalon['visitId']
        print(f"{i+1}. Визит {visit_id}: Эталон - {etalon['activityLevel']}, Рассчитано - {activity['score']}")
        print(f"   Длительность: {etalon['duration']}, Слоты: {activity['active_slots']}")
    
    # Анализируем первые 3 несоответствия
    for i, (etalon, activity) in enumerate(mismatches[:3]):
        visit_id = etalon['visitId']
        analyze_visit_details(visit_id, raw_visits, raw_hits, etalon_visits, activity_data)

if __name__ == "__main__":
    main() 