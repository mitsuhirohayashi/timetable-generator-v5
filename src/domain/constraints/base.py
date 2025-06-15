"""制約システムの基盤クラス"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.assignment import ConstraintViolation


class ConstraintType(Enum):
    """制約のタイプ"""
    HARD = "HARD"    # 絶対に守る必要がある制約
    SOFT = "SOFT"    # 可能な限り守りたい制約


class ConstraintPriority(Enum):
    """制約の優先度"""
    CRITICAL = 100   # 最高優先度（システムエラーレベル）
    HIGH = 80        # 高優先度（教員重複など）
    MEDIUM = 60      # 中優先度（標準時数など）
    LOW = 40         # 低優先度（日内重複回避など）
    SUGGESTION = 20  # 提案レベル


@dataclass
class ConstraintResult:
    """制約検証の結果"""
    constraint_name: str
    violations: List['ConstraintViolation']
    message: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0
    
    def __bool__(self) -> bool:
        return self.is_valid


class Constraint(ABC):
    """制約の抽象基底クラス"""
    
    def __init__(self, 
                 constraint_type: ConstraintType,
                 priority: ConstraintPriority,
                 name: str,
                 description: str = ""):
        self.type = constraint_type
        self.priority = priority
        self.name = name
        self.description = description
    
    @abstractmethod
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """制約を検証する"""
        pass
    
    def is_hard_constraint(self) -> bool:
        """ハード制約かどうか判定"""
        return self.type == ConstraintType.HARD
    
    def is_soft_constraint(self) -> bool:
        """ソフト制約かどうか判定"""
        return self.type == ConstraintType.SOFT
    
    def __str__(self) -> str:
        return f"{self.name} ({self.type.value}, Priority: {self.priority.value})"
    
    def __lt__(self, other):
        """優先度による比較（高い優先度が先）"""
        return self.priority.value > other.priority.value


class HardConstraint(Constraint):
    """ハード制約の基底クラス"""
    
    def __init__(self, priority: ConstraintPriority, name: str, description: str = ""):
        super().__init__(ConstraintType.HARD, priority, name, description)


class SoftConstraint(Constraint):
    """ソフト制約の基底クラス"""
    
    def __init__(self, priority: ConstraintPriority, name: str, description: str = ""):
        super().__init__(ConstraintType.SOFT, priority, name, description)


class ConstraintValidator:
    """制約検証器"""
    
    def __init__(self, constraints: List[Constraint]):
        self.constraints = sorted(constraints)  # 優先度順にソート
    
    def check_assignment(self, schedule: Schedule, school: School, time_slot, assignment) -> bool:
        """配置前に全ての制約をチェック"""
        from ..value_objects.time_slot import TimeSlot
        from ..value_objects.assignment import Assignment
        
        # 全ての制約に対してcheckメソッドを呼び出す（存在する場合）
        for constraint in self.constraints:
            if hasattr(constraint, 'check'):
                if not constraint.check(schedule, school, time_slot, assignment):
                    return False
        return True
    
    def validate_all(self, schedule: Schedule, school: School) -> List[ConstraintResult]:
        """全ての制約を検証"""
        results = []
        schedule.clear_violations()  # 既存の違反をクリア
        
        for constraint in self.constraints:
            result = constraint.validate(schedule, school)
            results.append(result)
            
            # 違反をスケジュールに追加
            for violation in result.violations:
                schedule.add_violation(violation)
        
        return results
    
    def validate_hard_constraints_only(self, schedule: Schedule, school: School) -> List[ConstraintResult]:
        """ハード制約のみを検証"""
        hard_constraints = [c for c in self.constraints if c.is_hard_constraint()]
        results = []
        
        for constraint in hard_constraints:
            result = constraint.validate(schedule, school)
            results.append(result)
        
        return results
    
    def has_hard_constraint_violations(self, schedule: Schedule, school: School) -> bool:
        """ハード制約の違反があるかどうか判定"""
        results = self.validate_hard_constraints_only(schedule, school)
        return any(not result.is_valid for result in results)
    
    def get_violation_summary(self, schedule: Schedule, school: School) -> str:
        """制約違反のサマリーを取得"""
        results = self.validate_all(schedule, school)
        
        hard_violations = sum(len(r.violations) for r in results 
                            if r.violations and any(v.severity == "ERROR" for v in r.violations))
        soft_violations = sum(len(r.violations) for r in results 
                            if r.violations and any(v.severity == "WARNING" for v in r.violations))
        
        return f"制約違反: ハード制約 {hard_violations}件, ソフト制約 {soft_violations}件"
    
    def add_constraint(self, constraint: Constraint) -> None:
        """制約を追加"""
        self.constraints.append(constraint)
        self.constraints.sort()  # 優先度順に再ソート
    
    def remove_constraint(self, constraint_name: str) -> None:
        """制約を削除"""
        self.constraints = [c for c in self.constraints if c.name != constraint_name]