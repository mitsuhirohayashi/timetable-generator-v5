#!/usr/bin/env python3
"""最終修正の検証スクリプト（シンプル版）"""

import sys
import os
from pathlib import Path
from collections import defaultdict
import csv

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def read_csv_schedule(file_path):
    """CSVファイルから時間割を読み込む"""
    schedule = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行をスキップ
        
        for row in reader:
            if len(row) > 31:  # 十分な列数がある場合
                class_name = row[0].strip()
                if class_name and class_name != '学年':
                    schedule[class_name] = []
                    
                    # 各曜日の時間割を読み込む（6列ずつ）
                    for day in range(5):  # 月〜金
                        day_schedule = []
                        for period in range(6):  # 1〜6限
                            col_idx = 1 + day * 6 + period
                            if col_idx < len(row):
                                cell = row[col_idx].strip()
                                if '/' in cell:
                                    parts = cell.split('/')
                                    subject = parts[0].strip()
                                    teacher = parts[1].strip() if len(parts) > 1 else None
                                else:
                                    subject = cell
                                    teacher = None
                                day_schedule.append((subject, teacher))
                            else:
                                day_schedule.append((None, None))
                        schedule[class_name].append(day_schedule)
    
    return schedule

def analyze_teacher_conflicts(schedule, test_periods):
    """教師の重複を分析（テスト期間を除外）"""
    conflicts = []
    
    # 時間ごとの教師配置を収集
    for day in range(5):
        for period in range(6):
            # テスト期間はスキップ
            if (day, period) in test_periods:
                continue
                
            teacher_assignments = defaultdict(list)
            
            for class_name, class_schedule in schedule.items():
                if day < len(class_schedule) and period < len(class_schedule[day]):
                    subject, teacher = class_schedule[day][period]
                    if teacher and teacher != "未定":
                        teacher_assignments[teacher].append(class_name)
            
            # 重複をチェック
            for teacher, classes in teacher_assignments.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [c for c in classes if c.endswith('5')]
                    non_grade5_classes = [c for c in classes if not c.endswith('5')]
                    
                    # 5組以外で重複がある場合
                    if len(non_grade5_classes) > 1:
                        conflicts.append({
                            'day': day,
                            'period': period,
                            'teacher': teacher,
                            'classes': classes
                        })
                    # 5組と他クラスが混在している場合
                    elif grade5_classes and non_grade5_classes:
                        conflicts.append({
                            'day': day,
                            'period': period,
                            'teacher': teacher,
                            'classes': classes
                        })
    
    return conflicts

def analyze_exchange_class_sync(schedule):
    """交流学級の同期を分析"""
    sync_issues = []
    
    # 交流学級と親学級のペア
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
        
        for day in range(5):
            for period in range(6):
                if day < len(exchange_schedule) and period < len(exchange_schedule[day]) and \
                   day < len(parent_schedule) and period < len(parent_schedule[day]):
                    exchange_subject, _ = exchange_schedule[day][period]
                    parent_subject, _ = parent_schedule[day][period]
                    
                    if exchange_subject and parent_subject:
                        # 自立活動の場合はスキップ
                        if exchange_subject in ['自立', '日生', '作業']:
                            continue
                            
                        # 科目が異なる場合
                        if exchange_subject != parent_subject:
                            sync_issues.append({
                                'day': day,
                                'period': period,
                                'exchange_class': exchange_class,
                                'parent_class': parent_class,
                                'exchange_subject': exchange_subject,
                                'parent_subject': parent_subject
                            })
    
    return sync_issues

def analyze_daily_duplicates(schedule):
    """日内重複を分析"""
    duplicates = []
    
    for class_name, class_schedule in schedule.items():
        for day in range(5):
            subjects_in_day = defaultdict(list)
            
            if day < len(class_schedule):
                for period in range(6):
                    if period < len(class_schedule[day]):
                        subject, _ = class_schedule[day][period]
                        if subject and subject not in ['欠', 'YT', '学', '総', '道', '学総', '行']:
                            subjects_in_day[subject].append(period)
            
            # 重複をチェック
            for subject, periods in subjects_in_day.items():
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
    print("=== 最終修正の検証 ===\n")
    
    # スケジュールの読み込み
    output_path = project_root / "data" / "output" / "output.csv"
    schedule = read_csv_schedule(output_path)
    
    # テスト期間を定義（Follow-up.csvより）
    test_periods = {
        (0, 0), (0, 1), (0, 2),  # 月曜1-3限
        (1, 0), (1, 1), (1, 2),  # 火曜1-3限  
        (2, 0), (2, 1),          # 水曜1-2限
    }
    
    # 1. 教師の重複チェック（テスト期間除外）
    print("1. 教師の重複チェック（テスト期間除外）")
    print("-" * 50)
    teacher_conflicts = analyze_teacher_conflicts(schedule, test_periods)
    
    if teacher_conflicts:
        print(f"❌ {len(teacher_conflicts)}件の教師重複が見つかりました：")
        for conflict in teacher_conflicts:
            day_names = ['月', '火', '水', '木', '金']
            print(f"  - {day_names[conflict['day']]}曜{conflict['period']+1}限: "
                  f"{conflict['teacher']}先生が{', '.join(conflict['classes'])}で重複")
    else:
        print("✅ 教師の重複はありません")
    
    # 2. 交流学級の同期チェック
    print("\n2. 交流学級の同期チェック")
    print("-" * 50)
    sync_issues = analyze_exchange_class_sync(schedule)
    
    if sync_issues:
        print(f"❌ {len(sync_issues)}件の同期問題が見つかりました：")
        for issue in sync_issues:
            day_names = ['月', '火', '水', '木', '金']
            print(f"  - {day_names[issue['day']]}曜{issue['period']+1}限: "
                  f"{issue['exchange_class']}={issue['exchange_subject']}, "
                  f"{issue['parent_class']}={issue['parent_subject']}")
    else:
        print("✅ 交流学級の同期は正常です")
    
    # 3. 日内重複チェック
    print("\n3. 日内重複チェック")
    print("-" * 50)
    daily_duplicates = analyze_daily_duplicates(schedule)
    
    if daily_duplicates:
        print(f"❌ {len(daily_duplicates)}件の日内重複が見つかりました：")
        for dup in daily_duplicates:
            day_names = ['月', '火', '水', '木', '金']
            periods_str = ', '.join([f"{p+1}限" for p in dup['periods']])
            print(f"  - {dup['class']} {day_names[dup['day']]}曜: "
                  f"{dup['subject']}が{periods_str}に重複")
    else:
        print("✅ 日内重複はありません")
    
    # サマリー
    print("\n" + "=" * 50)
    print("検証結果サマリー")
    print("=" * 50)
    
    total_issues = len(teacher_conflicts) + len(sync_issues) + len(daily_duplicates)
    
    if total_issues == 0:
        print("✅ すべての制約が満たされています！")
        print("   - 教師の重複: 0件")
        print("   - 交流学級の同期問題: 0件")
        print("   - 日内重複: 0件")
    else:
        print(f"❌ 合計{total_issues}件の問題が残っています")
        print(f"   - 教師の重複: {len(teacher_conflicts)}件")
        print(f"   - 交流学級の同期問題: {len(sync_issues)}件")
        print(f"   - 日内重複: {len(daily_duplicates)}件")
    
    # 特記事項
    print("\n【特記事項】")
    print("- テスト期間の教師重複は正常な巡回監督として除外しています")
    print("- 5組（1-5, 2-5, 3-5）の合同授業は正常として扱っています")
    print("- 交流学級の自立活動時は親学級との同期は不要です")

if __name__ == "__main__":
    main()