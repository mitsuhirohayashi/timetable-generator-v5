"""交流学級完全同期制約

交流学級（6組・7組）と親学級の授業を完全に同期させる制約。
- 自立活動時：親学級は数学か英語
- それ以外：親学級と同じ教科
"""
from .base import HardConstraint, ConstraintResult, ConstraintPriority
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import ConstraintViolation


class ExchangeClassFullSyncConstraint(HardConstraint):
    """交流学級完全同期制約
    
    支援学級（6組・7組）と親学級の授業を同期：
    1. 支援学級が自立活動 → 親学級は数学か英語
    2. 支援学級がそれ以外 → 親学級と同じ教科
    """
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.HIGH,
            name="交流学級完全同期制約",
            description="交流学級と親学級の授業を適切に同期"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック"""
        class_ref = assignment.class_ref
        
        # 交流学級の場合
        if class_ref.is_exchange_class():
            parent_class = class_ref.get_parent_class()
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            
            if assignment.subject.name == "自立":
                # 自立活動の場合、親学級は数学か英語
                if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                    return False
            else:
                # 自立活動以外の場合、親学級と同じ教科
                if parent_assignment and parent_assignment.subject.name != assignment.subject.name:
                    return False
        
        # 親学級の場合（交流学級を持つかチェック）
        else:
            # この親学級に対応する交流学級を取得
            for exchange_class in school.get_all_classes():
                if exchange_class.is_exchange_class():
                    try:
                        if exchange_class.get_parent_class() == class_ref:
                            exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                            
                            if exchange_assignment:
                                if exchange_assignment.subject.name == "自立":
                                    # 交流学級が自立活動なら、親学級は数学か英語
                                    if assignment.subject.name not in ["数", "英"]:
                                        return False
                                else:
                                    # 交流学級が自立活動以外なら、同じ教科
                                    if assignment.subject.name != exchange_assignment.subject.name:
                                        return False
                    except ValueError:
                        # get_parent_class() can raise ValueError if not an exchange class
                        continue
        
        return True
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """全体検証"""
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 交流学級をチェック
                for class_ref in school.get_all_classes():
                    if not class_ref.is_exchange_class():
                        continue
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if not assignment:
                        continue
                    
                    parent_class = class_ref.get_parent_class()
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if assignment.subject.name == "自立":
                        # 自立活動の場合
                        if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                            violation = ConstraintViolation(
                                description=f"交流学級{class_ref}が自立活動中、"
                                          f"親学級{parent_class}は{parent_assignment.subject}を実施"
                                          f"（数学か英語である必要）",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
                    else:
                        # 自立活動以外の場合
                        if parent_assignment and parent_assignment.subject.name != assignment.subject.name:
                            violation = ConstraintViolation(
                                description=f"交流学級{class_ref}({assignment.subject})と"
                                          f"親学級{parent_class}({parent_assignment.subject})の"
                                          f"教科が異なります",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
                        elif not parent_assignment:
                            violation = ConstraintViolation(
                                description=f"交流学級{class_ref}に授業があるが、"
                                          f"親学級{parent_class}に授業が設定されていません",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"交流学級完全同期チェック完了: {len(violations)}件の違反"
        )