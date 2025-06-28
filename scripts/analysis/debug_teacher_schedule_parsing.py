#!/usr/bin/env python3
"""teacher_schedule.csvの解析デバッグ"""
import csv

# teacher_schedule.csvを読み込み
with open('data/output/teacher_schedule.csv', 'r', encoding='utf-8-sig') as f:
    teacher_lines = list(csv.reader(f))

print("=== teacher_schedule.csvの内容確認 ===")
print()

# ヘッダー確認
print("ヘッダー行1:", teacher_lines[0][:7])
print("ヘッダー行2:", teacher_lines[1][:7])
print()

# 5組を担当している教師を探す
print("【5組を担当している教師】")
for i, line in enumerate(teacher_lines[2:], 2):
    if not line or not line[0]:
        continue
    teacher_name = line[0]
    
    # 5組の担当があるか確認
    has_grade5 = False
    grade5_slots = []
    
    for j in range(1, min(31, len(line))):
        if line[j] and ('1-5' in line[j] or '2-5' in line[j] or '3-5' in line[j]):
            has_grade5 = True
            day_idx = (j - 1) // 6
            period_idx = (j - 1) % 6
            days = ['月', '火', '水', '木', '金']
            periods = [1, 2, 3, 4, 5, 6]
            time_key = f"{days[day_idx]}{periods[period_idx]}"
            grade5_slots.append(f"{time_key}: {line[j]}")
    
    if has_grade5:
        print(f"\n{teacher_name}:")
        for slot in grade5_slots:
            print(f"  {slot}")

# 特定の時間の詳細を確認
print("\n【月曜1限の担当状況】")
for i, line in enumerate(teacher_lines[2:], 2):
    if not line or not line[0]:
        continue
    teacher_name = line[0]
    if len(line) > 1 and line[1]:  # 月曜1限
        print(f"{teacher_name}: {line[1]}")