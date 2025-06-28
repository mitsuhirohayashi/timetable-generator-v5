#!/usr/bin/env python3
"""
最終的な修正済み時間割の違反詳細分析
"""

import pandas as pd
from collections import defaultdict
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def load_schedule_df():
    """時間割CSVを直接読み込む"""
    schedule_path = project_root / "data/output/output_3_6_fixed.csv"
    try:
        return pd.read_csv(schedule_path, encoding='utf-8')
    except:
        return pd.read_csv(schedule_path, encoding='shift_jis')

def is_test_period(day, period):
    """テスト期間かどうか判定"""
    test_periods = {
        ('月', 1), ('月', 2), ('月', 3),
        ('火', 1), ('火', 2), ('火', 3),
        ('水', 1), ('水', 2)
    }
    return (day, period) in test_periods

def parse_schedule_df(df):
    """DataFrameを時間割データ構造に変換"""
    schedule = {}
    days = ['月', '火', '水', '木', '金']
    
    # Skip header rows
    for idx, row in df.iterrows():
        if idx < 2:  # Skip first 2 rows (headers)
            continue
            
        class_name = str(row.iloc[0])
        if pd.isna(class_name) or class_name == '' or class_name == 'nan':
            continue
        
        schedule[class_name] = {}
        col_idx = 1
        
        for day in days:
            schedule[class_name][day] = []
            for period in range(1, 7):
                if col_idx < len(row):
                    subject = row.iloc[col_idx]
                    if pd.isna(subject):
                        subject = ''
                    schedule[class_name][day].append(str(subject).strip())
                else:
                    schedule[class_name][day].append('')
                col_idx += 1
    
    return schedule

def analyze_teacher_conflicts(schedule):
    """教師重複の詳細分析"""
    print("\n【教師重複の詳細】")
    days = ['月', '火', '水', '木', '金']
    
    conflict_count = 0
    
    for day_idx, day in enumerate(days):
        for period_idx in range(6):
            period = period_idx + 1
            
            if is_test_period(day, period):
                continue  # テスト期間はスキップ
            
            # この時間の科目と担当クラスを収集
            subject_classes = defaultdict(list)
            
            for class_name, class_schedule in schedule.items():
                subject = class_schedule[day][period_idx]
                if subject and subject not in ['欠', '空', '']:
                    subject_classes[subject].append(class_name)
            
            # 同じ科目を複数クラスで実施している場合
            for subject, classes in subject_classes.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [c for c in classes if c.endswith('5')]
                    non_grade5_classes = [c for c in classes if not c.endswith('5')]
                    
                    # 交流学級と親学級のペアをチェック
                    exchange_pairs = {
                        '1年6組': '1年1組',
                        '1年7組': '1年2組',
                        '2年6組': '2年3組',
                        '2年7組': '2年2組',
                        '3年6組': '3年3組',
                        '3年7組': '3年2組'
                    }
                    
                    # ペアを除外
                    remaining_classes = classes.copy()
                    for ex_class, parent_class in exchange_pairs.items():
                        if ex_class in remaining_classes and parent_class in remaining_classes:
                            # 体育の場合はペアは正常
                            if subject in ['保', '体']:
                                remaining_classes.remove(ex_class)
                                remaining_classes.remove(parent_class)
                    
                    # 5組を除外
                    remaining_classes = [c for c in remaining_classes if not c.endswith('5')]
                    
                    if len(remaining_classes) > 1:
                        conflict_count += 1
                        if conflict_count <= 10:  # 最初の10件のみ表示
                            print(f"{day}曜{period}限 - {subject}: {', '.join(classes)}")

def analyze_exchange_sync(schedule):
    """交流学級同期違反の詳細分析"""
    print("\n【交流学級同期違反の詳細】")
    days = ['月', '火', '水', '木', '金']
    
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
    violation_count = 0
    
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in schedule or parent_class not in schedule:
            continue
        
        exchange_schedule = schedule[exchange_class]
        parent_schedule = schedule[parent_class]
        
        for day in days:
            for period_idx in range(6):
                exchange_subject = exchange_schedule[day][period_idx]
                parent_subject = parent_schedule[day][period_idx]
                
                # 自立活動以外は同じでなければならない
                if exchange_subject not in ['自立', '日生', '作業', '']:
                    if exchange_subject != parent_subject:
                        violation_count += 1
                        if violation_count <= 10:  # 最初の10件のみ表示
                            print(f"{exchange_class}と{parent_class} - {day}曜{period_idx + 1}限: "
                                  f"交流={exchange_subject}, 親={parent_subject}")

def check_grade5_sync(schedule):
    """5組の同期状況をチェック"""
    print("\n【5組の同期状況】")
    days = ['月', '火', '水', '木', '金']
    
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    
    # 各時間帯での5組の科目をチェック
    sync_violations = 0
    
    for day in days:
        for period_idx in range(6):
            subjects = []
            for class_name in grade5_classes:
                if class_name in schedule:
                    subject = schedule[class_name][day][period_idx]
                    subjects.append((class_name, subject))
            
            # 全ての5組が同じ科目でない場合
            if subjects:
                unique_subjects = set([s[1] for s in subjects])
                if len(unique_subjects) > 1:
                    sync_violations += 1
                    if sync_violations <= 5:  # 最初の5件のみ表示
                        print(f"{day}曜{period_idx + 1}限: {subjects}")
    
    if sync_violations == 0:
        print("5組は完全に同期しています！")

def main():
    print("=== 最終修正済み時間割の違反詳細分析 ===")
    
    # データの読み込み
    schedule_df = load_schedule_df()
    schedule = parse_schedule_df(schedule_df)
    
    # 各種分析
    analyze_teacher_conflicts(schedule)
    analyze_exchange_sync(schedule)
    check_grade5_sync(schedule)
    
    print("\n=== 分析完了 ===")

if __name__ == "__main__":
    main()