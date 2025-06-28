#!/usr/bin/env python3
"""最終出力の違反を簡単に確認するスクリプト"""

import csv
from collections import defaultdict


def check_teacher_conflicts(schedule, teacher_mapping):
    """教師の重複をチェック"""
    conflicts = []
    days = ['月', '火', '水', '木', '金']
    
    # 時間ごとの教師割り当てを収集
    teacher_schedule = defaultdict(lambda: defaultdict(list))
    
    for class_name, class_schedule in schedule.items():
        for day in days:
            if day in class_schedule:
                for period, subject in class_schedule[day].items():
                    if subject:
                        teacher = teacher_mapping.get((class_name, subject))
                        if teacher:
                            teacher_schedule[(day, period)][teacher].append((class_name, subject))
    
    # 重複をチェック
    for (day, period), teachers in teacher_schedule.items():
        for teacher, assignments in teachers.items():
            if len(assignments) > 1:
                # 5組の合同授業を除外
                grade5_classes = ['1年5組', '2年5組', '3年5組']
                grade5_count = sum(1 for cls, _ in assignments if cls in grade5_classes)
                if not (grade5_count > 1 and grade5_count == len(assignments)):
                    conflicts.append(f"{teacher}先生が{day}曜{period}校時に複数クラス: {', '.join([f'{cls}({subj})' for cls, subj in assignments])}")
    
    return conflicts


def check_exchange_sync(schedule):
    """交流学級の同期をチェック"""
    violations = []
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組',
    }
    
    days = ['月', '火', '水', '木', '金']
    
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in schedule or parent_class not in schedule:
            continue
            
        for day in days:
            if day not in schedule[exchange_class] or day not in schedule[parent_class]:
                continue
                
            for period in range(1, 7):
                ex_subj = schedule[exchange_class][day].get(period, '')
                par_subj = schedule[parent_class][day].get(period, '')
                
                if ex_subj == '自立':
                    if par_subj not in ['数', '英']:
                        violations.append(f"{exchange_class}が{day}曜{period}校時に自立だが、{parent_class}は{par_subj}")
                elif ex_subj and par_subj and ex_subj != par_subj:
                    violations.append(f"{exchange_class}({ex_subj})と{parent_class}({par_subj})が{day}曜{period}校時で不一致")
    
    return violations


def main():
    # スケジュールを読み込む
    schedule = {}
    with open('data/output/output_final.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    header1 = rows[0]
    header2 = rows[1]
    
    for row_idx in range(2, len(rows)):
        if not rows[row_idx][0]:
            continue
            
        class_name = rows[row_idx][0]
        schedule[class_name] = {}
        
        for col_idx in range(1, len(rows[row_idx])):
            if col_idx >= len(header1):
                break
                
            day = header1[col_idx]
            period = int(header2[col_idx]) if header2[col_idx].isdigit() else 0
            
            if day and period:
                if day not in schedule[class_name]:
                    schedule[class_name][day] = {}
                    
                subject = rows[row_idx][col_idx].strip() if rows[row_idx][col_idx] else ''
                schedule[class_name][day][period] = subject
    
    # 教師マッピングを読み込む
    teacher_mapping = {}
    with open('data/config/teacher_subject_mapping.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # ヘッダーをスキップ
        
        for row in reader:
            if len(row) >= 4:
                teacher = row[0].strip()
                subject = row[1].strip()
                grade = row[2].strip()
                class_num = row[3].strip()
                
                class_name = f"{grade}年{class_num}組"
                teacher_mapping[(class_name, subject)] = teacher
    
    print("=== 最終出力の違反チェック ===\n")
    
    # 教師重複をチェック
    teacher_conflicts = check_teacher_conflicts(schedule, teacher_mapping)
    print(f"教師重複: {len(teacher_conflicts)}件")
    if teacher_conflicts:
        for i, conflict in enumerate(teacher_conflicts[:10]):
            print(f"  {i+1}. {conflict}")
        if len(teacher_conflicts) > 10:
            print(f"  ... 他 {len(teacher_conflicts) - 10} 件")
    
    # 交流学級同期をチェック
    print()
    sync_violations = check_exchange_sync(schedule)
    print(f"交流学級同期違反: {len(sync_violations)}件")
    if sync_violations:
        for i, violation in enumerate(sync_violations[:10]):
            print(f"  {i+1}. {violation}")
    
    # 空きスロットをチェック
    print()
    empty_count = 0
    empty_details = []
    for class_name, class_schedule in schedule.items():
        for day in ['月', '火', '水', '木', '金']:
            if day in class_schedule:
                for period in range(1, 7):
                    if not class_schedule[day].get(period, ''):
                        empty_count += 1
                        empty_details.append(f"{class_name}の{day}曜{period}校時")
    
    print(f"空きスロット: {empty_count}件")
    if empty_details:
        for detail in empty_details[:5]:
            print(f"  - {detail}")
    
    print(f"\n総違反数: {len(teacher_conflicts) + len(sync_violations)}件（空きスロット除く）")


if __name__ == "__main__":
    main()