"""5組ユニットデータ - 純粋なデータ保持クラス"""
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment
from ..value_objects.special_support_hours import SpecialSupportHour


@dataclass
class Grade5UnitData:
    """5組ユニットの純粋なデータを保持するクラス
    
    1年5組、2年5組、3年5組の共通データを管理
    """
    # 5組のクラス一覧
    classes: list[ClassReference] = field(default_factory=lambda: [
        ClassReference(1, 5),
        ClassReference(2, 5),
        ClassReference(3, 5)
    ])
    
    # 時間枠ごとの共通割り当て
    assignments: Dict[TimeSlot, Assignment] = field(default_factory=dict)
    
    # ロックされた時間枠
    locked_slots: Set[TimeSlot] = field(default_factory=set)
    
    # 特別支援時数表記（拡張機能用）
    hour_assignments: Dict[TimeSlot, SpecialSupportHour] = field(default_factory=dict)
    
    # 基本的なデータ操作メソッド
    def set_assignment(self, time_slot: TimeSlot, assignment: Assignment) -> None:
        """割り当てを設定"""
        self.assignments[time_slot] = assignment
    
    def get_assignment(self, time_slot: TimeSlot) -> Optional[Assignment]:
        """割り当てを取得"""
        return self.assignments.get(time_slot)
    
    def remove_assignment(self, time_slot: TimeSlot) -> None:
        """割り当てを削除"""
        if time_slot in self.assignments:
            del self.assignments[time_slot]
    
    def set_hour_assignment(self, time_slot: TimeSlot, hour: SpecialSupportHour) -> None:
        """特別支援時数表記を設定"""
        self.hour_assignments[time_slot] = hour
    
    def get_hour_assignment(self, time_slot: TimeSlot) -> Optional[SpecialSupportHour]:
        """特別支援時数表記を取得"""
        return self.hour_assignments.get(time_slot)
    
    def remove_hour_assignment(self, time_slot: TimeSlot) -> None:
        """特別支援時数表記を削除"""
        if time_slot in self.hour_assignments:
            del self.hour_assignments[time_slot]
    
    def set_locked(self, time_slot: TimeSlot, locked: bool) -> None:
        """ロック状態を設定"""
        if locked:
            self.locked_slots.add(time_slot)
        else:
            self.locked_slots.discard(time_slot)
    
    def is_locked(self, time_slot: TimeSlot) -> bool:
        """ロック状態を取得"""
        return time_slot in self.locked_slots
    
    def get_all_time_slots(self) -> Set[TimeSlot]:
        """全ての使用中の時間枠を取得"""
        return set(self.assignments.keys())
    
    def clone(self) -> 'Grade5UnitData':
        """データの複製を作成"""
        new_data = Grade5UnitData()
        new_data.classes = self.classes.copy()
        new_data.assignments = self.assignments.copy()
        new_data.locked_slots = self.locked_slots.copy()
        new_data.hour_assignments = self.hour_assignments.copy()
        return new_data