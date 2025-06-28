#!/usr/bin/env python3
"""最終修正の検証スクリプト"""

import sys
import os
from pathlib import Path
from collections import defaultdict

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.parsers.followup_constraint_parser import FollowUpConstraintParser
from src.infrastructure.config.exchange_class_config_loader import ExchangeClassConfigLoader

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
            
            for class_name, class_schedule in schedule.assignments.items():
                if period < len(class_schedule.assignments[day]):
                    assignment = class_schedule.assignments[day][period]
                    if assignment and assignment.teacher and assignment.teacher != "未定":
                        teacher_assignments[assignment.teacher].append(class_name)
            
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

def analyze_exchange_class_sync(schedule, exchange_pairs):
    """交流学級の同期を分析"""
    sync_issues = []
    
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in schedule.assignments or parent_class not in schedule.assignments:
            continue
            
        exchange_schedule = schedule.assignments[exchange_class]
        parent_schedule = schedule.assignments[parent_class]
        
        for day in range(5):
            for period in range(6):
                if period < len(exchange_schedule.assignments[day]) and period < len(parent_schedule.assignments[day]):
                    exchange_assignment = exchange_schedule.assignments[day][period]
                    parent_assignment = parent_schedule.assignments[day][period]
                    
                    if exchange_assignment and parent_assignment:
                        # 自立活動の場合はスキップ
                        if exchange_assignment.subject in ['自立', '日生', '作業']:
                            continue
                            
                        # 科目が異なる場合
                        if exchange_assignment.subject != parent_assignment.subject:
                            sync_issues.append({
                                'day': day,
                                'period': period,
                                'exchange_class': exchange_class,
                                'parent_class': parent_class,
                                'exchange_subject': exchange_assignment.subject,
                                'parent_subject': parent_assignment.subject
                            })
    
    return sync_issues

def analyze_daily_duplicates(schedule):
    """日内重複を分析"""
    duplicates = []
    
    for class_name, class_schedule in schedule.assignments.items():
        for day in range(5):
            subjects_in_day = defaultdict(list)
            
            for period in range(6):
                if period < len(class_schedule.assignments[day]):
                    assignment = class_schedule.assignments[day][period]
                    if assignment and assignment.subject not in ['欠', 'YT', '学', '総', '道', '学総', '行']:
                        subjects_in_day[assignment.subject].append(period)
            
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
    
    # リポジトリの初期化
    csv_repo = CSVScheduleRepository()
    output_path = project_root / "data" / "output" / "output.csv"
    
    # スケジュールの読み込み
    schedule = csv_repo.load_schedule(str(output_path))
    
    # Follow-up.csvからテスト期間を取得
    followup_parser = FollowUpConstraintParser()
    followup_path = project_root / "data" / "input" / "Follow-up.csv"
    constraints = followup_parser.parse(str(followup_path))
    
    # テスト期間を特定
    test_periods = set()
    for constraint in constraints:
        if hasattr(constraint, 'is_test_period') and constraint.is_test_period:
            for day in constraint.days:
                for period in constraint.periods:
                    test_periods.add((day, period))
    
    # 交流学級ペアの取得
    exchange_loader = ExchangeClassConfigLoader()
    exchange_pairs = exchange_loader.load_pairs()
    
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
    sync_issues = analyze_exchange_class_sync(schedule, exchange_pairs)
    
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