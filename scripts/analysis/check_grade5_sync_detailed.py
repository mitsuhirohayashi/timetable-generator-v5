#!/usr/bin/env python3
"""5組の同期状態を詳しくチェック"""
import csv
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# output.csvを読み込み
with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
    lines = list(csv.reader(f))

# teacher_schedule.csvを読み込み
teacher_assignments = {}
try:
    with open('data/output/teacher_schedule.csv', 'r', encoding='utf-8-sig') as f:
        teacher_lines = list(csv.reader(f))
        
    # 教師ごとの担当を解析
    for i, line in enumerate(teacher_lines[2:], 2):  # ヘッダーをスキップ
        if not line or not line[0]:
            continue
        teacher_name = line[0]
        
        # 各時限の担当クラスを記録
        for j in range(1, min(31, len(line))):
            if line[j]:
                classes = line[j].split(',')
                for cls in classes:
                    cls = cls.strip()
                    if '5組' in cls:
                        day_idx = (j - 1) // 6
                        period_idx = (j - 1) % 6
                        days = ['月', '火', '水', '木', '金']
                        periods = [1, 2, 3, 4, 5, 6]
                        time_key = f"{days[day_idx]}{periods[period_idx]}"
                        
                        if time_key not in teacher_assignments:
                            teacher_assignments[time_key] = {}
                        teacher_assignments[time_key][cls] = teacher_name
except:
    print("teacher_schedule.csvが見つかりません")

print('=== 5組の同期状態を詳しくチェック ===')
print()

days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]

# 各時限での5組の授業内容をチェック
sync_issues = []
for day in days:
    for period in periods:
        time_slot = f'{day}{period}'
        subjects = {}
        teachers = {}
        
        # 各5組の授業を取得
        for i, line in enumerate(lines):
            if line and line[0] in ['1年5組', '2年5組', '3年5組']:
                class_name = line[0]
                day_idx = days.index(day)
                period_idx = period - 1
                col_idx = day_idx * 6 + period_idx + 1
                
                if col_idx < len(line) and line[col_idx]:
                    subject = line[col_idx]
                    subjects[class_name] = subject
                    
                    # 教師情報を取得
                    teacher_key = f"{time_slot}"
                    if teacher_key in teacher_assignments and class_name in teacher_assignments[teacher_key]:
                        teachers[class_name] = teacher_assignments[teacher_key][class_name]
        
        # 同期チェック
        if len(set(subjects.values())) > 1:
            sync_issues.append({
                'time': time_slot,
                'subjects': subjects,
                'teachers': teachers
            })

if sync_issues:
    print('【同期違反が見つかりました】')
    for issue in sync_issues:
        print(f"\n{issue['time']}校時:")
        for cls, subj in issue['subjects'].items():
            teacher = issue['teachers'].get(cls, '不明')
            print(f"  {cls}: {subj} (教師: {teacher})")
else:
    print('5組は正しく同期されています')

# 各5組の教科別担当教師をチェック
print('\n\n=== 5組の教科別担当教師 ===')
subject_teachers = {}

for i, line in enumerate(lines):
    if line and line[0] in ['1年5組', '2年5組', '3年5組']:
        class_name = line[0]
        
        for j in range(1, min(31, len(line))):
            if line[j]:
                subject = line[j]
                day_idx = (j - 1) // 6
                period_idx = (j - 1) % 6
                time_key = f"{days[day_idx]}{periods[period_idx]}"
                
                if time_key in teacher_assignments and class_name in teacher_assignments[time_key]:
                    teacher = teacher_assignments[time_key][class_name]
                    
                    if subject not in subject_teachers:
                        subject_teachers[subject] = {}
                    if class_name not in subject_teachers[subject]:
                        subject_teachers[subject][class_name] = set()
                    subject_teachers[subject][class_name].add(teacher)

# 教科ごとの教師を表示
for subject in sorted(subject_teachers.keys()):
    print(f"\n{subject}:")
    for cls in ['1年5組', '2年5組', '3年5組']:
        if cls in subject_teachers[subject]:
            teachers = list(subject_teachers[subject][cls])
            print(f"  {cls}: {', '.join(teachers)}")
        else:
            print(f"  {cls}: 未配置")