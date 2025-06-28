
"""シンプルで確実な時間割生成アルゴリズム"""
import logging
from typing import Optional, List
from collections import defaultdict

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, Teacher, Subject
from src.domain.value_objects.assignment import Assignment

class SimpleGenerator:
    """シンプルさを重視した、ステップ・バイ・ステップの時間割ジェネレーター"""

    def __init__(self, school: School, initial_schedule: Schedule):
        self.logger = logging.getLogger(__name__)
        self.school = school
        self.schedule = initial_schedule.clone()  # 元のスケジュールを汚さないようにコピー
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "行", "テスト"}

    def generate(self) -> Schedule:
        """時間割の生成を実行する"""
        self.logger.info("=== SimpleGeneratorによる時間割生成を開始します ===")

        # ステップ1: 固定授業の配置とロック（初期スケジュールから）
        self._place_and_lock_fixed_assignments()

        # ステップ2: 主要教科の配置
        self._place_subjects_by_priority([
            "国", "数", "英", "理", "社"
        ])

        # ステップ3: 技能教科の配置
        self._place_subjects_by_priority([
            "保", "音", "美", "技", "家"
        ])

        self.logger.info("=== SimpleGeneratorによる時間割生成が完了しました ===")
        return self.schedule

    def _place_and_lock_fixed_assignments(self):
        """初期スケジュールに含まれる固定授業をロックする"""
        self.logger.info("ステップ1: 固定授業の配置とロック")
        locked_count = 0
        for time_slot, assignment in self.schedule.get_all_assignments():
            if assignment.subject.name in self.fixed_subjects:
                self.schedule.lock_cell(time_slot, assignment.class_ref)
                locked_count += 1
        self.logger.info(f"  -> {locked_count}件の固定授業をロックしました。")

    def _place_subjects_by_priority(self, subjects: List[str]):
        """指定された優先順位で教科を配置する"""
        self.logger.info(f"ステップ: {', '.join(subjects)}の配置")
        
        all_time_slots = [TimeSlot(day, p) for day in ["月", "火", "水", "木", "金"] for p in range(1, 7)]

        for class_ref in self.school.get_all_classes():
            for subject_name in subjects:
                subject = Subject(subject_name)
                required_hours = self.school.get_standard_hours(class_ref, subject)
                if not required_hours:
                    continue

                current_hours = self.schedule.count_subject_hours(class_ref, subject)
                needed_hours = int(required_hours - current_hours)

                for _ in range(needed_hours):
                    teacher = self.school.get_assigned_teacher(subject, class_ref)
                    if not teacher:
                        self.logger.warning(f"{class_ref}の{subject_name}に担当教師が割り当てられていません。")
                        continue

                    # 最適な空きスロットを探して配置
                    for time_slot in all_time_slots:
                        if self._is_slot_available(time_slot, class_ref, teacher, subject_name):
                            assignment = Assignment(class_ref, subject, teacher)
                            self.schedule.assign(time_slot, assignment)
                            break # 次のコマへ

    def _is_slot_available(self, time_slot: TimeSlot, class_ref, teacher: Teacher, subject_name: str) -> bool:
        """指定されたスロットが利用可能かチェックする"""
        # 1. クラスが空いているか
        if self.schedule.get_assignment(time_slot, class_ref) is not None:
            return False

        # 2. 教師が空いているか
        if not self.schedule.is_teacher_available(time_slot, teacher):
            return False

        # 3. 日内重複がないか
        daily_subjects = self.schedule.get_daily_subjects(class_ref, time_slot.day)
        if subject_name in [s.name for s in daily_subjects]:
            return False

        return True
