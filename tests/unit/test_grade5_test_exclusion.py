#!/usr/bin/env python3
"""
Grade 5 Test Exclusion Constraint検証スクリプト

5組がテスト期間中に通常クラスのテスト科目を受けないことを確認
"""
import sys
from pathlib import Path
import logging

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment
from src.domain.constraints.grade5_test_exclusion_constraint import Grade5TestExclusionConstraint
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_grade5_test_exclusion():
    """Grade 5 Test Exclusion Constraintのテスト"""
    logger.info("=== Grade 5 Test Exclusion Constraint テスト開始 ===")
    
    # テスト用のスケジュールと学校データを作成
    schedule = Schedule()
    school_repo = CSVSchoolRepository("data")
    school = school_repo.load_school_data()
    
    # テスト期間を設定（水曜の2時間目）
    schedule.test_periods = {
        "水": [2]
    }
    logger.info(f"テスト期間設定: {schedule.test_periods}")
    
    # 制約を作成
    constraint = Grade5TestExclusionConstraint()
    
    # テストケース1: 通常クラス（1-1）に数学のテストを配置
    logger.info("\nテストケース1: 通常クラス（1-1）に数学を配置")
    time_slot = TimeSlot("水", 2)
    class_1_1 = ClassReference(1, 1)
    math_teacher = Teacher("梶永先生")
    assignment_1_1 = Assignment(class_1_1, Subject("数"), math_teacher)
    schedule.assign(time_slot, assignment_1_1)
    logger.info(f"  1-1に数学を配置完了")
    
    # テストケース2: 5組（1-5）に同じ科目（数学）を配置しようとする（失敗するべき）
    logger.info("\nテストケース2: 5組（1-5）に数学を配置（失敗するべき）")
    class_1_5 = ClassReference(1, 5)
    assignment_1_5_math = Assignment(class_1_5, Subject("数"), math_teacher)
    
    # 制約チェック
    can_place = constraint.check(schedule, school, time_slot, assignment_1_5_math)
    logger.info(f"  配置可能？: {can_place}")
    assert not can_place, "5組に数学を配置できてしまった（エラー）"
    logger.info("  ✓ 正しく配置が拒否されました")
    
    # テストケース3: 5組（1-5）に別の科目（国語）を配置（成功するべき）
    logger.info("\nテストケース3: 5組（1-5）に国語を配置（成功するべき）")
    japanese_teacher = Teacher("井野口先生")
    assignment_1_5_japanese = Assignment(class_1_5, Subject("国"), japanese_teacher)
    
    can_place = constraint.check(schedule, school, time_slot, assignment_1_5_japanese)
    logger.info(f"  配置可能？: {can_place}")
    assert can_place, "5組に国語を配置できなかった（エラー）"
    schedule.assign(time_slot, assignment_1_5_japanese)
    logger.info("  ✓ 正しく配置されました")
    
    # テストケース4: 制約違反の検証
    logger.info("\nテストケース4: 既存スケジュールの制約違反を検証")
    # 一旦5組の国語を削除して数学を強制配置
    # 5組の同期を一時的に無効化して個別に配置
    schedule._grade5_sync_enabled = False
    schedule.remove_assignment(time_slot, class_1_5)
    schedule.assign(time_slot, assignment_1_5_math)
    schedule._grade5_sync_enabled = True
    
    # 制約違反をチェック
    result = constraint.validate(schedule, school)
    logger.info(f"  違反数: {len(result.violations)}")
    
    if result.violations:
        for violation in result.violations:
            logger.info(f"  違反: {violation.description}")
        assert len(result.violations) == 1, "違反数が予想と異なる"
        logger.info("  ✓ 正しく違反が検出されました")
    else:
        raise AssertionError("違反が検出されなかった")
    
    # テストケース5: テスト期間外での配置（全て成功するべき）
    logger.info("\nテストケース5: テスト期間外（月曜1限）での配置")
    non_test_slot = TimeSlot("月", 1)
    
    # 1-1に数学
    schedule.assign(non_test_slot, assignment_1_1)
    
    # 1-5にも数学（テスト期間外なので成功するべき）
    can_place = constraint.check(schedule, school, non_test_slot, assignment_1_5_math)
    logger.info(f"  5組に数学配置可能？: {can_place}")
    assert can_place, "テスト期間外で5組に数学を配置できなかった"
    schedule.assign(non_test_slot, assignment_1_5_math)
    logger.info("  ✓ テスト期間外では同じ科目を配置可能")
    
    logger.info("\n=== 全てのテストケースが成功しました ===")
    return True

if __name__ == "__main__":
    try:
        test_grade5_test_exclusion()
        logger.info("\n✅ Grade 5 Test Exclusion Constraintは正しく実装されています")
    except Exception as e:
        logger.error(f"\n❌ テスト失敗: {e}", exc_info=True)
        sys.exit(1)