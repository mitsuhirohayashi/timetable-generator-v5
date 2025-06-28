#!/usr/bin/env python3
"""
残存する教師重複の簡易分析
"""

import csv
from collections import defaultdict
from typing import Dict, List, Set, Tuple

def load_schedule(filepath: str) -> Dict[str, Dict[Tuple[str, int], str]]:
    """時間割を読み込む"""
    schedule = {}
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)  # 曜日行
        periods = next(reader)  # 時限行
        
        # Create day-period mapping
        day_period_map = []
        for i in range(1, len(headers)):
            if i < len(headers) and i < len(periods):
                day = headers[i].strip()
                period = periods[i].strip()
                if day and period and period.isdigit():
                    day_period_map.append((day, int(period)))
                else:
                    day_period_map.append(None)
        
        for row in reader:
            if not row or not row[0]:
                continue
            
            class_name = row[0].strip()
            schedule[class_name] = {}
            
            for i, dp in enumerate(day_period_map):
                if dp and i + 1 < len(row):
                    day, period = dp
                    subject = row[i + 1].strip() if row[i + 1] else ""
                    if subject:
                        schedule[class_name][(day, period)] = subject
    
    return schedule

def load_teacher_mapping(filepath: str) -> Dict[Tuple[str, str], str]:
    """教師マッピングを読み込む"""
    mapping = {}
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            teacher = row['教員名'].strip()
            subject = row['教科'].strip()
            grade = row['学年'].strip()
            class_num = row['組'].strip()
            class_name = f"{grade}年{class_num}組"
            mapping[(class_name, subject)] = teacher
    
    return mapping

def get_test_periods() -> Set[Tuple[str, int]]:
    """テスト期間を取得"""
    test_periods = set()
    
    # Follow-up.csvから直接読み取る
    with open('data/input/Follow-up.csv', 'r', encoding='utf-8-sig') as f:
        content = f.read()
        
    # テスト期間の抽出
    if "１・２・３校時はテストなので時間割の変更をしないでください" in content:
        test_periods.update([('月', 1), ('月', 2), ('月', 3)])
        test_periods.update([('火', 1), ('火', 2), ('火', 3)])
    
    if "１・２校時はテストなので時間割の変更をしないでください" in content:
        test_periods.update([('水', 1), ('水', 2)])
    
    return test_periods

def analyze_conflicts(schedule: Dict, teacher_mapping: Dict, test_periods: Set) -> None:
    """教師の重複を分析"""
    # 各時間帯の教師配置を収集
    time_teacher_classes = defaultdict(lambda: defaultdict(list))
    
    for class_name, class_schedule in schedule.items():
        for (day, period), subject in class_schedule.items():
            if subject in ['欠', '行', 'YT', '']:
                continue
            
            # Get teacher for this subject and class
            teacher = teacher_mapping.get((class_name, subject), None)
            if teacher:
                time_teacher_classes[(day, period)][teacher].append((class_name, subject))
    
    # Analyze conflicts
    print("\n" + "=" * 80)
    print("教師重複分析結果")
    print("=" * 80)
    
    real_conflicts = []
    test_conflicts = []
    grade5_conflicts = []
    exchange_conflicts = []
    
    for (day, period), teacher_classes in sorted(time_teacher_classes.items()):
        for teacher, assignments in teacher_classes.items():
            if len(assignments) > 1:
                # Check if it's grade 5 joint class
                if all('5組' in a[0] for a in assignments):
                    grade5_conflicts.append((day, period, teacher, assignments))
                    continue
                
                # Check if it's exchange class pair
                exchange_pairs = [
                    ('1年1組', '1年6組'), ('1年2組', '1年7組'),
                    ('2年3組', '2年6組'), ('2年2組', '2年7組'),
                    ('3年3組', '3年6組'), ('3年2組', '3年7組')
                ]
                
                is_exchange = False
                for parent, exchange in exchange_pairs:
                    class_names = [a[0] for a in assignments]
                    if parent in class_names and exchange in class_names and len(class_names) == 2:
                        is_exchange = True
                        exchange_conflicts.append((day, period, teacher, assignments))
                        break
                
                if is_exchange:
                    continue
                
                # Check if it's test period
                if (day, period) in test_periods:
                    test_conflicts.append((day, period, teacher, assignments))
                else:
                    real_conflicts.append((day, period, teacher, assignments))
    
    # Display results
    print("\n1. 真の教師重複（テスト期間外）")
    print("-" * 80)
    if real_conflicts:
        for day, period, teacher, assignments in real_conflicts:
            print(f"\n{day}曜{period}限 - {teacher}先生:")
            for class_name, subject in assignments:
                print(f"  - {class_name}: {subject}")
    else:
        print("✅ 真の教師重複はありません！")
    
    print("\n2. テスト期間中の巡回監督（正常）")
    print("-" * 80)
    if test_conflicts:
        for day, period, teacher, assignments in test_conflicts:
            print(f"\n{day}曜{period}限 - {teacher}先生（巡回監督）:")
            for class_name, subject in assignments:
                print(f"  - {class_name}: {subject}")
    else:
        print("テスト期間中の教師重複はありません")
    
    print("\n3. 5組合同授業（正常）")
    print("-" * 80)
    if grade5_conflicts:
        for day, period, teacher, assignments in grade5_conflicts:
            print(f"\n{day}曜{period}限 - {teacher}先生（合同授業）:")
            for class_name, subject in assignments:
                print(f"  - {class_name}: {subject}")
    else:
        print("5組の合同授業はありません")
    
    print("\n4. 交流学級ペア（正常）")
    print("-" * 80)
    if exchange_conflicts:
        for day, period, teacher, assignments in exchange_conflicts:
            print(f"\n{day}曜{period}限 - {teacher}先生（交流学級）:")
            for class_name, subject in assignments:
                print(f"  - {class_name}: {subject}")
    else:
        print("交流学級のペア授業はありません")
    
    # Summary
    print("\n" + "=" * 80)
    print("サマリー")
    print("=" * 80)
    print(f"真の教師重複: {len(real_conflicts)}件")
    print(f"テスト期間の巡回監督: {len(test_conflicts)}件（正常）")
    print(f"5組合同授業: {len(grade5_conflicts)}件（正常）")
    print(f"交流学級ペア: {len(exchange_conflicts)}件（正常）")
    
    if len(real_conflicts) == 0:
        print("\n✅ 全ての教師重複が解決されました！")
    else:
        print(f"\n⚠️ {len(real_conflicts)}件の真の教師重複が残っています")

def check_kaneko_mi(schedule: Dict, teacher_mapping: Dict, test_periods: Set) -> None:
    """金子み先生の確認"""
    print("\n" + "=" * 80)
    print("金子み先生のスケジュール確認")
    print("=" * 80)
    
    kaneko_schedule = []
    
    for class_name, class_schedule in schedule.items():
        for (day, period), subject in class_schedule.items():
            teacher = teacher_mapping.get((class_name, subject), None)
            if teacher == '金子み':
                kaneko_schedule.append((day, period, class_name, subject))
    
    # Sort by day and period
    kaneko_schedule.sort(key=lambda x: (x[0], x[1]))
    
    print("\n金子み先生の全授業:")
    test_count = 0
    for day, period, class_name, subject in kaneko_schedule:
        test_mark = " [テスト期間]" if (day, period) in test_periods else ""
        if test_mark:
            test_count += 1
        print(f"{day}曜{period}限{test_mark}: {class_name} - {subject}")
    
    if test_count == 0:
        print("\n✅ 金子み先生はテスト期間中の授業なし（修正成功！）")
    else:
        print(f"\n⚠️ 金子み先生がテスト期間中に{test_count}件の授業を担当")

def main():
    """メイン処理"""
    print("=" * 80)
    print("残存する教師重複の簡易分析")
    print("=" * 80)
    
    # Load data
    schedule = load_schedule('data/output/output.csv')
    teacher_mapping = load_teacher_mapping('data/config/teacher_subject_mapping.csv')
    test_periods = get_test_periods()
    
    print(f"\nテスト期間: {sorted(test_periods)}")
    
    # Analyze conflicts
    analyze_conflicts(schedule, teacher_mapping, test_periods)
    
    # Check 金子み
    check_kaneko_mi(schedule, teacher_mapping, test_periods)

if __name__ == "__main__":
    main()