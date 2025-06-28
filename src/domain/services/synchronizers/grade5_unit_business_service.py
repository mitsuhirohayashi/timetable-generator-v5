"""5組ユニットビジネスサービス - 5組に関するビジネスロジック"""
from typing import List, Optional, Callable, Dict, Tuple
import logging
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.grade5_unit_data import Grade5UnitData
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...value_objects.assignment import Assignment
from ...value_objects.special_support_hours import (
    SpecialSupportHour, SpecialSupportHourMapping
)


class Grade5UnitBusinessService(LoggingMixin):
    """5組ユニットに関するビジネスロジックを提供するサービス"""
    
    def __init__(self, enable_hour_notation: bool = False):
        super().__init__()
        self.enable_hour_notation = enable_hour_notation
        
        # 特別支援時数マッピング（拡張機能用）
        if enable_hour_notation:
            self._hour_mapping = SpecialSupportHourMapping()
        else:
            self._hour_mapping = None
        
        # 特別支援教科のセット
        self._special_support_subjects = {"自立", "日生", "作業", "生単"}
    
    def can_assign(self, data: Grade5UnitData, time_slot: TimeSlot,
                  subject: Subject, teacher: Optional[Teacher] = None,
                  teacher_absence_checker: Optional[Callable] = None) -> bool:
        """割り当てが可能かどうかを判定"""
        # ロックチェック
        if data.is_locked(time_slot):
            return False
        
        # 特別支援教科は5組共通では実施しない
        if subject.name in self._special_support_subjects:
            return False
        
        # 教師不在チェック
        if teacher and teacher_absence_checker:
            if teacher_absence_checker(teacher.name, time_slot.day, time_slot.period):
                self.logger.debug(
                    f"教師不在のため割り当て不可: {time_slot} {teacher.name}"
                )
                return False
        
        # 日内重複チェック
        if self._would_cause_daily_duplicate(data, time_slot, subject):
            return False
        
        return True
    
    def create_assignment_with_hour_notation(self, data: Grade5UnitData,
                                           time_slot: TimeSlot,
                                           subject: Subject,
                                           teacher: Optional[Teacher] = None) -> None:
        """時数表記を含む割り当てを作成"""
        # 基本の割り当て
        assignment = Assignment(data.classes[0], subject, teacher)
        data.set_assignment(time_slot, assignment)
        
        # 時数表記の処理
        if self.enable_hour_notation and self._hour_mapping:
            teacher_name = teacher.name if teacher else None
            hour_code = self._hour_mapping.get_hour_code(
                subject.name, time_slot.day, time_slot.period, teacher_name
            )
            
            special_hour = SpecialSupportHour(
                hour_code=hour_code,
                subject_name=subject.name,
                teacher_name=teacher_name
            )
            data.set_hour_assignment(time_slot, special_hour)
    
    def get_display_text(self, data: Grade5UnitData, time_slot: TimeSlot) -> str:
        """表示用テキストを取得"""
        # 時数表記を優先
        if self.enable_hour_notation:
            hour_assignment = data.get_hour_assignment(time_slot)
            if hour_assignment:
                return hour_assignment.hour_code
        
        # 通常の教科名
        assignment = data.get_assignment(time_slot)
        if assignment:
            return assignment.subject.name
        
        return ""
    
    def get_assignment_for_class(self, data: Grade5UnitData,
                               time_slot: TimeSlot,
                               class_ref: ClassReference) -> Optional[Assignment]:
        """特定クラス用の割り当てを生成"""
        if class_ref not in data.classes:
            return None
        
        common_assignment = data.get_assignment(time_slot)
        if not common_assignment:
            return None
        
        # クラス別のAssignmentを生成
        return Assignment(
            class_ref,
            common_assignment.subject,
            common_assignment.teacher
        )
    
    def get_all_assignments_expanded(self, data: Grade5UnitData) -> List[Tuple[TimeSlot, ClassReference, Assignment]]:
        """全ての割り当てを各クラス分に展開"""
        assignments = []
        for time_slot, common_assignment in data.assignments.items():
            for class_ref in data.classes:
                assignment = Assignment(
                    class_ref,
                    common_assignment.subject,
                    common_assignment.teacher
                )
                assignments.append((time_slot, class_ref, assignment))
        return assignments
    
    def get_empty_slots(self, data: Grade5UnitData) -> List[TimeSlot]:
        """空き時間枠を取得"""
        empty_slots = []
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if (not data.get_assignment(time_slot) and 
                    not data.is_locked(time_slot)):
                    empty_slots.append(time_slot)
        return empty_slots
    
    def get_daily_subjects(self, data: Grade5UnitData, day: str) -> List[Subject]:
        """特定の曜日の教科リストを取得"""
        subjects = []
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = data.get_assignment(time_slot)
            if assignment:
                subjects.append(assignment.subject)
        return subjects
    
    def count_subject_hours(self, data: Grade5UnitData, subject: Subject) -> int:
        """特定教科の週間時数をカウント"""
        count = 0
        for assignment in data.assignments.values():
            if assignment.subject == subject:
                count += 1
        return count
    
    def count_hour_code_occurrences(self, data: Grade5UnitData, hour_code: str) -> int:
        """特定の時数コードの出現回数をカウント"""
        if not self.enable_hour_notation:
            return 0
        
        count = 0
        for hour_assignment in data.hour_assignments.values():
            if hour_assignment.hour_code == hour_code:
                count += 1
        return count
    
    def optimize_hour_distribution(self, data: Grade5UnitData) -> Dict[str, int]:
        """時数配分の最適化情報を取得"""
        if not self.enable_hour_notation:
            return {}
        
        # 各時数コードの出現回数を集計
        hour_counts = {}
        for hour_assignment in data.hour_assignments.values():
            code = hour_assignment.hour_code
            hour_counts[code] = hour_counts.get(code, 0) + 1
        
        return hour_counts
    
    def _would_cause_daily_duplicate(self, data: Grade5UnitData,
                                   time_slot: TimeSlot,
                                   subject: Subject) -> bool:
        """日内重複を引き起こすかどうかを判定"""
        day_subjects = self.get_daily_subjects(data, time_slot.day)
        return subject in day_subjects
    
    def validate_hour_placement(self, time_slot: TimeSlot, subject: Subject) -> bool:
        """時数配置の妥当性を検証"""
        if not self.enable_hour_notation or not self._hour_mapping:
            return True
        
        hour_code = self._hour_mapping.get_hour_code(
            subject.name, time_slot.day, time_slot.period
        )
        return self._hour_mapping.is_valid_placement(
            hour_code, time_slot.day, time_slot.period
        )