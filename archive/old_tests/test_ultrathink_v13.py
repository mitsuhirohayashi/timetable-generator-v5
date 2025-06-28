#!/usr/bin/env python3
"""
Ultrathink Perfect Generator V13のテストスクリプト
教師中心スケジューリングの効果を検証
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.application.services.schedule_generation_service import ScheduleGenerationService
from src.domain.services.unified_constraint_system import UnifiedConstraintSystem
from src.infrastructure.config.path_manager import PathManager
from src.infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.logging_config import LoggingConfig
# from scripts.analysis.check_violations import check_all_violations  # Not needed for basic test


def main():
    """メイン処理"""
    # ロギング設定（詳細モード）
    LoggingConfig.setup_logging(
        log_level='DEBUG',
        console_output=True,
        simple_format=False
    )
    
    logger = logging.getLogger(__name__)
    
    logger.info("=== Ultrathink V13 (教師中心スケジューリング) テスト開始 ===")
    
    # パス管理の初期化
    path_manager = PathManager()
    
    # リポジトリ初期化
    repository = CSVScheduleRepository()
    
    # データ読み込み
    logger.info("データを読み込み中...")
    from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
    school_repo = CSVSchoolRepository()
    school = school_repo.load_school_data()
    initial_schedule = repository.load("input/input.csv", school)
    
    # Follow-up.csvから教師不在情報を読み込み
    natural_parser = NaturalFollowUpParser(path_manager.input_dir)
    parse_result = natural_parser.parse_file("Follow-up.csv")
    
    if parse_result["parse_success"]:
        # 教師不在情報を適用
        absence_loader = TeacherAbsenceLoader()
        if parse_result.get("teacher_absences"):
            absence_loader.update_absences_from_parsed_data(parse_result["teacher_absences"])
            school.update_teacher_availabilities(absence_loader.get_teacher_absences())
    
    # 制約システムの初期化
    constraint_system = UnifiedConstraintSystem()
    constraint_system.register_default_constraints()
    
    # スケジュール生成サービスの初期化
    generation_service = ScheduleGenerationService(
        constraint_system=constraint_system,
        path_manager=path_manager
    )
    
    # V13で生成
    logger.info("\n=== Ultrathink V13で時間割を生成中... ===")
    schedule = generation_service.generate_schedule(
        school=school,
        initial_schedule=initial_schedule,
        use_ultrathink=True
    )
    
    # 結果を保存
    output_path = path_manager.get_output_path("output.csv")
    repository.save_schedule(schedule, output_path)
    logger.info(f"生成された時間割を保存しました: {output_path}")
    
    # 違反チェック
    logger.info("\n=== 生成結果の違反チェック ===")
    validation_result = constraint_system.validate_schedule(schedule, school)
    violations_summary = {
        'total_violations': len(validation_result.violations),
        'non_test_violations': len([v for v in validation_result.violations if "テスト期間" not in v.description])
    }
    
    # 教師重複の詳細チェック
    logger.info("\n=== 教師重複の詳細チェック ===")
    teacher_duplicates = 0
    duplicate_details = []
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            # テスト期間はスキップ
            if day in ["月", "火", "水"] and period in [1, 2, 3]:
                continue
            
            teacher_assignments = {}
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(TimeSlot(day, period), class_ref)
                if assignment and assignment.teacher:
                    teacher_name = assignment.teacher.name
                    if teacher_name in teacher_assignments:
                        teacher_duplicates += 1
                        duplicate_details.append(
                            f"{day}曜{period}限: {teacher_name}先生が "
                            f"{teacher_assignments[teacher_name]}と{class_ref}で重複"
                        )
                    else:
                        teacher_assignments[teacher_name] = class_ref
    
    if teacher_duplicates > 0:
        logger.error(f"\n教師重複が{teacher_duplicates}件見つかりました:")
        for detail in duplicate_details[:10]:  # 最初の10件を表示
            logger.error(f"  - {detail}")
    else:
        logger.info("教師重複は完全に解消されました！")
    
    # 空きスロットの確認
    logger.info("\n=== 空きスロットの確認 ===")
    empty_slots = 0
    for class_ref in school.get_all_classes():
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                if not schedule.get_assignment(TimeSlot(day, period), class_ref):
                    empty_slots += 1
    
    logger.info(f"空きスロット数: {empty_slots}")
    
    # 統計情報
    logger.info("\n=== 生成統計 ===")
    logger.info(f"総違反数: {violations_summary['total_violations']}")
    logger.info(f"テスト期間を除く違反数: {violations_summary['non_test_violations']}")
    logger.info(f"教師重複: {teacher_duplicates}件")
    logger.info(f"空きスロット: {empty_slots}個")
    
    logger.info("\n=== Ultrathink V13テスト完了 ===")


if __name__ == "__main__":
    from src.domain.value_objects.time_slot import TimeSlot
    main()