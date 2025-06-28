"""HF会議制約 - 火曜4限の2年生授業を禁止"""
from typing import List
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot


class HFMeetingConstraint(Constraint):
    """HF（ホームフレンド）会議制約 - 火曜4限に2年生の授業配置を禁止"""
    
    def __init__(self):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="HF会議制約",
            description="火曜4限（HF会議）には2年生の授業を配置不可"
        )
        self.hf_time_slot = TimeSlot("火", 4)
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """火曜4限に2年生の授業が配置されていないか検証"""
        violations = []
        
        # 2年生の全クラスをチェック
        for class_ref in school.get_all_classes():
            if class_ref.grade != 2:
                continue
            
            assignment = schedule.get_assignment(self.hf_time_slot, class_ref)
            if assignment:
                # 固定科目（欠、YT等）は許可
                if assignment.subject.name in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]:
                    continue
                
                violation = ConstraintViolation(
                    description=f"HF会議違反: 火曜4限は2年団のHF会議のため、{class_ref}に{assignment.subject.name}を配置不可",
                    time_slot=self.hf_time_slot,
                    assignment=assignment,
                    severity="ERROR"
                )
                violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"HF会議制約チェック完了: {len(violations)}件の違反"
        )
    
    def check_before_assignment(self, schedule: Schedule, school: School, 
                                time_slot: TimeSlot, assignment) -> bool:
        """配置前チェック: 火曜4限の2年生授業を防ぐ"""
        # 火曜4限でない場合は許可
        if time_slot != self.hf_time_slot:
            return True
        
        # 2年生でない場合は許可
        if assignment.class_ref.grade != 2:
            return True
        
        # 固定科目は許可
        if assignment.subject.name in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]:
            return True
        
        # それ以外は禁止
        return False