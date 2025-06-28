"""教師不在制約"""
from typing import Dict, List, Optional, Set
from .base import HardConstraint, ConstraintPriority, ConstraintResult, ConstraintViolation
from ..entities.school import School
from ..entities.schedule import Schedule
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
from ..interfaces.teacher_absence_repository import ITeacherAbsenceRepository
import logging


class TeacherAbsenceConstraint(HardConstraint):
    """教師不在制約
    
    Follow-up.csvで指定された教師の不在情報に基づいて、
    不在時に授業が割り当てられないようにする
    """
    
    def __init__(self, absence_repository: ITeacherAbsenceRepository = None):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教師不在制約",
            description="不在の教師に授業を割り当てない"
        )
        self.logger = logging.getLogger(__name__)
        
        # 依存性注入: リポジトリが渡されない場合はDIコンテナから取得
        if absence_repository is None:
            from ...infrastructure.di_container import get_teacher_absence_repository
            absence_repository = get_teacher_absence_repository()
        
        self.absence_repository = absence_repository
    
    def check(self, schedule: 'Schedule', school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """指定された時間帯に教師が不在でないかチェック"""
        
        # 教師を取得
        teacher = assignment.teacher
        if not teacher:
            return True
        
        # 教師名を取得（Teacher オブジェクトの場合は name 属性を使用）
        teacher_name = teacher.name if hasattr(teacher, 'name') else str(teacher)
        
        # リポジトリを使用して不在チェック
        if self.absence_repository.is_teacher_absent(teacher_name, time_slot):
            self.logger.debug(f"{teacher_name}先生は{time_slot.day}{time_slot.period}限不在のため配置不可")
            return False
        
        return True
    
    def get_unavailable_teachers(self, time_slot: TimeSlot) -> Set[str]:
        """指定された時間帯に不在の教師のセットを返す"""
        return self.absence_repository.get_absent_teachers_at(time_slot)
    
    def is_teacher_available(self, teacher: str, time_slot: TimeSlot) -> bool:
        """指定された時間帯に教師が利用可能かチェック"""
        return not self.absence_repository.is_teacher_absent(teacher, time_slot)
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """スケジュール全体の教師不在制約を検証"""
        violations = []
        
        # 全ての時間枠を生成
        days = ["月", "火", "水", "木", "金"]
        periods = [1, 2, 3, 4, 5, 6]
        
        for day in days:
            for period in periods:
                time_slot = TimeSlot(day, period)
                unavailable_teachers = self.get_unavailable_teachers(time_slot)
                if not unavailable_teachers:
                    continue
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if not assignment or not assignment.subject:
                        continue
                    
                    # 教師を取得
                    teacher = assignment.teacher
                    if not teacher:
                        # 教科から教師を推定
                        teacher = school.get_assigned_teacher(assignment.subject, class_ref)
                    
                    if teacher:
                        teacher_name = teacher.name if hasattr(teacher, 'name') else str(teacher)
                        if teacher_name in unavailable_teachers:
                            violations.append(ConstraintViolation(
                                description=f"{class_ref}の{time_slot}に{teacher_name}先生（不在）が{assignment.subject}を担当",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            ))
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations
        )