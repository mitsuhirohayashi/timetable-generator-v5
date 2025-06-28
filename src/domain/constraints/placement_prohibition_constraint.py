"""配置禁止制約（非保・非数・非理など）"""

from typing import Dict, List, Optional, Set
import logging

from src.domain.constraints.base import BaseConstraint, ConstraintPriority, ConstraintViolation
from src.domain.entities import Schedule, TimeSlot
from src.domain.value_objects import Assignment, ClassReference, Subject, Teacher

logger = logging.getLogger(__name__)


class PlacementProhibitionConstraint(BaseConstraint):
    """特定の教科を配置してはいけない制約
    
    「非保」「非数」「非理」などの表記に対応し、
    指定された教科を特定のスロットに配置することを禁止する。
    """
    
    def __init__(self):
        super().__init__(
            name="配置禁止制約",
            priority=ConstraintPriority.CRITICAL
        )
        self.prohibited_subjects: Dict[str, Dict[TimeSlot, Set[str]]] = {}
        
    def add_prohibition(self, class_ref: ClassReference, time_slot: TimeSlot, prohibited_subject: str):
        """配置禁止を追加する
        
        Args:
            class_ref: クラス
            time_slot: 時間枠
            prohibited_subject: 禁止する教科名
        """
        class_name = str(class_ref)
        if class_name not in self.prohibited_subjects:
            self.prohibited_subjects[class_name] = {}
        
        if time_slot not in self.prohibited_subjects[class_name]:
            self.prohibited_subjects[class_name][time_slot] = set()
            
        self.prohibited_subjects[class_name][time_slot].add(prohibited_subject)
        logger.debug(f"配置禁止追加: {class_name} {time_slot} に {prohibited_subject} を配置禁止")
        
    def check(self, schedule: Schedule, assignment: Optional[Assignment] = None) -> List[ConstraintViolation]:
        """配置禁止制約をチェック"""
        violations = []
        
        if assignment:
            # 単一の割り当てをチェック
            violations.extend(self._check_single_assignment(schedule, assignment))
        else:
            # スケジュール全体をチェック
            for slot, assign in schedule.assignments.items():
                if assign:
                    violations.extend(self._check_single_assignment(schedule, assign))
                    
        return violations
        
    def _check_single_assignment(
        self, 
        schedule: Schedule, 
        assignment: Assignment
    ) -> List[ConstraintViolation]:
        """単一の割り当てをチェック"""
        violations = []
        
        class_name = str(assignment.class_ref)
        time_slot = assignment.time_slot
        subject_name = str(assignment.subject)
        
        # 配置禁止がある場合
        if class_name in self.prohibited_subjects:
            if time_slot in self.prohibited_subjects[class_name]:
                prohibited = self.prohibited_subjects[class_name][time_slot]
                
                if subject_name in prohibited:
                    violation = ConstraintViolation(
                        constraint=self,
                        assignments=[assignment],
                        message=f"{class_name}の{time_slot}に{subject_name}は配置禁止です"
                    )
                    violations.append(violation)
                    
        return violations
        
    def can_place(
        self, 
        schedule: Schedule, 
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject,
        teacher: Optional[Teacher] = None
    ) -> bool:
        """配置可能かチェック"""
        class_name = str(class_ref)
        subject_name = str(subject)
        
        # 配置禁止チェック
        if class_name in self.prohibited_subjects:
            if time_slot in self.prohibited_subjects[class_name]:
                prohibited = self.prohibited_subjects[class_name][time_slot]
                if subject_name in prohibited:
                    logger.debug(f"配置禁止: {class_name} {time_slot} に {subject_name} は配置できません")
                    return False
                    
        return True
        
    def get_prohibited_subjects(
        self, 
        class_ref: ClassReference, 
        time_slot: TimeSlot
    ) -> Set[str]:
        """特定のクラス・時間枠で禁止されている教科を取得"""
        class_name = str(class_ref)
        
        if class_name in self.prohibited_subjects:
            if time_slot in self.prohibited_subjects[class_name]:
                return self.prohibited_subjects[class_name][time_slot].copy()
                
        return set()