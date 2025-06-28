"""家庭科教師制約

全クラスの家庭科は金子み先生のみが担当するという制約
"""
from typing import List, Optional
from .base import Constraint, ConstraintPriority, ConstraintType, ConstraintResult, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
import logging


class HomeEconomicsTeacherConstraint(Constraint):
    """家庭科教師制約
    
    全クラス（1-1〜3-3、1-5〜3-5）の家庭科は金子み先生のみが担当可能
    """
    
    def __init__(self):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="家庭科教師制約",
            description="全クラスの家庭科は金子み先生のみが担当"
        )
        self.logger = logging.getLogger(__name__)
        
        # 家庭科を担当できる唯一の教師
        self.HOME_ECONOMICS_TEACHER = "金子み"
        self.HOME_ECONOMICS_SUBJECT = "家"
    
    def check_before_assignment(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """配置前チェック: 家庭科の教師が金子み先生かどうか確認"""
        # 家庭科以外の科目は常に許可
        if assignment.subject.name != self.HOME_ECONOMICS_SUBJECT:
            return True
        
        # 家庭科の場合、教師が金子み先生であることを確認
        if assignment.teacher and assignment.teacher.name != self.HOME_ECONOMICS_TEACHER:
            self.logger.warning(
                f"家庭科教師制約違反: {assignment.class_ref}の家庭科を"
                f"{assignment.teacher.name}先生が担当しようとしています"
                f"（金子み先生のみ可能）"
            )
            return False
        
        return True
    
    def check(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: Optional[TimeSlot] = None,
        assignment: Optional[Assignment] = None
    ) -> List[ConstraintViolation]:
        """家庭科の教師が金子み先生であることをチェック"""
        violations = []
        
        if time_slot and assignment:
            # 特定の配置をチェック
            if (assignment.subject.name == self.HOME_ECONOMICS_SUBJECT and 
                assignment.teacher and 
                assignment.teacher.name != self.HOME_ECONOMICS_TEACHER):
                violations.append(ConstraintViolation(
                    description=(
                        f"家庭科教師違反: {assignment.class_ref}の家庭科を"
                        f"{assignment.teacher.name}先生が担当"
                        f"（金子み先生のみ可能）"
                    ),
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="ERROR"
                ))
        else:
            # 全体をチェック
            violations.extend(self._check_all_home_economics(schedule, school))
        
        return violations
    
    def _check_all_home_economics(
        self, 
        schedule: Schedule, 
        school: School
    ) -> List[ConstraintViolation]:
        """全ての家庭科配置をチェック"""
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if (assignment and 
                        assignment.subject.name == self.HOME_ECONOMICS_SUBJECT):
                        
                        # 教師が指定されていない場合
                        if not assignment.teacher:
                            violations.append(ConstraintViolation(
                                description=(
                                    f"家庭科教師未指定: {class_ref}の{time_slot}の"
                                    f"家庭科に教師が割り当てられていません"
                                ),
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            ))
                        # 教師が金子み先生でない場合
                        elif assignment.teacher.name != self.HOME_ECONOMICS_TEACHER:
                            violations.append(ConstraintViolation(
                                description=(
                                    f"家庭科教師違反: {class_ref}の{time_slot}の"
                                    f"家庭科を{assignment.teacher.name}先生が担当"
                                    f"（金子み先生のみ可能）"
                                ),
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            ))
        
        return violations
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """全体の家庭科教師配置を検証"""
        violations = self._check_all_home_economics(schedule, school)
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations,
            message=(
                f"家庭科教師制約: {len(violations)}件の違反" 
                if violations else "家庭科教師制約: 違反なし"
            )
        )