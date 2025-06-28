#!/usr/bin/env python3
"""時間割の制約違反を包括的にチェックするスクリプト（正常パターン除外対応版）"""
import sys
import json
import os
from pathlib import Path
from collections import defaultdict

# timetable_v5ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.domain.services.core.unified_constraint_system import UnifiedConstraintSystem, AssignmentContext
from src.domain.value_objects.time_slot import TimeSlot
from src.infrastructure.config.constraint_loader import ConstraintLoader
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.domain.services.core.test_period_protector import TestPeriodProtector as CoreTestPeriodProtector


def load_exclusion_rules():
    """制約除外ルールを読み込む"""
    rules_path = os.path.join(path_config.data_dir, "config", "constraint_exclusion_rules.json")
    if os.path.exists(rules_path):
        with open(rules_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('exclusion_rules', {})
    return {}


def main():
    """メイン処理"""
    print("=== 時間割制約違反チェック（正常パターン除外対応版） ===\n")
    
    # 除外ルールを読み込む
    exclusion_rules = load_exclusion_rules()
    
    # リポジリ初期化
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    school_repo = CSVSchoolRepository(path_config.data_dir)
    
    # 学校データ読み込み
    print("学校データを読み込み中...")
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 制約システム初期化（学校データを渡す）
    constraint_system = UnifiedConstraintSystem()
    constraint_system.school = school
    
    # 制約登録サービスを使用（生成時と同じ方法）
    constraint_registration_service = ConstraintRegistrationService()
    constraint_registration_service.register_all_constraints(
        constraint_system,
        path_config.data_dir,
        teacher_absences=None
    )
    
    # 制約リストを取得（すべての優先度から制約を集める）
    constraints = []
    for priority_constraints in constraint_system.constraints.values():
        constraints.extend(priority_constraints)
    
    # 時間割読み込み
    print(f"時間割を読み込み中: {path_config.default_output_csv}")
    schedule = schedule_repo.load_desired_schedule(
        str(path_config.default_output_csv),
        school
    )
    
    # 違反をチェック
    print("\n制約違反をチェック中...\n")
    
    all_violations = []
    empty_slots = []
    total_slots = 0
    
    # --- TestPeriodProtectorによるチェック ---
    test_period_protector = CoreTestPeriodProtector()
    test_period_violations = test_period_protector.check_violations(schedule)
    if test_period_violations:
        print(f"TestPeriodProtectorが {len(test_period_violations)} 件の違反を検出しました。")

    # 各制約の validate メソッドを使用して違反をチェック
    for constraint in constraints:
        result = constraint.validate(schedule, school)
        if result.violations:
            all_violations.extend(result.violations)
    
    # 空きコマをチェック
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):  # 1〜6時限
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                total_slots += 1
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                # 空きコマチェック
                if not assignment or not assignment.subject:
                    # 月曜6時限の「欠」と火水金6時限の「YT」は除外
                    if not ((day == "月" and period == 6) or 
                           (day in ["火", "水", "金"] and period == 6)):
                        empty_slots.append((time_slot, class_ref))
                    continue
    
    # 結果表示
    print("=== チェック結果 ===\n")
    
    if not all_violations and not empty_slots and not test_period_violations:
        print("✅ すべての制約を満たしています！")
        print("✅ 空きコマもありません！")
    else:
        # --- テスト期間違反の表示 ---
        if test_period_violations:
            print(f"❌ 【テスト期間保護違反】({len(test_period_violations)}件)")
            for i, violation in enumerate(test_period_violations[:5]):
                # violation is a dict, so access items with keys
                print(f"  - {violation['message']}")
            if len(test_period_violations) > 5:
                print(f"  ... 他 {len(test_period_violations) - 5} 件")
            print()

        if all_violations:
            # 違反を種類別に集計
            violations_by_type = defaultdict(list)
            excluded_violations = []
            
            for violation in all_violations:
                # violation.descriptionから違反の種類を推定
                if "体育館使用制約" in violation.description:
                    violations_by_type["体育館使用制約違反"].append(violation)
                elif "教師重複違反" in violation.description:
                    # 正常パターンはメッセージが調整されているため、そのまま記録
                    violations_by_type["教師重複制約違反"].append(violation)
                elif "交流学級" in violation.description:
                    violations_by_type["交流学級同期制約違反"].append(violation)
                elif "日内重複" in violation.description:
                    violations_by_type["日内重複制約違反"].append(violation)
                else:
                    violations_by_type["その他の制約違反"].append(violation)
            
            # 実際の違反数を計算
            actual_violations_count = sum(len(violations) for violations in violations_by_type.values())
            
            if actual_violations_count > 0:
                print(f"❌ {actual_violations_count} 件の一般制約違反が見つかりました：\n")
            
            for violation_type, instances in violations_by_type.items():
                print(f"【{violation_type}】({len(instances)}件)")
                # 最初の5件を表示
                for i, violation in enumerate(instances[:5]):
                    print(f"  - {violation.description}")
                if len(instances) > 5:
                    print(f"  ... 他 {len(instances) - 5} 件")
                print()
        
        if empty_slots:
            print(f"⚠️  空きコマが {len(empty_slots)} 個あります：\n")
            # クラスごとに集計
            empty_by_class = defaultdict(int)
            for time_slot, class_ref in empty_slots:
                empty_by_class[class_ref] += 1
            
            for class_ref, count in sorted(empty_by_class.items(), key=lambda x: x[1], reverse=True):
                print(f"  {class_ref}: {count} コマ")
    
    # サマリー
    print(f"\n=== サマリー ===")
    print(f"総コマ数: {total_slots}")
    print(f"空きコマ数: {len(empty_slots)} ({len(empty_slots)/total_slots*100:.1f}%)")
    
    total_violation_count = len(test_period_violations)
    if all_violations:
        actual_violations_count = sum(len(v) for v in violations_by_type.values())
        total_violation_count += actual_violations_count
    
    if total_violation_count > 0:
        print(f"総違反件数: {total_violation_count}")
        print(f"  - テスト期間保護違反: {len(test_period_violations)}件")
        if 'actual_violations_count' in locals() and actual_violations_count > 0:
            print(f"  - 一般制約違反: {actual_violations_count}件")
            # 除外ルールが適用されたことを通知
            if actual_violations_count < len(all_violations):
                print(f"（注：一般制約において正常パターンとして除外された項目があります）")


if __name__ == "__main__":
    main()