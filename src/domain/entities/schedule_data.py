"""スケジュールデータ - 純粋なデータ保持クラス"""
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

from ..value_objects.time_slot import TimeSlot, ClassReference
from ..value_objects.assignment import Assignment


@dataclass
class ScheduleData:
    """時間割の純粋なデータを保持するクラス
    
    ビジネスロジックを含まず、データの保存・取得のみを行う
    """
    # 時間割の割り当て: TimeSlot -> ClassReference -> Assignment
    assignments: Dict[TimeSlot, Dict[ClassReference, Assignment]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    
    # ロックされたセル
    locked_cells: Set[Tuple[TimeSlot, ClassReference]] = field(
        default_factory=set
    )
    
    # 基本的なデータ操作メソッド
    def set_assignment(self, time_slot: TimeSlot, class_ref: ClassReference, 
                      assignment: Assignment) -> None:
        """割り当てを設定（単純な保存）"""
        self.assignments[time_slot][class_ref] = assignment
    
    def get_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[Assignment]:
        """割り当てを取得"""
        return self.assignments[time_slot].get(class_ref)
    
    def remove_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """割り当てを削除"""
        if time_slot in self.assignments and class_ref in self.assignments[time_slot]:
            del self.assignments[time_slot][class_ref]
    
    def set_locked(self, time_slot: TimeSlot, class_ref: ClassReference, locked: bool) -> None:
        """ロック状態を設定"""
        if locked:
            self.locked_cells.add((time_slot, class_ref))
        else:
            self.locked_cells.discard((time_slot, class_ref))
    
    def is_locked(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """ロック状態を取得"""
        return (time_slot, class_ref) in self.locked_cells
    
    def get_all_assignments(self) -> List[Tuple[TimeSlot, ClassReference, Assignment]]:
        """全ての割り当てを取得"""
        result = []
        for time_slot, class_assignments in self.assignments.items():
            for class_ref, assignment in class_assignments.items():
                result.append((time_slot, class_ref, assignment))
        return result
    
    def get_assignments_by_time_slot(self, time_slot: TimeSlot) -> Dict[ClassReference, Assignment]:
        """指定時間枠の全割り当てを取得"""
        return dict(self.assignments[time_slot])
    
    def get_assignments_by_class(self, class_ref: ClassReference) -> List[Tuple[TimeSlot, Assignment]]:
        """指定クラスの全割り当てを取得"""
        result = []
        for time_slot, class_assignments in self.assignments.items():
            if class_ref in class_assignments:
                result.append((time_slot, class_assignments[class_ref]))
        return result
    
    def clone(self) -> 'ScheduleData':
        """データの複製を作成"""
        new_data = ScheduleData()
        # 深いコピー
        for time_slot, class_assignments in self.assignments.items():
            new_data.assignments[time_slot] = dict(class_assignments)
        new_data.locked_cells = self.locked_cells.copy()
        return new_data