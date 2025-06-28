#!/usr/bin/env python3
"""5組の教師未割当の授業を特定"""
import csv
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.services.grade5_teacher_mapping_service import Grade5TeacherMappingService

# 5組の正しい教師マッピング
grade5_service = Grade5TeacherMappingService()

# output.csvを読み込み
with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
    lines = list(csv.reader(f))

# teacher_schedule.csvを読み込み  
teacher_assignments = {}
try:
    with open('data/output/teacher_schedule.csv', 'r', encoding='utf-8-sig') as f:
        teacher_lines = list(csv.reader(f))
        
    # 教師ごとの担当を解析
    for i, line in enumerate(teacher_lines[2:], 2):
        if not line or not line[0]:
            continue
        teacher_name = line[0]
        
        # 各時限の担当クラスを記録
        for j in range(1, min(31, len(line))):
            if line[j]:
                classes = line[j].split(',')
                for cls in classes:
                    cls = cls.strip()
                    # 1-5, 2-5, 3-5 形式をチェック
                    if '-5' in cls:
                        day_idx = (j - 1) // 6
                        period_idx = (j - 1) % 6
                        days = ['月', '火', '水', '木', '金']
                        periods = [1, 2, 3, 4, 5, 6]
                        time_key = f"{days[day_idx]}{periods[period_idx]}"
                        
                        if time_key not in teacher_assignments:
                            teacher_assignments[time_key] = {}
                        # 5組は合同授業なので、1-5の教師を全5組に適用
                        teacher_assignments[time_key]['1年5組'] = teacher_name
                        teacher_assignments[time_key]['2年5組'] = teacher_name
                        teacher_assignments[time_key]['3年5組'] = teacher_name
except:
    print("teacher_schedule.csvが見つかりません")

print('=== 5組の教師未割当の授業 ===')
print()

days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]

# 未割当の授業を収集
unassigned_slots = []

for day in days:
    for period in periods:
        time_slot = f'{day}{period}'
        
        # 各5組の授業を取得
        for i, line in enumerate(lines):
            if line and line[0] in ['1年5組', '2年5組', '3年5組']:
                class_name = line[0]
                day_idx = days.index(day)
                period_idx = period - 1
                col_idx = day_idx * 6 + period_idx + 1
                
                if col_idx < len(line) and line[col_idx]:
                    subject = line[col_idx]
                    
                    # 正しい教師を取得
                    correct_teacher = grade5_service.get_teacher_for_subject(subject)
                    
                    # 実際の教師を取得
                    actual_teacher = teacher_assignments.get(time_slot, {}).get(class_name, None)
                    
                    if correct_teacher and not actual_teacher:
                        # 最初の5組だけ記録（合同授業なので）
                        if class_name == '1年5組':
                            unassigned_slots.append({
                                'time': time_slot,
                                'subject': subject,
                                'correct_teacher': correct_teacher
                            })

# 結果を表示
if unassigned_slots:
    print(f"教師未割当の授業が {len(unassigned_slots)} コマあります：")
    print()
    
    # 教科別にグループ化
    by_subject = {}
    for slot in unassigned_slots:
        subject = slot['subject']
        if subject not in by_subject:
            by_subject[subject] = []
        by_subject[subject].append(slot)
    
    for subject, slots in sorted(by_subject.items()):
        print(f"\n【{subject}】正しい教師: {slots[0]['correct_teacher']}")
        for slot in slots:
            print(f"  {slot['time']}校時")
else:
    print("すべての5組の授業に教師が割り当てられています！")

# teacher_schedule.csvに記載されているかチェック
print("\n=== 未割当授業の詳細チェック ===")
for slot in unassigned_slots[:5]:  # 最初の5つだけ詳しく表示
    time = slot['time']
    subject = slot['subject']
    teacher = slot['correct_teacher']
    
    print(f"\n{time}校時の{subject}（教師: {teacher}）:")
    
    # この時間に教師が何をしているかチェック
    day_idx = days.index(time[0])
    period_idx = int(time[1]) - 1
    col_idx = day_idx * 6 + period_idx + 1
    
    for i, line in enumerate(teacher_lines[2:], 2):
        if line and line[0] == teacher:
            if col_idx < len(line):
                if line[col_idx]:
                    print(f"  {teacher}先生はこの時間: {line[col_idx]} を担当")
                else:
                    print(f"  {teacher}先生はこの時間: 空き")
            break