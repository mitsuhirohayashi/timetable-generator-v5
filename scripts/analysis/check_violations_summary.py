#!/usr/bin/env python3
"""
最終的な修正済み時間割の違反数をカウント（簡易版）
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

def count_violations(schedule):
    """各種違反をカウント"""
    
    # 1. 教師重複（簡易版 - 同じ科目が同時に複数クラスで行われているかチェック）
    teacher_conflicts = 0
    days = ['月', '火', '水', '木', '金']
    
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
            
            # 同じ科目を複数クラスで実施している場合（5組を除く）
            for subject, classes in subject_classes.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [c for c in classes if c.endswith('5')]
                    non_grade5_classes = [c for c in classes if not c.endswith('5')]
                    
                    if non_grade5_classes and len(non_grade5_classes) > 1:
                        teacher_conflicts += 1
    
    # 2. 日内重複
    daily_duplicates = 0
    
    for class_name, class_schedule in schedule.items():
        for day in days:
            subject_counts = defaultdict(int)
            
            for subject in class_schedule[day]:
                if subject and subject not in ['欠', '空', '']:
                    subject_counts[subject] += 1
            
            for subject, count in subject_counts.items():
                if count > 1:
                    daily_duplicates += 1
    
    # 3. 交流学級同期違反
    exchange_sync_violations = 0
    exchange_pairs = {
        '1年6組': '1年1組',
        '1年7組': '1年2組',
        '2年6組': '2年3組',
        '2年7組': '2年2組',
        '3年6組': '3年3組',
        '3年7組': '3年2組'
    }
    
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
                        exchange_sync_violations += 1
    
    # 4. 月曜6限違反
    monday_6th_violations = 0
    
    for class_name, class_schedule in schedule.items():
        # 1・2年生のクラスのみチェック
        if class_name.startswith('1年') or class_name.startswith('2年'):
            subject = class_schedule['月'][5]  # 月曜6限
            if subject and subject != '欠':
                monday_6th_violations += 1
    
    # 5. 空きスロット
    empty_slots = 0
    
    for class_name, class_schedule in schedule.items():
        for day_schedule in class_schedule.values():
            for subject in day_schedule:
                if not subject or subject in ['空', '']:
                    empty_slots += 1
    
    return {
        'teacher_conflicts': teacher_conflicts,
        'daily_duplicates': daily_duplicates,
        'exchange_sync': exchange_sync_violations,
        'monday_6th': monday_6th_violations,
        'empty_slots': empty_slots
    }

def main():
    print("=== 最終修正済み時間割の違反数サマリー ===\n")
    
    # データの読み込み
    schedule_df = load_schedule_df()
    schedule = parse_schedule_df(schedule_df)
    
    # 違反数をカウント
    violations = count_violations(schedule)
    
    # 結果の表示
    print("【制約違反数】")
    print(f"1. 教師重複（テスト期間除く）: {violations['teacher_conflicts']}件")
    print(f"2. 日内重複: {violations['daily_duplicates']}件")
    print(f"3. 交流学級同期違反: {violations['exchange_sync']}件")
    print(f"4. 月曜6限違反: {violations['monday_6th']}件")
    
    total_violations = (violations['teacher_conflicts'] + 
                       violations['daily_duplicates'] + 
                       violations['exchange_sync'] + 
                       violations['monday_6th'])
    
    print(f"\n総違反数: {total_violations}件")
    print(f"（元の142件から{142 - total_violations}件削減、{round((142 - total_violations) / 142 * 100, 1)}%改善）")
    
    print(f"\n空きスロット数: {violations['empty_slots']}個")
    
    print("\n=== チェック完了 ===")

if __name__ == "__main__":
    main()