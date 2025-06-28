"""制約分類サービス

制約を優先度別に分類する責務を持つ。
"""
from typing import List, Dict
from collections import defaultdict

from ....domain.constraints.base import Constraint, ConstraintPriority


class ConstraintCategorizer:
    """制約を優先度別に分類"""
    
    def __init__(self):
        self.critical_constraints: List[Constraint] = []
        self.high_constraints: List[Constraint] = []
        self.medium_constraints: List[Constraint] = []
        self.low_constraints: List[Constraint] = []
    
    def categorize(self, constraints: List[Constraint]) -> None:
        """制約を優先度別に分類"""
        # 既存の制約をクリア
        self.critical_constraints.clear()
        self.high_constraints.clear()
        self.medium_constraints.clear()
        self.low_constraints.clear()
        
        # 制約を分類
        for constraint in constraints:
            if hasattr(constraint, 'priority'):
                if constraint.priority == ConstraintPriority.CRITICAL:
                    self.critical_constraints.append(constraint)
                elif constraint.priority == ConstraintPriority.HIGH:
                    self.high_constraints.append(constraint)
                elif constraint.priority == ConstraintPriority.MEDIUM:
                    self.medium_constraints.append(constraint)
                else:
                    self.low_constraints.append(constraint)
    
    def get_all_constraints(self) -> List[Constraint]:
        """全ての制約を優先度順に取得"""
        return (self.critical_constraints + 
                self.high_constraints + 
                self.medium_constraints + 
                self.low_constraints)