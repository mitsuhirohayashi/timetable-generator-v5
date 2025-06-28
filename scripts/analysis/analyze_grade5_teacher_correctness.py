#!/usr/bin/env python3
"""5組の教師割り当ての正誤を分析"""
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

print('=== 5組の教師割り当て正誤分析 ===')
print()

days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]

# 正しい教師割り当てを表示
print("【5組の正しい教師マッピング】")
print("国語: 寺田")
print("社会: 蒲地")
print("数学: 梶永")
print("理科: 智田")
print("音楽: 塚本")
print("美術: 金子み")
print("保健体育: 野口")
print("技術: 林")
print("家庭: 金子み")
print("英語: 林田")
print("日生・作業・生単・自立・学・総・道: 金子み")
print()

# 各5組の授業と教師をチェック
correct_count = 0
incorrect_count = 0
incorrect_assignments = []

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
                    actual_teacher = teacher_assignments.get(time_slot, {}).get(class_name, '不明')
                    
                    if correct_teacher and actual_teacher != '不明':
                        if actual_teacher == correct_teacher:
                            correct_count += 1
                        else:
                            incorrect_count += 1
                            incorrect_assignments.append({
                                'time': time_slot,
                                'class': class_name,
                                'subject': subject,
                                'actual': actual_teacher,
                                'correct': correct_teacher
                            })

print(f"正しい教師割り当て: {correct_count} 件")
print(f"誤った教師割り当て: {incorrect_count} 件")
print()

if incorrect_assignments:
    print("【誤った教師割り当ての詳細】")
    for error in incorrect_assignments:
        print(f"{error['time']}校時 {error['class']} {error['subject']}: "
              f"{error['actual']} → 正しくは {error['correct']}")
else:
    print("すべての5組の授業に正しい教師が割り当てられています！")

# 教科別の正誤率を計算
subject_stats = {}
for day in days:
    for period in periods:
        time_slot = f'{day}{period}'
        
        for i, line in enumerate(lines):
            if line and line[0] in ['1年5組', '2年5組', '3年5組']:
                class_name = line[0]
                day_idx = days.index(day)
                period_idx = period - 1
                col_idx = day_idx * 6 + period_idx + 1
                
                if col_idx < len(line) and line[col_idx]:
                    subject = line[col_idx]
                    correct_teacher = grade5_service.get_teacher_for_subject(subject)
                    actual_teacher = teacher_assignments.get(time_slot, {}).get(class_name, '不明')
                    
                    if subject not in subject_stats:
                        subject_stats[subject] = {'correct': 0, 'total': 0}
                    
                    subject_stats[subject]['total'] += 1
                    if correct_teacher and actual_teacher == correct_teacher:
                        subject_stats[subject]['correct'] += 1

print("\n【教科別の正誤率】")
for subject, stats in sorted(subject_stats.items()):
    if stats['total'] > 0:
        rate = stats['correct'] / stats['total'] * 100
        print(f"{subject}: {stats['correct']}/{stats['total']} ({rate:.1f}%)")