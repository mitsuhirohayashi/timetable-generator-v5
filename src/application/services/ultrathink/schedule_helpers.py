"""スケジュール操作のヘルパーメソッド集

共通的なスケジュール操作機能を提供するユーティリティクラス。
"""
from typing import List, Optional
import logging

from ....domain.entities import School, Schedule
from ....domain.value_objects.time_slot import TimeSlot, ClassReference as ClassRef, Subject, Teacher
from .metadata_collector import MetadataCollector

logger = logging.getLogger(__name__)


class ScheduleHelpers:
    """スケジュール操作のヘルパーメソッド"""
    
    def __init__(self, metadata: MetadataCollector):
        self.metadata = metadata
    
    def get_class_ref(self, school: School, class_name: str) -> Optional[ClassRef]:
        """クラス名からClassRefを取得"""
        parts = class_name.split('-')
        if len(parts) == 2:
            grade = int(parts[0])
            class_num = int(parts[1])
            for class_ref in school.get_all_classes():
                if class_ref.grade == grade and class_ref.class_number == class_num:
                    return class_ref
        return None
    
    def get_all_time_slots(self) -> List[TimeSlot]:
        """全ての時間スロットを取得"""
        slots = []
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                slots.append(TimeSlot(day=day, period=period))
        return slots
    
    def find_teacher_for_subject(self, school: School, class_ref: ClassRef,
                                subject: str, time_slot: TimeSlot) -> Optional[Teacher]:
        """教科に適した教師を見つける"""
        # まず、クラスと教科に割り当てられた教師を探す
        subject_obj = Subject(subject)
        assigned_teacher = school.get_assigned_teacher(subject_obj, class_ref)
        
        if assigned_teacher:
            # 教師の不在をチェック
            if not self.metadata.is_teacher_absent(
                assigned_teacher.name, time_slot.day, str(time_slot.period)
            ):
                return assigned_teacher
        
        # 割り当てがない場合は、その教科を教えられる教師を探す
        for teacher in school.get_subject_teachers(subject_obj):
            # 教師の不在をチェック
            if not self.metadata.is_teacher_absent(
                teacher.name, time_slot.day, str(time_slot.period)
            ):
                return teacher
        
        return None
    
    def would_create_daily_duplicate(self, schedule: Schedule, class_ref: ClassRef,
                                    time_slot: TimeSlot, subject: str) -> bool:
        """日内重複を作成するかチェック"""
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            check_slot = TimeSlot(day=time_slot.day, period=period)
            assignment = schedule.get_assignment(check_slot, class_ref)
            if assignment and assignment.subject.name == subject:
                return True
        return False
    
    def count_gym_usage(self, schedule: Schedule, time_slot: TimeSlot) -> int:
        """体育館使用数をカウント"""
        count = 0
        # schedule.get_all_assignments()は(TimeSlot, Assignment)のタプルのリストを返す
        for ts, assignment in schedule.get_all_assignments():
            if ts == time_slot and assignment.subject.name == "保":
                # 5組の合同体育は1つとしてカウント
                if assignment.class_ref.class_number == 5:
                    return 1  # 5組が使用している場合は1とする
                count += 1
        return count
    
    def calculate_teacher_load(self, schedule: Schedule, teacher: Teacher,
                              time_slot: TimeSlot) -> float:
        """教師の負荷を計算"""
        # その時間帯の教師の授業数をカウント
        count = 0
        # schedule.get_all_assignments()は(TimeSlot, Assignment)のタプルのリストを返す
        for ts, assignment in schedule.get_all_assignments():
            if ts == time_slot and assignment.teacher == teacher:
                count += 1
        
        # 5組の合同授業は1つとしてカウント
        return min(count, 1.0)