#!/usr/bin/env python3
"""Grade5修正後の違反を分析"""

import logging
from pathlib import Path
from collections import defaultdict
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.domain.value_objects.time_slot import TimeSlot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_violations(schedule_file, school):
    """違反を分析"""
    # 制約システム初期化
    constraint_system = UnifiedConstraintSystem()
    constraint_system.school = school
    
    # 制約登録
    constraint_registration_service = ConstraintRegistrationService()
    constraint_registration_service.register_all_constraints(
        constraint_system,
        Path("data"),
        teacher_absences=None
    )
    
    # スケジュール読み込み
    schedule_repo = CSVScheduleRepository()
    schedule = schedule_repo.load(schedule_file, school)
    
    # 違反カテゴリ別集計
    violation_summary = defaultdict(list)
    
    # 各制約の validate メソッドを使用
    for priority_constraints in constraint_system.constraints.values():
        for constraint in priority_constraints:
            result = constraint.validate(schedule, school)
            if result.violations:
                for violation in result.violations:
                    violation_summary[type(constraint).__name__].append(violation)
    
    return violation_summary

def main():
    # 学校データ読み込み
    school_repo = CSVSchoolRepository()
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    
    # 元のファイルの違反チェック
    logger.info("=== 元のファイルの違反分析 ===")
    original_violations = analyze_violations("data/output/output.csv", school)
    
    total_original = sum(len(v) for v in original_violations.values())
    logger.info(f"総違反数: {total_original}")
    
    for constraint_name, violations in original_violations.items():
        logger.info(f"{constraint_name}: {len(violations)}件")
    
    # 修正後のファイルの違反チェック
    logger.info("\n=== 修正後のファイルの違反分析 ===")
    fixed_violations = analyze_violations("data/output/output_grade5_sync_fixed.csv", school)
    
    total_fixed = sum(len(v) for v in fixed_violations.values())
    logger.info(f"総違反数: {total_fixed}")
    
    for constraint_name, violations in fixed_violations.items():
        logger.info(f"{constraint_name}: {len(violations)}件")
    
    # 改善状況
    logger.info(f"\n=== 改善状況 ===")
    logger.info(f"違反削減: {total_original} → {total_fixed} ({total_original - total_fixed}件削減)")
    
    # Grade5同期違反の確認
    if 'Grade5SameSubjectConstraint' in original_violations:
        original_g5 = len(original_violations['Grade5SameSubjectConstraint'])
        fixed_g5 = len(fixed_violations.get('Grade5SameSubjectConstraint', []))
        logger.info(f"Grade5同期違反: {original_g5} → {fixed_g5}")

if __name__ == "__main__":
    main()