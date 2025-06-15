#!/usr/bin/env python3
"""入力データ（input.csv）の日内重複をチェックするスクリプト"""

import csv
from collections import defaultdict

def check_daily_duplicates_in_csv(csv_path):
    """CSVファイルから日内重複をチェック"""
    protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行', '総', ''}
    
    # CSVを読み込み
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行（曜日）
        time_headers = next(reader)  # 時限行
        
        # データを読み込み
        duplicates = []
        
        for row in reader:
            if not row[0] or row[0].strip() == "":  # 空行スキップ
                continue
                
            class_name = row[0]
            
            # 各曜日ごとに教科をチェック
            subjects_by_day = {
                '月': defaultdict(list),
                '火': defaultdict(list),
                '水': defaultdict(list),
                '木': defaultdict(list),
                '金': defaultdict(list)
            }
            
            # 各セルを処理
            for i, subject in enumerate(row[1:], 1):
                if i > 30:  # 最大30コマ（5日×6時限）
                    break
                    
                day_index = (i - 1) // 6
                period = ((i - 1) % 6) + 1
                
                days = ['月', '火', '水', '木', '金']
                if day_index < len(days):
                    day = days[day_index]
                    
                    # 保護教科を除外
                    if subject and subject not in protected_subjects:
                        subjects_by_day[day][subject].append(period)
            
            # 重複をチェック
            for day, subjects in subjects_by_day.items():
                for subject, periods in subjects.items():
                    if len(periods) > 1:
                        duplicates.append({
                            'class': class_name,
                            'day': day,
                            'subject': subject,
                            'periods': periods
                        })
    
    return duplicates


def main():
    """メイン処理"""
    print("=== input.csv の日内重複チェック ===\n")
    
    # input.csvをチェック
    csv_path = "/Users/hayashimitsuhiro/Desktop/timetable_v5/data/input/input.csv"
    duplicates = check_daily_duplicates_in_csv(csv_path)
    
    if duplicates:
        print(f"入力データに {len(duplicates)} 件の日内重複が見つかりました：")
        for dup in duplicates:
            periods_str = ", ".join([f"{p}限" for p in dup['periods']])
            print(f"  - {dup['class']}の{dup['day']}曜日: {dup['subject']}が{periods_str}に重複")
    else:
        print("入力データに日内重複はありません")
    
    # 特定のクラスの詳細を表示
    print("\n=== 特定クラスの詳細 ===")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        time_headers = next(reader)
        
        for row in reader:
            if row[0] in ['2年1組', '3年1組']:
                print(f"\n{row[0]}:")
                # 火曜日（2年1組）
                if row[0] == '2年1組':
                    print(f"  火曜日: {row[7:13]}")
                # 金曜日（3年1組）
                if row[0] == '3年1組':
                    print(f"  金曜日: {row[25:31]}")


if __name__ == "__main__":
    main()