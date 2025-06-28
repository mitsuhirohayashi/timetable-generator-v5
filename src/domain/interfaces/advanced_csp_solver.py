"""高度なCSPソルバーのインターフェース"""
from abc import ABC, abstractmethod
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment


@dataclass
class Domain:
    """変数のドメイン（可能な値の集合）"""
    time_slot: TimeSlot
    class_ref: ClassReference
    possible_assignments: Set[Tuple[Subject, Teacher]]
    
    def size(self) -> int:
        """ドメインのサイズを返す"""
        return len(self.possible_assignments)
    
    def is_empty(self) -> bool:
        """ドメインが空かどうか"""
        return len(self.possible_assignments) == 0


@dataclass 
class CSPVariable:
    """CSP変数（時間割の1マス）"""
    time_slot: TimeSlot
    class_ref: ClassReference
    domain: Domain
    is_assigned: bool = False
    assignment: Optional[Assignment] = None


class AdvancedCSPSolver(ABC):
    """高度なCSPソルバーの抽象基底クラス"""
    
    @abstractmethod
    def solve(self, school: School, initial_schedule: Optional[Schedule] = None) -> Schedule:
        """CSP問題を解く"""
        pass
    
    @abstractmethod
    def select_unassigned_variable(self, variables: List[CSPVariable]) -> Optional[CSPVariable]:
        """未割当変数を選択（MRVヒューリスティック）"""
        pass
    
    @abstractmethod
    def order_domain_values(self, variable: CSPVariable, school: School, 
                          schedule: Schedule) -> List[Tuple[Subject, Teacher]]:
        """ドメイン値を順序付け（LCVヒューリスティック）"""
        pass
    
    @abstractmethod
    def propagate_constraints(self, variable: CSPVariable, assignment: Assignment,
                            variables: Dict[Tuple[TimeSlot, ClassReference], CSPVariable],
                            school: School) -> bool:
        """制約伝播を実行"""
        pass