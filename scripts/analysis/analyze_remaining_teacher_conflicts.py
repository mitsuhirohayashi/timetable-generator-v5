#!/usr/bin/env python3
"""
残存する教師重複の詳細分析
- テスト期間を除外して真の重複を特定
- 金子みテスト監督修正の効果を確認
- 重複の根本原因を分析
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser

def load_schedule(filepath: str) -> Dict[str, Dict[Tuple[str, int], str]]:
    """時間割を読み込む"""
    schedule = {}
    day_map = {'月': 'Monday', '火': 'Tuesday', '水': 'Wednesday', '木': 'Thursday', '金': 'Friday'}
    
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

def get_test_periods(followup_parser: EnhancedFollowUpParser) -> Set[Tuple[str, int]]:
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

def analyze_teacher_conflicts(schedule: Dict, mapping_repo: TeacherMappingRepository, test_periods: Set[Tuple[str, int]]) -> Dict:
    """教師の重複を分析"""
    # 各時間帯の教師配置を収集
    time_teacher_classes = defaultdict(lambda: defaultdict(list))
    
    for class_name, class_schedule in schedule.items():
        for (day, period), subject in class_schedule.items():
            if subject in ['欠', '行', 'YT', '']:
                continue
            
            teacher = mapping_repo.get_teacher_for_subject_class(subject, class_name)
            teachers = [teacher] if teacher else []
            for teacher in teachers:
                time_teacher_classes[(day, period)][teacher].append((class_name, subject))
    
    # 重複を分析
    conflicts = {
        'test_period_conflicts': defaultdict(list),
        'real_conflicts': defaultdict(list),
        'grade5_joint_classes': defaultdict(list),
        'exchange_class_pairs': defaultdict(list)
    }
    
    for (day, period), teacher_classes in time_teacher_classes.items():
        for teacher, assignments in teacher_classes.items():
            if len(assignments) > 1:
                # 複数クラスを担当
                class_names = [a[0] for a in assignments]
                
                # 5組の合同授業チェック
                if all('5' in cn for cn in class_names):
                    conflicts['grade5_joint_classes'][(day, period)].append({
                        'teacher': teacher,
                        'assignments': assignments
                    })
                    continue
                
                # 交流学級ペアチェック
                exchange_pairs = [
                    ('1年1組', '1年6組'), ('1年2組', '1年7組'),
                    ('2年3組', '2年6組'), ('2年2組', '2年7組'),
                    ('3年3組', '3年6組'), ('3年2組', '3年7組')
                ]
                
                is_exchange_pair = False
                for parent, exchange in exchange_pairs:
                    if parent in class_names and exchange in class_names and len(class_names) == 2:
                        is_exchange_pair = True
                        conflicts['exchange_class_pairs'][(day, period)].append({
                            'teacher': teacher,
                            'assignments': assignments
                        })
                        break
                
                if is_exchange_pair:
                    continue
                
                # テスト期間かどうか
                if (day, period) in test_periods:
                    conflicts['test_period_conflicts'][(day, period)].append({
                        'teacher': teacher,
                        'assignments': assignments
                    })
                else:
                    conflicts['real_conflicts'][(day, period)].append({
                        'teacher': teacher,
                        'assignments': assignments
                    })
    
    return conflicts

def check_kaneko_mi_fix(schedule: Dict, test_periods: Set[Tuple[str, int]]) -> Dict:
    """金子みテスト監督修正の確認"""
    kaneko_mi_schedule = defaultdict(list)
    
    # 金子みの担当クラスと時間を収集
    for class_name, class_schedule in schedule.items():
        if '5' in class_name:  # 5組担当
            for (day, period), subject in class_schedule.items():
                if subject and subject not in ['欠', '行', 'YT']:
                    kaneko_mi_schedule[(day, period)].append((class_name, subject))
    
    # テスト期間中の金子みの状況を分析
    test_period_status = {}
    for (day, period) in test_periods:
        if (day, period) in kaneko_mi_schedule:
            test_period_status[(day, period)] = kaneko_mi_schedule[(day, period)]
    
    return {
        'full_schedule': dict(kaneko_mi_schedule),
        'test_periods': test_period_status
    }

def main():
    """メイン処理"""
    print("=" * 80)
    print("残存する教師重複の詳細分析")
    print("=" * 80)
    
    # データ読み込み
    schedule = load_schedule('data/output/output.csv')
    mapping_repo = TeacherMappingRepository('data/config/teacher_subject_mapping.csv')
    followup_parser = EnhancedFollowUpParser('data/input/Follow-up.csv')
    test_periods = get_test_periods(followup_parser)
    
    print(f"\nテスト期間: {sorted(test_periods)}")
    
    # 教師重複分析
    conflicts = analyze_teacher_conflicts(schedule, mapping_repo, test_periods)
    
    # 結果表示
    print("\n" + "=" * 80)
    print("1. 真の教師重複（テスト期間外）")
    print("=" * 80)
    
    if conflicts['real_conflicts']:
        for (day, period), conflict_list in sorted(conflicts['real_conflicts'].items()):
            print(f"\n{day}曜{period}限:")
            for conflict in conflict_list:
                print(f"  教師: {conflict['teacher']}")
                for class_name, subject in conflict['assignments']:
                    print(f"    - {class_name}: {subject}")
    else:
        print("真の教師重複はありません！")
    
    print("\n" + "=" * 80)
    print("2. テスト期間中の教師配置（正常な巡回監督）")
    print("=" * 80)
    
    if conflicts['test_period_conflicts']:
        for (day, period), conflict_list in sorted(conflicts['test_period_conflicts'].items()):
            print(f"\n{day}曜{period}限（テスト）:")
            for conflict in conflict_list:
                print(f"  教師: {conflict['teacher']} - 巡回監督")
                for class_name, subject in conflict['assignments']:
                    print(f"    - {class_name}: {subject}")
    else:
        print("テスト期間中の教師配置はありません")
    
    print("\n" + "=" * 80)
    print("3. 5組合同授業（正常）")
    print("=" * 80)
    
    if conflicts['grade5_joint_classes']:
        for (day, period), conflict_list in sorted(conflicts['grade5_joint_classes'].items()):
            print(f"\n{day}曜{period}限:")
            for conflict in conflict_list:
                print(f"  教師: {conflict['teacher']} - 合同授業")
                for class_name, subject in conflict['assignments']:
                    print(f"    - {class_name}: {subject}")
    
    print("\n" + "=" * 80)
    print("4. 交流学級ペア（正常）")
    print("=" * 80)
    
    if conflicts['exchange_class_pairs']:
        for (day, period), conflict_list in sorted(conflicts['exchange_class_pairs'].items()):
            print(f"\n{day}曜{period}限:")
            for conflict in conflict_list:
                print(f"  教師: {conflict['teacher']} - 交流学級ペア")
                for class_name, subject in conflict['assignments']:
                    print(f"    - {class_name}: {subject}")
    
    # 金子み修正の確認
    print("\n" + "=" * 80)
    print("5. 金子み先生のテスト監督修正確認")
    print("=" * 80)
    
    kaneko_mi_status = check_kaneko_mi_fix(schedule, test_periods)
    
    print("\nテスト期間中の金子み先生:")
    if kaneko_mi_status['test_periods']:
        for (day, period), assignments in sorted(kaneko_mi_status['test_periods'].items()):
            print(f"{day}曜{period}限: {assignments}")
    else:
        print("テスト期間中の授業なし（修正成功！）")
    
    print("\n金子み先生の全スケジュール:")
    for (day, period), assignments in sorted(kaneko_mi_status['full_schedule'].items()):
        test_mark = " [テスト期間]" if (day, period) in test_periods else ""
        print(f"{day}曜{period}限{test_mark}: {assignments}")
    
    # サマリー
    print("\n" + "=" * 80)
    print("サマリー")
    print("=" * 80)
    
    real_conflict_count = sum(len(conflicts) for conflicts in conflicts['real_conflicts'].values())
    test_conflict_count = sum(len(conflicts) for conflicts in conflicts['test_period_conflicts'].values())
    
    print(f"真の教師重複: {real_conflict_count}件")
    print(f"テスト期間の巡回監督: {test_conflict_count}件（正常）")
    print(f"5組合同授業: {sum(len(c) for c in conflicts['grade5_joint_classes'].values())}件（正常）")
    print(f"交流学級ペア: {sum(len(c) for c in conflicts['exchange_class_pairs'].values())}件（正常）")
    
    if real_conflict_count == 0:
        print("\n✅ 全ての教師重複が解決されました！")
    else:
        print(f"\n⚠️ {real_conflict_count}件の真の教師重複が残っています")

if __name__ == "__main__":
    main()