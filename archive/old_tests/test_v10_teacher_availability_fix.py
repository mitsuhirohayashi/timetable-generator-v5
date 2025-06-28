#!/usr/bin/env python3
"""
Test the fixed V10 teacher availability initialization
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.config.config_loader import ConfigLoader
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.domain.entities.school import School
from src.domain.services.constraint_validator import ConstraintValidator
from src.infrastructure.config.constraint_loader import ConstraintLoader
from src.domain.services.ultrathink.ultrathink_perfect_generator_v10 import UltrathinkPerfectGeneratorV10
from src.domain.services.ultrathink.ultrathink_perfect_generator_v10_fixed import UltrathinkPerfectGeneratorV10Fixed

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def compare_teacher_availability():
    """V10とV10 Fixedの教師利用可能性初期化を比較"""
    try:
        # リポジトリとローダーの初期化
        schedule_repo = CSVScheduleRepository()
        config_loader = ConfigLoader("data/config")
        absence_loader = TeacherAbsenceLoader("data/input/Follow-up.csv")
        
        # Follow-up.csvの解析
        followup_parser = EnhancedFollowUpParser("data/input")
        followup_info = followup_parser.parse_file("Follow-up.csv")
        
        # 学校データの作成
        school = School()
        config_loader.load_school_structure(school)
        config_loader.load_standard_hours(school)
        config_loader.load_teacher_assignments(school)
        absence_loader.load_teacher_absences(school)
        
        # 既存のスケジュールを読み込み
        initial_schedule = schedule_repo.load("data/input/input.csv")
        
        # 制約のロード
        constraint_loader = ConstraintLoader(
            school=school,
            followup_info=followup_info,
            exchange_class_pairs=config_loader.get_exchange_class_pairs()
        )
        constraints = constraint_loader.load_all_constraints()
        
        # V10のテスト
        logger.info("\n=== V10 Original ===")
        generator_v10 = UltrathinkPerfectGeneratorV10()
        teacher_avail_v10 = generator_v10._initialize_teacher_availability(school, initial_schedule)
        
        # V10 Fixedのテスト
        logger.info("\n=== V10 Fixed ===")
        generator_v10_fixed = UltrathinkPerfectGeneratorV10Fixed()
        teacher_avail_v10_fixed = generator_v10_fixed._initialize_teacher_availability_fixed(school, initial_schedule)
        
        # 結果の比較
        logger.info("\n=== 比較結果 ===")
        logger.info(f"V10 Original - 既存教師配置数: 0")  # V10では常に0
        logger.info(f"V10 Fixed - 既存教師配置数: {generator_v10_fixed.stats['existing_teacher_assignments']}")
        
        # いくつかの教師の利用可能時間を比較
        sample_teachers = ["井野口", "金子ひ", "塚本", "野口", "永山"]
        
        for teacher_name in sample_teachers:
            if teacher_name in teacher_avail_v10 and teacher_name in teacher_avail_v10_fixed:
                v10_available = len(teacher_avail_v10[teacher_name])
                v10_fixed_available = len(teacher_avail_v10_fixed[teacher_name])
                logger.info(f"{teacher_name}先生 - V10: {v10_available}スロット利用可能, V10 Fixed: {v10_fixed_available}スロット利用可能")
                
                # 差分を表示
                if v10_available != v10_fixed_available:
                    v10_slots = teacher_avail_v10[teacher_name]
                    v10_fixed_slots = teacher_avail_v10_fixed[teacher_name]
                    busy_slots = v10_slots - v10_fixed_slots
                    logger.info(f"  → V10 Fixedで追加でbusyになったスロット: {len(busy_slots)}個")
                    for day, period in sorted(busy_slots)[:3]:  # 最初の3つだけ表示
                        logger.info(f"    - {day}{period}限")
        
        # 全体の統計
        logger.info("\n=== 全体統計 ===")
        logger.info(f"初期割り当て数: {len(initial_schedule.get_all_assignments())}")
        
        # V10 Fixedで実際に教師が検出された割り当て数を確認
        detected_count = 0
        for time_slot, assignment in initial_schedule.get_all_assignments():
            if assignment.subject.name in generator_v10_fixed.fixed_subjects:
                continue
            if (time_slot.day, time_slot.period) in generator_v10_fixed.test_periods:
                continue
                
            teacher = assignment.teacher
            if not teacher:
                subject_obj = Subject(assignment.subject.name)
                teacher = school.get_assigned_teacher(subject_obj, assignment.class_ref)
            
            if teacher:
                detected_count += 1
        
        logger.info(f"教師を特定できた割り当て数: {detected_count}")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    from src.domain.value_objects.time_slot import Subject
    compare_teacher_availability()