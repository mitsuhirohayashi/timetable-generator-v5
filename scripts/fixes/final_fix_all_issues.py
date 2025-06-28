#!/usr/bin/env python3
"""最終的にすべての問題を修正するスクリプト"""
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_manager import get_path_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """すべての問題を最終的に修正"""
    path_manager = get_path_manager()
    
    # リポジトリの初期化
    schedule_repo = CSVScheduleRepository(path_manager.data_dir)
    school_repo = CSVSchoolRepository(path_manager.data_dir)
    
    # データの読み込み
    logger.info("データを読み込み中...")
    school = school_repo.load_school_data()
    schedule = schedule_repo.load(str(path_manager.output_dir / "output.csv"), school)
    
    # 問題1: 3年3組の水曜3限・4限が空欄になっている問題を修正
    logger.info("\n=== 問題1: 3年3組の水曜3限・4限の空欄を修正 ===")
    
    class_ref = ClassReference(3, 3)
    
    # 水曜3限に技を配置
    wed_3_slot = TimeSlot("水", 3)
    if not schedule.get_assignment(wed_3_slot, class_ref):
        tech_subject = Subject("技")
        tech_teacher = school.get_assigned_teacher(tech_subject, class_ref)
        if tech_teacher:
            assignment = Assignment(class_ref, tech_subject, tech_teacher)
            if schedule.assign(wed_3_slot, assignment):
                logger.info(f"✓ 水曜3限に技({tech_teacher.name})を配置")
    
    # 水曜4限に美を配置
    wed_4_slot = TimeSlot("水", 4)
    if not schedule.get_assignment(wed_4_slot, class_ref):
        beauty_subject = Subject("美")
        beauty_teacher = school.get_assigned_teacher(beauty_subject, class_ref)
        if beauty_teacher:
            assignment = Assignment(class_ref, beauty_subject, beauty_teacher)
            if schedule.assign(wed_4_slot, assignment):
                logger.info(f"✓ 水曜4限に美({beauty_teacher.name})を配置")
    
    # 問題2: 3年3組の金曜5限を数学に変更（美→数）
    logger.info("\n=== 問題2: 3年3組の金曜5限を数学に変更 ===")
    
    fri_5_slot = TimeSlot("金", 5)
    current_assignment = schedule.get_assignment(fri_5_slot, class_ref)
    
    if current_assignment and current_assignment.subject.name == "美":
        # 美術を削除
        schedule.remove_assignment(fri_5_slot, class_ref)
        
        # 金曜3限の数学と入れ替え
        fri_3_slot = TimeSlot("金", 3)
        fri_3_assignment = schedule.get_assignment(fri_3_slot, class_ref)
        
        if fri_3_assignment and fri_3_assignment.subject.name == "数":
            # 金曜3限を美術に変更
            schedule.remove_assignment(fri_3_slot, class_ref)
            beauty_assignment = Assignment(class_ref, current_assignment.subject, current_assignment.teacher)
            
            # 金曜5限を数学に変更
            math_assignment = Assignment(class_ref, fri_3_assignment.subject, fri_3_assignment.teacher)
            
            if schedule.assign(fri_5_slot, math_assignment):
                logger.info("✓ 金曜5限: 美 → 数")
                if schedule.assign(fri_3_slot, beauty_assignment):
                    logger.info("✓ 金曜3限: 数 → 美")
    
    # 問題3: 全体的な確認と微調整
    logger.info("\n=== 問題3: 全体的な確認 ===")
    
    # 交流学級の自立活動違反を再確認
    exchange_violations = []
    exchange_pairs = [
        (ClassReference(1, 6), ClassReference(1, 1)),
        (ClassReference(1, 7), ClassReference(1, 2)),
        (ClassReference(2, 6), ClassReference(2, 3)),
        (ClassReference(2, 7), ClassReference(2, 2)),
        (ClassReference(3, 6), ClassReference(3, 3)),
        (ClassReference(3, 7), ClassReference(3, 2))
    ]
    
    for exchange_class, parent_class in exchange_pairs:
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                
                if exchange_assignment and parent_assignment:
                    if exchange_assignment.subject.name in ["自立", "日生", "作業"]:
                        if parent_assignment.subject.name not in ["数", "英", "算"]:
                            exchange_violations.append({
                                'time_slot': time_slot,
                                'exchange_class': exchange_class,
                                'parent_class': parent_class,
                                'parent_subject': parent_assignment.subject.name
                            })
    
    if exchange_violations:
        logger.warning(f"\n残っている交流学級違反: {len(exchange_violations)}件")
        for v in exchange_violations:
            logger.warning(f"  {v['time_slot']} {v['exchange_class'].full_name}(自立) ← " +
                          f"{v['parent_class'].full_name}({v['parent_subject']})")
    else:
        logger.info("✓ 交流学級の自立活動違反はすべて解決されました")
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    schedule_repo.save_schedule(schedule, str(path_manager.output_dir / "output.csv"))
    logger.info("✓ output.csvを更新しました")
    
    # 最終確認
    logger.info("\n=== 最終確認 ===")
    
    # 2年2組の月曜日
    logger.info("\n2年2組の月曜日:")
    mon_subjects = {}
    for period in range(1, 7):
        assignment = schedule.get_assignment(TimeSlot("月", period), ClassReference(2, 2))
        if assignment and assignment.subject.name not in ["欠", "YT", "道", "学総", "総", "行"]:
            subject_name = assignment.subject.name
            mon_subjects[subject_name] = mon_subjects.get(subject_name, 0) + 1
            logger.info(f"  {period}限: {subject_name}")
    
    # 3年3組の金曜日
    logger.info("\n3年3組の金曜日:")
    for period in range(1, 7):
        assignment = schedule.get_assignment(TimeSlot("金", period), ClassReference(3, 3))
        if assignment:
            logger.info(f"  {period}限: {assignment.subject.name}")
    
    # 3年3組と3年6組の金曜5限
    parent_assignment = schedule.get_assignment(TimeSlot("金", 5), ClassReference(3, 3))
    exchange_assignment = schedule.get_assignment(TimeSlot("金", 5), ClassReference(3, 6))
    
    if parent_assignment and exchange_assignment:
        if exchange_assignment.subject.name in ["自立", "日生", "作業"]:
            status = "✓" if parent_assignment.subject.name in ["数", "英", "算"] else "✗"
            logger.info(f"\n金曜5限: 3年6組(自立) ← 3年3組({parent_assignment.subject.name}) {status}")


if __name__ == "__main__":
    main()