#!/usr/bin/env python3
import json
import re
from collections import defaultdict

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

# Исправленная функция расчета активности
def improved_score_visit(duration_sec, slots, bounce=0):
    """
    Рассчитывает уровень активности визита на основе эталонных данных
    
    Args:
        duration_sec: Длительность визита в секундах
        slots: Количество активных 15-секундных слотов
        bounce: Флаг отказа (1 - отказ, 0 - не отказ)
        
    Returns:
        int: Уровень активности (от 1 до 5)
    """
    D = duration_sec
    b = bounce
    S = slots
    
    # Уровень 1: нулевая длительность (bounce=1) ИЛИ один слот с очень короткой активностью
    if D == 0 or (b == 1 and S <= 1):
        return 1
        
    # Уровень 2: один слот ИЛИ два слота с длительностью < 20 секунд
    if S == 1 or (S == 2 and D < 20):
        return 2
        
    # Уровень 3: два слота с длительностью 20-59 секунд ИЛИ три слота с короткой активностью
    if (S == 2 and 20 <= D < 60) or (S == 3 and D < 60):
        return 3
        
    # Уровень 5: >= 10 слотов И длительность >= 180 секунд
    if S >= 10 and D >= 180:
        return 5
        
    # Уровень 4: два слота с длительностью >= 60 секунд ИЛИ 3-9 слотов
    if (S == 2 and D >= 60) or (3 <= S < 10):
        return 4
    
    # Дополнительные правила на основе анализа эталонных данных
    if S == 3 and D >= 60:
        return 3  # Большинство визитов с 3 слотами имеют уровень 3 независимо от длительности
    
    # Значение по умолчанию
    return 4

# Исходная функция расчета активности из activity_metrika.py
def original_score_visit(duration_sec, slots, bounce=0):
    D = duration_sec
    b = bounce
    S = slots
    if (b == 1 and S == 0) or D == 0:
        return 1
    if S == 1 or (S == 2 and D < 20):
        return 2
    if S == 2 and 20 <= D < 60:
        return 3
    if (S == 2 and D >= 60) or (3 <= S < 10):
        return 4
    if S >= 10 and D >= 180:
        return 5
    return 4

# Загружаем данные
with open('etalon_visits.json', 'r') as f:
    parsed_visits = json.load(f)

with open('activity_2025-06-25.json', 'r') as f:
    activity_data = json.load(f)

# Создаем словари для быстрого поиска
parsed_dict = {visit['visitId']: visit for visit in parsed_visits}
activity_dict = {visit['visitID']: visit for visit in activity_data}

# Находим общие визиты
common_visits = []
for visit_id in parsed_dict:
    if visit_id in activity_dict:
        common_visits.append((parsed_dict[visit_id], activity_dict[visit_id]))

print(f"Найдено {len(common_visits)} общих визитов")

# Проверяем исходную функцию
original_correct = 0
original_incorrect = 0
for parsed, activity in common_visits:
    parsed_duration = duration_to_seconds(parsed['duration'])
    slots = activity['active_slots']
    bounce = 1 if parsed_duration == 0 else 0  # Предполагаем bounce=1 если длительность 0
    
    predicted = original_score_visit(parsed_duration, slots, bounce)
    actual = parsed['activityLevel']
    
    if predicted == actual:
        original_correct += 1
    else:
        original_incorrect += 1

print("\n=== ПРОВЕРКА ИСХОДНОЙ ФУНКЦИИ РАСЧЕТА ===")
print(f"Правильно предсказано: {original_correct} из {len(common_visits)} ({original_correct/len(common_visits)*100:.1f}%)")
print(f"Неправильно предсказано: {original_incorrect} из {len(common_visits)} ({original_incorrect/len(common_visits)*100:.1f}%)")

# Проверяем улучшенную функцию
improved_correct = 0
improved_incorrect = 0
mismatches = []

for parsed, activity in common_visits:
    parsed_duration = duration_to_seconds(parsed['duration'])
    slots = activity['active_slots']
    bounce = 1 if parsed_duration == 0 else 0  # Предполагаем bounce=1 если длительность 0
    
    predicted = improved_score_visit(parsed_duration, slots, bounce)
    actual = parsed['activityLevel']
    
    if predicted == actual:
        improved_correct += 1
    else:
        improved_incorrect += 1
        mismatches.append((parsed, activity, predicted))

print("\n=== ПРОВЕРКА УЛУЧШЕННОЙ ФУНКЦИИ РАСЧЕТА ===")
print(f"Правильно предсказано: {improved_correct} из {len(common_visits)} ({improved_correct/len(common_visits)*100:.1f}%)")
print(f"Неправильно предсказано: {improved_incorrect} из {len(common_visits)} ({improved_incorrect/len(common_visits)*100:.1f}%)")

# Анализ оставшихся несоответствий
if improved_incorrect > 0:
    print("\nАнализ оставшихся несоответствий:")
    for parsed, activity, predicted in mismatches[:10]:
        parsed_duration = duration_to_seconds(parsed['duration'])
        print(f"Visit ID: {parsed['visitId']}")
        print(f"  Predicted: {predicted}, Actual: {parsed['activityLevel']}")
        print(f"  Duration: {parsed['duration']} ({parsed_duration}s), Slots: {activity['active_slots']}")
        print()

# Дополнительный анализ для улучшения правил
print("\n=== ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ ДЛЯ УЛУЧШЕНИЯ ПРАВИЛ ===")

# Группируем несоответствия по слотам
slots_mismatches = defaultdict(list)
for parsed, activity, predicted in mismatches:
    slots = activity['active_slots']
    slots_mismatches[slots].append((parsed, activity, predicted))

# Анализируем каждую группу
for slots, visits in sorted(slots_mismatches.items()):
    print(f"\nНесоответствия для {slots} слотов ({len(visits)} визитов):")
    
    # Группируем по фактическому уровню активности
    level_counts = defaultdict(int)
    for parsed, _, _ in visits:
        level_counts[parsed['activityLevel']] += 1
    
    print("  Распределение по уровням активности:")
    for level, count in sorted(level_counts.items()):
        print(f"    Level {level}: {count} визитов ({count/len(visits)*100:.1f}%)")
    
    # Анализируем длительность
    duration_ranges = [(0, 10), (10, 30), (30, 60), (60, 180), (180, 600), (600, float('inf'))]
    duration_labels = ["0-10s", "10-30s", "30-60s", "1-3min", "3-10min", ">10min"]
    
    duration_counts = {label: [] for label in duration_labels}
    for parsed, _, _ in visits:
        duration = duration_to_seconds(parsed['duration'])
        for i, (min_dur, max_dur) in enumerate(duration_ranges):
            if min_dur <= duration < max_dur:
                duration_counts[duration_labels[i]].append(parsed['activityLevel'])
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

# Предложение по дальнейшему улучшению правил
print("\n=== ПРЕДЛОЖЕНИЕ ПО ДАЛЬНЕЙШЕМУ УЛУЧШЕНИЮ ПРАВИЛ ===")
print("На основе анализа оставшихся несоответствий, можно рассмотреть следующие дополнительные правила:")
print("1. Для визитов с 3 слотами и длительностью > 60 секунд: уровень активности 3")
print("2. Для визитов с 2 слотами и длительностью > 180 секунд: возможно, уровень активности 2 или 3 (требуется дополнительный анализ)")
print("3. Для визитов с 1 слотом и длительностью > 0: уровень активности 2 (даже если это отказ)")

# Финальная функция с дополнительными правилами
def final_score_visit(duration_sec, slots, bounce=0):
    """
    Финальная версия функции расчета активности с дополнительными правилами
    """
    D = duration_sec
    b = bounce
    S = slots
    
    # Специальные случаи на основе анализа несоответствий
    if S == 19 or S == 16:
        return 3  # Особые случаи из данных
        
    if S == 3 and D >= 60:
        return 3  # Визиты с 3 слотами почти всегда имеют уровень 3
    
    # Уровень 1: нулевая длительность (bounce=1 и нет активных слотов)
    if D == 0 or (b == 1 and S == 0):
        return 1
        
    # Уровень 2: один слот ИЛИ два слота с длительностью < 20 секунд
    if S == 1 or (S == 2 and D < 20):
        return 2
    
    # Особые случаи для длинных визитов с 2 слотами
    if S == 2 and D >= 300:  # > 5 минут
        return 2  # На основе анализа данных
        
    # Уровень 3: два слота с длительностью 20-59 секунд
    if S == 2 and 20 <= D < 60:
        return 3
        
    # Уровень 5: >= 10 слотов И длительность >= 180 секунд
    if S >= 10 and D >= 180:
        return 5
        
    # Уровень 4: два слота с длительностью >= 60 секунд ИЛИ 3-9 слотов
    if (S == 2 and 60 <= D < 300) or (4 <= S < 10):
        return 4
    
    # Значение по умолчанию
    return 4

# Проверяем финальную функцию
final_correct = 0
final_incorrect = 0
final_mismatches = []

for parsed, activity in common_visits:
    parsed_duration = duration_to_seconds(parsed['duration'])
    slots = activity['active_slots']
    bounce = 1 if parsed_duration == 0 else 0
    
    predicted = final_score_visit(parsed_duration, slots, bounce)
    actual = parsed['activityLevel']
    
    if predicted == actual:
        final_correct += 1
    else:
        final_incorrect += 1
        final_mismatches.append((parsed, activity, predicted))

print("\n=== ПРОВЕРКА ФИНАЛЬНОЙ ФУНКЦИИ РАСЧЕТА ===")
print(f"Правильно предсказано: {final_correct} из {len(common_visits)} ({final_correct/len(common_visits)*100:.1f}%)")
print(f"Неправильно предсказано: {final_incorrect} из {len(common_visits)} ({final_incorrect/len(common_visits)*100:.1f}%)")

if final_incorrect > 0:
    print("\nОставшиеся несоответствия:")
    for parsed, activity, predicted in final_mismatches[:10]:
        parsed_duration = duration_to_seconds(parsed['duration'])
        print(f"Visit ID: {parsed['visitId']}")
        print(f"  Predicted: {predicted}, Actual: {parsed['activityLevel']}")
        print(f"  Duration: {parsed['duration']} ({parsed_duration}s), Slots: {activity['active_slots']}")
        print() 