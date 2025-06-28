#!/usr/bin/env python3
"""
3年3組の水曜6校時の空白を埋めるスクリプト
D26×エラーの解決
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.config.path_config import PathConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_wednesday_6th_blank():
    """3年3組の水曜6校時の空白を埋める"""
    
    # パス設定とリポジトリ初期化
    path_config = PathConfig()
    repository = CSVScheduleRepository(path_config.data_dir)
    
    # データ読み込み
    logger.info("スケジュールを読み込み中...")
    school = repository.load_school_data()
    schedule = repository.read_schedule(path_config.output_dir / "output.csv", school)
    
    # 3-3の水曜6校時を確認
    time_slot = TimeSlot("水", 6)
    class_ref = school.get_class_by_name("3年3組")
    
    assignment = schedule.get_assignment(time_slot, class_ref)
    if assignment is not None:
        logger.info(f"3-3の水曜6校時は既に{assignment.subject.name}が配置されています")
        return
    
    logger.info("3-3の水曜6校時は空白です。配置可能な科目を探します...")
    
    # 3-3の必要時間数を確認
    required_hours = school.get_required_hours(class_ref)
    current_hours = {}
    
    # 現在の配置時間数を計算
    for subject in required_hours:
        current_hours[subject.name] = 0
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            ts = TimeSlot(day, period)
            asgn = schedule.get_assignment(ts, class_ref)
            if asgn and asgn.subject.name in current_hours:
                current_hours[asgn.subject.name] += 1
    
    # 不足している科目を確認
    logger.info("\n必要時間数と現在の配置:")
    candidates = []
    for subject_name, required in required_hours.items():
        current = current_hours.get(subject_name, 0)
        shortage = required - current
        logger.info(f"  {subject_name}: 必要{required}時間, 現在{current}時間, 不足{shortage}時間")
        if shortage > 0:
            candidates.append((subject_name, shortage))
    
    # 水曜に既に配置されている科目を確認（1日1コマ制限）
    wednesday_subjects = set()
    for period in range(1, 6):  # 1-5校時
        ts = TimeSlot("水", period)
        asgn = schedule.get_assignment(ts, class_ref)
        if asgn:
            wednesday_subjects.add(asgn.subject.name)
    
    logger.info(f"\n水曜に既に配置されている科目: {wednesday_subjects}")
    
    # 配置可能な科目から選択
    for subject_name, shortage in sorted(candidates, key=lambda x: x[1], reverse=True):
        if subject_name not in wednesday_subjects:
            # この科目を担当できる教師を探す
            subject = school.get_subject_by_name(subject_name)
            if not subject:
                continue
                
            # 教師を探す
            available_teachers = []
            for teacher in school.teachers:
                if teacher.can_teach_subject(subject):
                    # 水曜6校時に空いているか確認
                    available = True
                    for cls in school.get_all_classes():
                        asgn = schedule.get_assignment(time_slot, cls)
                        if asgn and asgn.teacher and asgn.teacher.name == teacher.name:
                            available = False
                            break
                    if available:
                        available_teachers.append(teacher)
            
            if available_teachers:
                # 最初の利用可能な教師を選択
                teacher = available_teachers[0]
                assignment = Assignment(class_ref, subject, teacher)
                schedule.assign(time_slot, assignment)
                logger.info(f"\n✅ 3-3の水曜6校時に{subject_name}を配置しました（担当: {teacher.name}）")
                
                # 保存
                logger.info("\n変更を保存中...")
                repository.write_schedule(schedule, school, path_config.output_dir / "output.csv")
                logger.info("✅ 保存完了")
                return
    
    logger.warning("適切な科目が見つかりませんでした")

if __name__ == "__main__":
    fix_wednesday_6th_blank()