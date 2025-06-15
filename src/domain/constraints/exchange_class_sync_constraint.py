"""交流学級同期制約 - 交流学級は自立以外は親学級と同じ教科"""
from typing import Dict, Tuple, Optional
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject
from ..value_objects.assignment import Assignment
from ..value_objects.class_validator import ClassValidator


class ExchangeClassSyncConstraint(Constraint):
    """交流学級同期制約 - 支援学級（交流学級）は自立以外は親学級と同じ教科にする"""
    
    def __init__(self):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="交流学級同期制約",
            description="交流学級は自立以外は親学級と同じ教科を行う"
        )
        # 交流学級と親学級の対応
        validator = ClassValidator()
        self.exchange_parent_map: Dict[ClassReference, ClassReference] = {}
        self.parent_subjects_for_jiritsu = {}
        
        # 設定ファイルから読み込んだマッピングを使用
        for grade in [1, 2, 3]:
            for class_num in [6, 7]:
                parent_info = validator.get_exchange_parent_info(grade, class_num)
                if parent_info:
                    parent_grade, parent_class = parent_info[0]
                    allowed_subjects = list(parent_info[1])
                    exchange_ref = ClassReference(grade, class_num)
                    parent_ref = ClassReference(parent_grade, parent_class)
                    self.exchange_parent_map[exchange_ref] = parent_ref
                    self.parent_subjects_for_jiritsu[exchange_ref] = allowed_subjects
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """交流学級が適切に親学級と同期しているか検証"""
        violations = []
        
        # 各時間枠をチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各交流学級をチェック
                for exchange_class, parent_class in self.exchange_parent_map.items():
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if exchange_assignment:
                        if exchange_assignment.subject.name == "自立":
                            # 交流学級が自立の場合、親学級は数または英でなければならない
                            if parent_assignment:
                                required_subjects = self.parent_subjects_for_jiritsu[exchange_class]
                                if parent_assignment.subject.name not in required_subjects:
                                    violation = ConstraintViolation(
                                        description=f"交流学級自立時制約違反: {exchange_class}が自立の時、{parent_class}は{'/'.join(required_subjects)}であるべきですが、{parent_assignment.subject.name}です",
                                        time_slot=time_slot,
                                        assignment=parent_assignment,
                                        severity="ERROR"
                                    )
                                    violations.append(violation)
                        else:
                            # 交流学級が自立以外の場合、親学級と同じ教科でなければならない
                            if parent_assignment:
                                if exchange_assignment.subject.name != parent_assignment.subject.name:
                                    violation = ConstraintViolation(
                                        description=f"交流学級同期違反: {exchange_class}({exchange_assignment.subject.name})と{parent_class}({parent_assignment.subject.name})の教科が異なります",
                                        time_slot=time_slot,
                                        assignment=exchange_assignment,
                                        severity="ERROR"
                                    )
                                    violations.append(violation)
                            else:
                                violation = ConstraintViolation(
                                    description=f"交流学級同期違反: {exchange_class}に授業がありますが、{parent_class}が空きです",
                                    time_slot=time_slot,
                                    assignment=exchange_assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"交流学級同期チェック完了: {len(violations)}件の違反"
        )