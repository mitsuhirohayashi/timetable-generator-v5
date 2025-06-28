#!/usr/bin/env python3
"""output.csvに5組のデータを復元するスクリプト"""
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_manager import get_path_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """output.csvに5組のデータを復元"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    
    # 現在のoutput.csvを読み込み
    schedule = schedule_repo.load("output/output.csv", school)
    
    # input.csvから5組のデータを読み込み
    logger.info("input.csvから5組のデータを読み込み中...")
    input_schedule = schedule_repo.load("input/input.csv", school)
    
    # 5組のクラス
    grade5_classes = [
        ClassReference(1, 5),
        ClassReference(2, 5),
        ClassReference(3, 5)
    ]
    
    # 5組のデータをコピー
    copied_count = 0
    for class_ref in grade5_classes:
        logger.info(f"\n{class_ref.full_name}のデータをコピー中...")
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # input.csvから割り当てを取得
                input_assignment = input_schedule.get_assignment(time_slot, class_ref)
                
                if input_assignment:
                    # output.csvに割り当てをコピー
                    try:
                        # 既存の割り当てがある場合は削除
                        if schedule.get_assignment(time_slot, class_ref):
                            schedule.remove_assignment(time_slot, class_ref)
                        
                        # 新しい割り当てを追加
                        schedule.assign(time_slot, input_assignment)
                        copied_count += 1
                        logger.debug(f"{time_slot}: {input_assignment.subject.name} をコピー")
                    except Exception as e:
                        logger.error(f"{time_slot}のコピー中にエラー: {e}")
    
    logger.info(f"\n合計{copied_count}個の割り当てをコピーしました")
    
    # 結果を保存（改良版Writerで5組が確実に出力される）
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました（5組を含む）")
    
    # 確認のため、全クラスをリスト
    logger.info("\n=== 出力されたクラス一覧 ===")
    all_classes = set()
    for _, assignment in schedule.get_all_assignments():
        all_classes.add(assignment.class_ref)
    
    for grade in [1, 2, 3]:
        grade_classes = sorted([c for c in all_classes if c.grade == grade], 
                              key=lambda c: c.class_number)
        logger.info(f"{grade}年: {', '.join([c.full_name for c in grade_classes])}")


if __name__ == "__main__":
    main()