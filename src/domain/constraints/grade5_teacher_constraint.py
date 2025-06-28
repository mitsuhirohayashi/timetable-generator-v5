"""5組教師制約

5組の各教科は teacher_subject_mapping.csv に従った正しい教師が担当する必要がある
"""
from typing import List, Optional
from .base import Constraint, ConstraintPriority, ConstraintType, ConstraintResult, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
from ..services.grade5_teacher_mapping_service import Grade5TeacherMappingService
import logging


class Grade5TeacherConstraint(Constraint):
    """5組教師制約
    
    5組（1-5、2-5、3-5）の各教科は決められた教師のみが担当可能
    """
    
    def __init__(self):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="5組教師制約",
            description="5組の各教科は指定された教師のみが担当"
        )
        self.logger = logging.getLogger(__name__)
        self.grade5_service = Grade5TeacherMappingService()
        
    def check_before_assignment(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """配置前チェック: 5組の教師が正しいかどうか確認"""
        # 5組以外は常に許可
        if not self.grade5_service.is_grade5_class(str(assignment.class_ref)):
            return True
        
        # 5組の場合、正しい教師かチェック
        if assignment.teacher:
            return self.grade5_service.validate_teacher_assignment(
                str(assignment.class_ref),
                assignment.subject.name,
                assignment.teacher.name
            )
        
        # 教師が未指定の場合は許可（後で適切な教師を割り当てる）
        return True
    
    def check(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: Optional[TimeSlot] = None,
        assignment: Optional[Assignment] = None
    ) -> List[ConstraintViolation]:
        """5組の教師割り当てをチェック"""
        violations = []
        
        if time_slot and assignment:
            # 特定の配置をチェック
            if (self.grade5_service.is_grade5_class(str(assignment.class_ref)) and 
                assignment.teacher and 
                not self.grade5_service.validate_teacher_assignment(
                    str(assignment.class_ref),
                    assignment.subject.name,
                    assignment.teacher.name
                )):
                expected_teacher = self.grade5_service.get_teacher_for_subject(assignment.subject.name)
                violations.append(ConstraintViolation(
                    description=(
                        f"5組教師違反: {assignment.class_ref}の{assignment.subject.name}を"
                        f"{assignment.teacher.name}先生が担当"
                        f"（{expected_teacher}先生が正しい担当）"
                    ),
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="ERROR"
                ))
        else:
            # 全体をチェック
            violations.extend(self._check_all_grade5_teachers(schedule, school))
        
        return violations
    
    def _check_all_grade5_teachers(
        self, 
        schedule: Schedule, 
        school: School
    ) -> List[ConstraintViolation]:
        """全ての5組の教師割り当てをチェック"""
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 5組のみチェック
                    if not self.grade5_service.is_grade5_class(str(class_ref)):
                        continue
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        # 教師が指定されていない場合
                        if not assignment.teacher:
                            violations.append(ConstraintViolation(
                                description=(
                                    f"5組教師未指定: {class_ref}の{time_slot}の"
                                    f"{assignment.subject.name}に教師が割り当てられていません"
                                ),
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            ))
                        # 教師が正しくない場合
                        elif not self.grade5_service.validate_teacher_assignment(
                            str(class_ref),
                            assignment.subject.name,
                            assignment.teacher.name
                        ):
                            expected_teacher = self.grade5_service.get_teacher_for_subject(
                                assignment.subject.name
                            )
                            violations.append(ConstraintViolation(
                                description=(
                                    f"5組教師違反: {class_ref}の{time_slot}の"
                                    f"{assignment.subject.name}を{assignment.teacher.name}先生が担当"
                                    f"（{expected_teacher}先生が正しい担当）"
                                ),
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            ))
        
        return violations
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """全体の5組教師配置を検証"""
        violations = self._check_all_grade5_teachers(schedule, school)
        
        # 5組の教師情報をログ出力（デバッグ用）
        if violations:
            self.grade5_service.log_grade5_teacher_info()
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations,
            message=(
                f"5組教師制約: {len(violations)}件の違反" 
                if violations else "5組教師制約: 違反なし"
            )
        )