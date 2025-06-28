#!/usr/bin/env python3
"""改善版CSP生成器のテストスクリプト"""

import sys
import os
import logging
from pathlib import Path

# パスを追加
sys.path.append(str(Path(__file__).parent))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.domain.services.implementations.improved_csp_generator import ImprovedCSPGenerator
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.infrastructure.config.path_config import path_config
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """改善版CSP生成器をテスト"""
    print("=== 改善版CSP生成器テスト ===\n")
    
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    school_repo = CSVSchoolRepository(path_config.data_dir)
    
    # 学校データ読み込み
    print("学校データを読み込み中...")
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 制約システム初期化
    print("制約システムを初期化中...")
    constraint_system = UnifiedConstraintSystem()
    constraint_system.school = school
    
    # 制約登録
    constraint_registration_service = ConstraintRegistrationService()
    constraint_registration_service.register_all_constraints(
        constraint_system,
        path_config.data_dir
    )
    
    # Follow-up制約読み込み
    print("Follow-up制約を読み込み中...")
    followup_parser = EnhancedFollowUpParser()
    followup_constraints = followup_parser.parse_file('data/input/Follow-up.csv')
    
    # 初期スケジュール読み込み（input.csvがあれば）
    print("初期スケジュールを読み込み中...")
    try:
        initial_schedule = schedule_repo.load('data/input/input.csv', school)
    except:
        initial_schedule = None
        print("初期スケジュールなしで生成します")
    
    # 改善版CSP生成器で生成
    print("\n改善版CSP生成器で時間割を生成中...")
    generator = ImprovedCSPGenerator(constraint_system)
    
    # 生成実行
    schedule = generator.generate(
        school=school,
        initial_schedule=initial_schedule,
        followup_constraints=followup_constraints
    )
    
    # 結果を保存
    print("\n生成結果を保存中...")
    output_path = 'data/output/output_improved.csv'
    schedule_repo.save(schedule, output_path)
    print(f"時間割を保存しました: {output_path}")
    
    # 違反チェック
    print("\n制約違反をチェック中...")
    violations = []
    
    # 各制約でvalidateメソッドを使用
    for priority_constraints in constraint_system.constraints.values():
        for constraint in priority_constraints:
            result = constraint.validate(schedule, school)
            if result.violations:
                violations.extend(result.violations)
    
    # 結果表示
    print("\n=== 生成結果 ===")
    print(f"総違反数: {len(violations)}")
    
    if violations:
        # 違反をタイプ別に集計
        violation_types = {}
        for v in violations:
            constraint_name = v.constraint_name
            if constraint_name not in violation_types:
                violation_types[constraint_name] = 0
            violation_types[constraint_name] += 1
        
        print("\n違反タイプ別:")
        for vtype, count in sorted(violation_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {vtype}: {count}件")
            
        # 主要な違反の詳細を表示
        print("\n主要な違反（上位5件）:")
        for v in violations[:5]:
            print(f"  - {v.constraint_name}: {v.details}")
    else:
        print("✅ すべての制約を満たしています！")
    
    # 改善効果の評価
    print("\n=== 改善効果 ===")
    print("改善前: 5組同期違反100件、教師重複18件")
    
    # 5組同期違反をカウント
    grade5_violations = sum(1 for v in violations if '5組' in v.constraint_name)
    teacher_conflicts = sum(1 for v in violations if '教師重複' in v.constraint_name)
    
    print(f"改善後: 5組同期違反{grade5_violations}件、教師重複{teacher_conflicts}件")
    
    if grade5_violations < 100 or teacher_conflicts < 18:
        print("✅ 改善効果が確認されました！")
    else:
        print("❌ 改善効果が不十分です。さらなる調整が必要です。")

if __name__ == "__main__":
    main()