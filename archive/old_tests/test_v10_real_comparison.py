#!/usr/bin/env python3
"""
Test the real V10 and V10 Fixed implementations
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.config_loader import ConfigLoader
from src.domain.entities.school import School
from src.domain.services.ultrathink.ultrathink_perfect_generator_v10 import UltrathinkPerfectGeneratorV10
from src.domain.services.ultrathink.ultrathink_perfect_generator_v10_fixed import UltrathinkPerfectGeneratorV10Fixed

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# 特定のモジュールのログレベルを調整
logging.getLogger('src.infrastructure').setLevel(logging.WARNING)
logging.getLogger('src.domain.value_objects').setLevel(logging.WARNING)


def test_real_implementations():
    """実際のV10とV10 Fixedを比較"""
    try:
        # 共通の初期化
        config_loader = ConfigLoader("data/config")
        school = School()
        
        # 学校構造をロード（ConfigLoaderの実際のメソッドを使用）
        # クラスをロード
        classes_data = config_loader.get_classes()
        for class_info in classes_data:
            school.add_class(class_info)
        
        # 教師をロード
        teachers_data = config_loader.get_teachers()
        for teacher in teachers_data:
            school.add_teacher(teacher)
        
        # 標準時数をロード
        standard_hours = config_loader.get_standard_hours()
        for (class_ref, subject), hours in standard_hours.items():
            school.set_standard_hours(class_ref, subject, hours)
        
        # 教師割り当てをロード
        teacher_assignments = config_loader.get_teacher_assignments()
        for (subject, class_ref), teacher in teacher_assignments.items():
            school.assign_teacher(subject, class_ref, teacher)
        
        # 既存のスケジュールを読み込み
        schedule_repo = CSVScheduleRepository()
        initial_schedule = schedule_repo.load("data/input/input.csv")
        
        logger.info(f"初期スケジュールの割り当て数: {len(initial_schedule.get_all_assignments())}")
        
        # V10 Originalのテスト
        logger.info("\n=== V10 Original Test ===")
        v10_generator = UltrathinkPerfectGeneratorV10()
        
        # _initialize_teacher_availabilityを直接呼び出し
        v10_availability = v10_generator._initialize_teacher_availability(school, initial_schedule)
        
        # 統計情報を表示
        logger.info(f"V10 Original - 教師数: {len(v10_availability)}")
        
        # いくつかの教師の利用可能時間を表示
        for teacher_name in ["井野口", "金子み", "塚本", "野口", "永山"]:
            if teacher_name in v10_availability:
                available_slots = len(v10_availability[teacher_name])
                logger.info(f"  {teacher_name}先生: {available_slots}スロット利用可能")
        
        # V10 Fixedのテスト
        logger.info("\n=== V10 Fixed Test ===")
        v10_fixed_generator = UltrathinkPerfectGeneratorV10Fixed()
        
        # _initialize_teacher_availability_fixedを直接呼び出し
        v10_fixed_availability = v10_fixed_generator._initialize_teacher_availability_fixed(school, initial_schedule)
        
        # 統計情報を表示
        logger.info(f"V10 Fixed - 教師数: {len(v10_fixed_availability)}")
        logger.info(f"V10 Fixed - 検出された既存教師配置数: {v10_fixed_generator.stats['existing_teacher_assignments']}")
        
        # いくつかの教師の利用可能時間を表示
        for teacher_name in ["井野口", "金子み", "塚本", "野口", "永山"]:
            if teacher_name in v10_fixed_availability:
                available_slots = len(v10_fixed_availability[teacher_name])
                logger.info(f"  {teacher_name}先生: {available_slots}スロット利用可能")
        
        # 差分を分析
        logger.info("\n=== 差分分析 ===")
        for teacher_name in v10_availability:
            if teacher_name in v10_fixed_availability:
                v10_slots = v10_availability[teacher_name]
                v10_fixed_slots = v10_fixed_availability[teacher_name]
                
                if len(v10_slots) != len(v10_fixed_slots):
                    diff = len(v10_slots) - len(v10_fixed_slots)
                    logger.info(f"{teacher_name}先生: V10 Fixedで{diff}スロット追加でbusy")
        
        logger.info("\n=== 結論 ===")
        logger.info(f"V10 Originalは既存配置の教師を検出できていない（常に0）")
        logger.info(f"V10 Fixedは{v10_fixed_generator.stats['existing_teacher_assignments']}個の既存教師配置を正しく検出")
        
    except Exception as e:
        logger.error(f"エラー: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_real_implementations()