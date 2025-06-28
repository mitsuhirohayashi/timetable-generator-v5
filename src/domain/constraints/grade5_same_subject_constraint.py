"""5組同一教科制約 - 1年5組・2年5組・3年5組は必ず同じ時限に同じ教科を行う"""
from typing import List, Dict
from pathlib import Path
from collections import defaultdict
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference
from ..interfaces.configuration_reader import IConfigurationReader
from ..constants import WEEKDAYS, PERIODS


class Grade5SameSubjectConstraint(Constraint):
    """5組同一教科制約 - 各学年の5組は同じ時限に同じ教科を行う"""
    
    def __init__(self, config_reader: IConfigurationReader = None):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="5組同一教科制約",
            description="1年5組・2年5組・3年5組は必ず同じ時限に同じ教科を行う"
        )
        
        # 依存性注入: 設定リーダーが渡されない場合はDIコンテナから取得
        if config_reader is None:
            from ...infrastructure.di_container import get_configuration_reader
            config_reader = get_configuration_reader()
        
        # 5組のクラスリストを取得
        grade5_class_names = config_reader.get_grade5_classes()
        self.grade5_classes = []
        for class_name in grade5_class_names:
            # "1年5組" を ClassReference(1, 5) に変換
            grade = int(class_name[0])
            class_num = int(class_name[2])
            self.grade5_classes.append(ClassReference(grade, class_num))
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """5組が同じ時限に同じ教科を行っているか検証"""
        violations = []
        
        # 各時間枠をチェック
        for day in WEEKDAYS:
            for period in PERIODS:
                time_slot = TimeSlot(day, period)
                
                # 5組の各クラスの教科を取得
                subjects = {}
                for class_ref in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subjects[class_ref] = assignment.subject.name
                    else:
                        subjects[class_ref] = "空き"
                
                # 全ての5組が同じ教科でない場合は違反
                if len(subjects) > 0:
                    subject_values = list(subjects.values())
                    if not all(s == subject_values[0] for s in subject_values):
                        violation = ConstraintViolation(
                            description=f"5組同一教科違反: {time_slot}に5組の教科が揃っていません - " + 
                                      ", ".join([f"{c}: {s}" for c, s in subjects.items()]),
                            time_slot=time_slot,
                            assignment=None,  # 複数クラスにまたがるため特定の割り当てはない
                            severity="ERROR"
                        )
                        violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"5組同一教科チェック完了: {len(violations)}件の違反"
        )