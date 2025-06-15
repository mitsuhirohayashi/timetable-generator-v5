"""5組ユニットエンティティ - 1年5組、2年5組、3年5組を1つのユニットとして管理"""
import logging
from typing import Dict, List, Optional, Tuple, Callable
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment
from ..value_objects.special_support_hours import (
    SpecialSupportHour, SpecialSupportHourMapping
)


class Grade5Unit:
    """5組を1つのユニットとして管理するエンティティ
    
    Args:
        enable_hour_notation (bool): 特別支援時数表記を有効にするか（デフォルト: False）
        detailed_logging (bool): 詳細なロギングを有効にするか（デフォルト: False）
    """
    
    def __init__(self, enable_hour_notation: bool = False, detailed_logging: bool = False):
        # ロガー設定
        self.logger = logging.getLogger(__name__)
        if detailed_logging:
            self.logger.setLevel(logging.DEBUG)
        
        # 基本設定
        self.classes = [
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        ]
        
        # 時間枠ごとの割り当て（3クラス共通）
        self._assignments: Dict[TimeSlot, Assignment] = {}
        
        # ロック状態
        self._locked_slots: set[TimeSlot] = set()
        
        # 教師不在チェック関数（外部から設定可能）
        self._is_teacher_absent_func: Optional[Callable] = None
        
        # 拡張機能の設定
        self.enable_hour_notation = enable_hour_notation
        self.detailed_logging = detailed_logging
        
        # 拡張機能が有効な場合の追加設定
        if self.enable_hour_notation:
            # 特別支援時数表記の割り当て
            self._hour_assignments: Dict[TimeSlot, SpecialSupportHour] = {}
            # 特別支援時数マッピング
            self._hour_mapping = SpecialSupportHourMapping()
            # 特別支援教師の情報
            self._special_teachers = {}
    
    def set_teacher_absence_checker(self, checker_func: Callable[[str, str, int], bool]) -> None:
        """教師不在チェック関数を設定"""
        self._is_teacher_absent_func = checker_func
    
    def assign(self, time_slot: TimeSlot, subject: Subject, teacher: Optional[Teacher] = None) -> None:
        """5組全体に同じ教科・教員を割り当て"""
        # ロックされている場合はエラー
        if self.is_locked(time_slot):
            raise ValueError(f"Cell is locked: {time_slot} - Grade 5 Unit")
        
        # 拡張機能：特別な教科のチェック
        if self.enable_hour_notation:
            if subject.name in ["音", "理", "社", "英", "数"] and not teacher:
                # これらの教科で教師が未指定の場合、時数コードを確認
                hour_code = self._hour_mapping.get_hour_code(
                    subject.name, time_slot.day, time_slot.period
                )
                # 5支の場合でも特定の教師は割り当てない
        
        # 教師不在チェック（関数が設定されている場合）
        if teacher and self._is_teacher_absent_func:
            if self._is_teacher_absent_func(teacher.name, time_slot.day, time_slot.period):
                if self.detailed_logging:
                    self.logger.warning(
                        f"教師不在のため5組割り当てをスキップ: {time_slot} "
                        f"{subject}({teacher.name}先生)")
                return
        
        # 拡張機能：時数コードを取得して記録
        if self.enable_hour_notation:
            teacher_name = teacher.name if teacher else None
            hour_code = self._hour_mapping.get_hour_code(
                subject.name, time_slot.day, time_slot.period, teacher_name
            )
            
            # 特別支援時数として記録
            special_hour = SpecialSupportHour(
                hour_code=hour_code,
                subject_name=subject.name,
                teacher_name=teacher_name
            )
            self._hour_assignments[time_slot] = special_hour
        
        # 通常のAssignment（基本機能）
        assignment = Assignment(self.classes[0], subject, teacher)
        self._assignments[time_slot] = assignment
        
        # ロギング
        if self.detailed_logging:
            if self.enable_hour_notation and hasattr(self, '_hour_assignments'):
                hour_code = self._hour_assignments[time_slot].hour_code
                self.logger.info(
                    f"5組ユニット: {time_slot}に{hour_code}[{subject}]"
                    f"({teacher.name if teacher else '未定'})を割り当て"
                )
            else:
                self.logger.info(
                    f"5組ユニット: {time_slot}に{subject}({teacher})を割り当て"
                )
    
    def remove_assignment(self, time_slot: TimeSlot) -> None:
        """割り当てを削除"""
        if time_slot in self._assignments:
            del self._assignments[time_slot]
        
        # 拡張機能：時数表記も削除
        if self.enable_hour_notation and hasattr(self, '_hour_assignments'):
            if time_slot in self._hour_assignments:
                del self._hour_assignments[time_slot]
        
        if self.detailed_logging:
            self.logger.info(f"5組ユニット: {time_slot}の割り当てを削除")
    
    def get_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[Assignment]:
        """特定クラスの割り当てを取得"""
        if class_ref not in self.classes:
            return None
        
        if time_slot not in self._assignments:
            return None
        
        # 共通の割り当てから、指定クラス用のAssignmentを生成
        common_assignment = self._assignments[time_slot]
        return Assignment(class_ref, common_assignment.subject, common_assignment.teacher)
    
    def get_hour_assignment(self, time_slot: TimeSlot) -> Optional[SpecialSupportHour]:
        """特別支援時数表記を取得（拡張機能）"""
        if self.enable_hour_notation and hasattr(self, '_hour_assignments'):
            return self._hour_assignments.get(time_slot)
        return None
    
    def get_display_text(self, time_slot: TimeSlot) -> str:
        """表示用テキストを取得"""
        # 拡張機能：時数表記を優先
        if self.enable_hour_notation and hasattr(self, '_hour_assignments'):
            hour_assignment = self._hour_assignments.get(time_slot)
            if hour_assignment:
                return hour_assignment.hour_code
        
        # 通常の教科名を返す
        assignment = self._assignments.get(time_slot)
        if assignment:
            return assignment.subject.name
        
        return ""
    
    def get_common_assignment(self, time_slot: TimeSlot) -> Optional[Assignment]:
        """5組共通の割り当てを取得"""
        return self._assignments.get(time_slot)
    
    def lock_slot(self, time_slot: TimeSlot) -> None:
        """時間枠をロック"""
        self._locked_slots.add(time_slot)
    
    def unlock_slot(self, time_slot: TimeSlot) -> None:
        """時間枠のロックを解除"""
        self._locked_slots.discard(time_slot)
    
    def is_locked(self, time_slot: TimeSlot) -> bool:
        """時間枠がロックされているか"""
        return time_slot in self._locked_slots
    
    def get_all_assignments(self) -> List[Tuple[TimeSlot, ClassReference, Assignment]]:
        """全ての割り当てを取得（各クラス分を展開）"""
        assignments = []
        for time_slot, common_assignment in self._assignments.items():
            for class_ref in self.classes:
                assignment = Assignment(class_ref, common_assignment.subject, common_assignment.teacher)
                assignments.append((time_slot, class_ref, assignment))
        return assignments
    
    def get_all_hour_assignments(self) -> List[Tuple[TimeSlot, ClassReference, SpecialSupportHour]]:
        """全ての時数表記割り当てを取得（拡張機能）"""
        if not self.enable_hour_notation or not hasattr(self, '_hour_assignments'):
            return []
        
        assignments = []
        for time_slot, hour_assignment in self._hour_assignments.items():
            for class_ref in self.classes:
                assignments.append((time_slot, class_ref, hour_assignment))
        return assignments
    
    def get_empty_slots(self) -> List[TimeSlot]:
        """空き時間枠を取得"""
        empty_slots = []
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if time_slot not in self._assignments and not self.is_locked(time_slot):
                    empty_slots.append(time_slot)
        return empty_slots
    
    def get_daily_subjects(self, day: str) -> List[Subject]:
        """特定の曜日の教科リストを取得"""
        subjects = []
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            if time_slot in self._assignments:
                subjects.append(self._assignments[time_slot].subject)
        return subjects
    
    def count_subject_hours(self, subject: Subject) -> int:
        """特定教科の週間時数をカウント"""
        count = 0
        for assignment in self._assignments.values():
            if assignment.subject == subject:
                count += 1
        return count
    
    def count_hour_code_occurrences(self, hour_code: str) -> int:
        """特定の時数コードの出現回数をカウント（拡張機能）"""
        if not self.enable_hour_notation or not hasattr(self, '_hour_assignments'):
            return 0
        
        count = 0
        for hour_assignment in self._hour_assignments.values():
            if hour_assignment.hour_code == hour_code:
                count += 1
        return count
    
    def is_valid_assignment(self, time_slot: TimeSlot, subject: Subject) -> bool:
        """割り当てが妥当かチェック"""
        # 特別支援教科は5組共通では実施しない
        if subject.name in ["自立", "日生", "作業", "生単"]:
            return False
        
        # 日内重複チェック
        day_subjects = self.get_daily_subjects(time_slot.day)
        if subject in day_subjects:
            return False
        
        # 拡張機能：時数配置パターンの妥当性チェック
        if self.enable_hour_notation and hasattr(self, '_hour_mapping'):
            hour_code = self._hour_mapping.get_hour_code(
                subject.name, time_slot.day, time_slot.period
            )
            if not self._hour_mapping.is_valid_placement(hour_code, time_slot.day, time_slot.period):
                return False
        
        return True
    
    def optimize_hour_distribution(self) -> None:
        """時数配分を最適化（拡張機能）"""
        if not self.enable_hour_notation or not hasattr(self, '_hour_assignments'):
            return
        
        # 各時数コードの出現回数をチェック
        hour_counts = {}
        for hour_assignment in self._hour_assignments.values():
            code = hour_assignment.hour_code
            hour_counts[code] = hour_counts.get(code, 0) + 1
        
        # 偏りがある場合は調整
        if self.detailed_logging:
            self.logger.info(f"5組時数配分: {hour_counts}")