#!/usr/bin/env python3
"""教師重複の詳細分析スクリプト"""

import pandas as pd

# CSVファイルを読み込む
schedule_df = pd.read_csv('data/output/output.csv', header=None)
teacher_df = pd.read_csv('data/config/teacher_subject_mapping.csv')

# 時間割データを整形
days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]
class_names = []
for i in range(2, min(22, len(schedule_df))):
    if i != 15:  # 空白行をスキップ
        class_name = schedule_df.iloc[i, 0]
        if pd.notna(class_name) and class_name != '':
            class_names.append(str(class_name))

# 教師重複を検出する関数
def find_teacher_conflicts():
    conflicts = []
    
    for day_idx, day in enumerate(days):
        for period_idx, period in enumerate(periods):
            col_idx = day_idx * 6 + period_idx + 1
            
            # 各時間の教師割り当てを収集
            teacher_assignments = {}
            
            for row_idx, class_name in enumerate(class_names):
                if not class_name:
                    continue
                    
                actual_row = row_idx + 2
                if actual_row >= 15:  # 空白行の後は+1
                    actual_row += 1
                    
                subject = schedule_df.iloc[actual_row, col_idx]
                
                if subject and subject not in ['欠', 'YT', '学総', '技家']:
                    # クラス情報を解析
                    parts = class_name.replace('年', '-').replace('組', '').split('-')
                    if len(parts) == 2:
                        grade = int(parts[0])
                        class_num = int(parts[1])
                        
                        # 教師を検索
                        teacher_match = teacher_df[
                            (teacher_df['学年'] == grade) & 
                            (teacher_df['組'] == class_num) & 
                            (teacher_df['教科'] == subject)
                        ]
                        
                        if len(teacher_match) > 0:
                            teacher_name = teacher_match['教員名'].values[0]
                            
                            if teacher_name not in teacher_assignments:
                                teacher_assignments[teacher_name] = []
                            teacher_assignments[teacher_name].append({
                                'class': class_name,
                                'subject': subject,
                                'grade': grade
                            })
            
            # 重複をチェック
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for a in assignments if '5組' in a['class'])
                    if grade5_count == len(assignments):
                        continue
                    
                    conflicts.append({
                        'day': day,
                        'period': period,
                        'teacher': teacher,
                        'assignments': assignments
                    })
    
    return conflicts

# 教師重複を検出
conflicts = find_teacher_conflicts()

print('=== 教師重複の詳細分析 ===')
print(f'\n検出された教師重複: {len(conflicts)}件\n')

for conflict in conflicts:
    print(f"\n{conflict['day']}曜{conflict['period']}限 - {conflict['teacher']}先生:")
    for assignment in conflict['assignments']:
        print(f"  - {assignment['class']}: {assignment['subject']}")

# 特に問題となっている2つのケースを詳細に表示
print('\n\n=== 特定のケースの詳細 ===')

# 月曜5限の社会科
print('\n1. 月曜5限の社会科:')
print('  - 3年2組: 社会 (教師: 北先生)')
print('  - 3年3組: 社会 (教師: 北先生)')
print('  -> 北先生が同時に2クラスを担当（教師重複違反）')

# 火曜5限の数学
print('\n2. 火曜5限の数学:')
print('  - 2年1組: 数学 (教師: 井上先生)')
print('  - 2年2組: 数学 (教師: 井上先生)')
print('  -> 井上先生が同時に2クラスを担当（教師重複違反）')