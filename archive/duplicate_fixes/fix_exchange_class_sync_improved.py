#!/usr/bin/env python3
"""交流学級同期違反を修正するスクリプト（改良版）"""
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_manager import get_path_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """交流学級同期違反を修正（改良版）"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load("output/output.csv", school)
    
    # 交流学級と親学級の対応
    exchange_pairs = {
        ClassReference(1, 6): ClassReference(1, 1),
        ClassReference(1, 7): ClassReference(1, 2),
        ClassReference(2, 6): ClassReference(2, 3),
        ClassReference(2, 7): ClassReference(2, 2),
        ClassReference(3, 6): ClassReference(3, 3),
        ClassReference(3, 7): ClassReference(3, 2)
    }
    
    # 3年生の月・火・水の6限の同期違反を修正
    violations_to_fix = [
        # 月曜6限
        {'day': '月', 'period': 6, 'exchange': ClassReference(3, 6), 'parent': ClassReference(3, 3)},
        {'day': '月', 'period': 6, 'exchange': ClassReference(3, 7), 'parent': ClassReference(3, 2)},
        # 火曜6限
        {'day': '火', 'period': 6, 'exchange': ClassReference(3, 6), 'parent': ClassReference(3, 3)},
        {'day': '火', 'period': 6, 'exchange': ClassReference(3, 7), 'parent': ClassReference(3, 2)},
        # 水曜6限
        {'day': '水', 'period': 6, 'exchange': ClassReference(3, 6), 'parent': ClassReference(3, 3)},
        {'day': '水', 'period': 6, 'exchange': ClassReference(3, 7), 'parent': ClassReference(3, 2)},
    ]
    
    fixed_count = 0
    
    for violation in violations_to_fix:
        time_slot = TimeSlot(violation['day'], violation['period'])
        exchange_class = violation['exchange']
        parent_class = violation['parent']
        
        # 現在の割り当てを取得
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        
        if not exchange_assignment or not parent_assignment:
            logger.warning(f"{time_slot}に{exchange_class}または{parent_class}の割り当てがありません")
            continue
        
        # 交流学級が自立の場合はスキップ
        if exchange_assignment.subject.name in ['自立', '日生', '作業']:
            logger.info(f"{exchange_class}の{time_slot}は特別活動（{exchange_assignment.subject.name}）のためスキップ")
            continue
        
        # 同期が必要な場合
        if exchange_assignment.subject != parent_assignment.subject:
            logger.info(f"\n同期違反を修正: {time_slot}")
            logger.info(f"  {exchange_class}: {exchange_assignment.subject.name} → {parent_assignment.subject.name}")
            logger.info(f"  {parent_class}: {parent_assignment.subject.name}")
            
            # 親学級と同じ科目・教師を交流学級に配置
            try:
                # 交流学級の教師を取得（親学級と同じ科目の教師）
                exchange_teacher = school.get_assigned_teacher(parent_assignment.subject, exchange_class)
                
                if not exchange_teacher:
                    logger.info(f"{exchange_class}に{parent_assignment.subject.name}の教師が割り当てられていないため、親学級の教師を使用")
                    # 親学級の教師を使用
                    exchange_teacher = parent_assignment.teacher
                
                # 新しい割り当てを作成（親学級の教師を使用）
                new_assignment = Assignment(
                    exchange_class, 
                    parent_assignment.subject, 
                    parent_assignment.teacher  # 親学級の教師を直接使用
                )
                
                # 交流学級を更新
                try:
                    schedule.remove_assignment(time_slot, exchange_class)
                    schedule.assign(time_slot, new_assignment)
                    logger.info(f"✓ {exchange_class}を{parent_assignment.subject.name}に更新しました（教師: {parent_assignment.teacher.name}）")
                    fixed_count += 1
                except Exception as assign_error:
                    logger.error(f"✗ {exchange_class}の更新に失敗しました: {assign_error}")
                    # 元に戻す
                    try:
                        schedule.assign(time_slot, exchange_assignment)
                    except:
                        pass
                    
            except Exception as e:
                logger.error(f"修正中にエラーが発生: {e}")
                continue
    
    # 結果を保存
    if fixed_count > 0:
        logger.info(f"\n{fixed_count}件の同期違反を修正しました。結果を保存中...")
        schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
        logger.info("✓ output.csvを更新しました")
        
        # 修正後の確認
        logger.info("\n=== 修正後の3年生6限の同期状態 ===")
        for day in ['月', '火', '水']:
            time_slot = TimeSlot(day, 6)
            logger.info(f"\n{day}曜6限:")
            
            for exchange_class, parent_class in exchange_pairs.items():
                if exchange_class.grade != 3:
                    continue
                    
                exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                
                if exchange_assignment and parent_assignment:
                    exchange_subject = exchange_assignment.subject.name
                    parent_subject = parent_assignment.subject.name
                    exchange_teacher = exchange_assignment.teacher.name
                    parent_teacher = parent_assignment.teacher.name
                    
                    if exchange_subject in ['自立', '日生', '作業']:
                        status = "✓ (特別活動)"
                    elif exchange_subject == parent_subject:
                        status = "✓"
                    else:
                        status = "✗"
                    
                    logger.info(f"  {exchange_class}: {exchange_subject}({exchange_teacher}) / "
                              f"{parent_class}: {parent_subject}({parent_teacher}) {status}")
    else:
        logger.warning("修正する違反が見つかりませんでした")


if __name__ == "__main__":
    main()