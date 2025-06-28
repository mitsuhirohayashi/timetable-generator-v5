#!/usr/bin/env python3
"""
Ultrathink V13の簡単なテスト
教師中心スケジューリングの効果を確認
"""

import sys
import logging
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent))

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """メイン処理"""
    logger.info("=== Ultrathink V13 Simple Test ===")
    
    # 必要なインポート
    from src.domain.entities.school import School
    from src.domain.entities.schedule import Schedule
    from src.domain.value_objects.time_slot import TimeSlot, ClassReference
    from src.infrastructure.config.path_config import path_config
    from src.domain.services.ultrathink.ultrathink_perfect_generator_v13 import UltrathinkPerfectGeneratorV13
    from src.domain.constraints.base import Constraint
    
    # Schoolオブジェクトを作成（簡単なテスト用）
    school = School()
    
    # いくつかのクラスを追加
    for grade in [1, 2, 3]:
        for class_num in [1, 2, 3, 5, 6, 7]:
            class_ref = ClassReference(grade, class_num)
            school.add_class(class_ref)
    
    # 制約リスト（空でもOK）
    constraints = []
    
    # 初期スケジュール（空）
    initial_schedule = Schedule()
    
    # V13を使用して生成
    logger.info("V13で時間割を生成中...")
    generator = UltrathinkPerfectGeneratorV13()
    
    try:
        schedule = generator.generate(school, constraints, initial_schedule)
        logger.info("生成完了!")
        
        # 統計情報を表示
        assignments = schedule.get_all_assignments()
        logger.info(f"総割り当て数: {len(assignments)}")
        
        # 教師重複をチェック
        teacher_duplicates = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                teachers_at_time = {}
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        if teacher_name in teachers_at_time:
                            teacher_duplicates += 1
                            logger.warning(
                                f"教師重複: {teacher_name} @ {time_slot} "
                                f"({teachers_at_time[teacher_name]} & {class_ref})"
                            )
                        else:
                            teachers_at_time[teacher_name] = class_ref
        
        logger.info(f"教師重複数: {teacher_duplicates}")
        
        # 結果を保存
        from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
        repo = CSVScheduleRepository()
        repo.save_schedule(schedule, "output_v13_test.csv")
        logger.info("結果を output_v13_test.csv に保存しました")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("=== テスト完了 ===")


if __name__ == "__main__":
    main()