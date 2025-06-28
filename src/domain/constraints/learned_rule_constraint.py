"""
学習ルール制約
QandAシステムから学習したルールを制約として適用する
"""

import logging
from typing import TYPE_CHECKING, List
from .base import Constraint, ConstraintViolation, ConstraintPriority

if TYPE_CHECKING:
    from ..entities.schedule import Schedule
    from ..entities.school import School
    from ..value_objects.time_slot import TimeSlot
    from ..value_objects.assignment import Assignment
    from ...application.services.learned_rule_application_service import LearnedRuleApplicationService


class LearnedRuleConstraint(Constraint):
    """QandAシステムから学習したルールに基づく制約"""
    
    def __init__(self, learned_rule_service: 'LearnedRuleApplicationService'):
        super().__init__(
            name="学習ルール制約",
            description="QandAシステムから学習したルールに基づく制約",
            priority=ConstraintPriority.HIGH
        )
        self.learned_rule_service = learned_rule_service
        self.logger = logging.getLogger(__name__)
    
    def check(self, schedule: 'Schedule', school: 'School',
              time_slot: 'TimeSlot', assignment: 'Assignment') -> bool:
        """配置前チェック: 学習ルールに違反しないか確認"""
        return self.check_before_assignment(schedule, school, time_slot, assignment)
    
    def check_before_assignment(self, schedule: 'Schedule', school: 'School',
                               time_slot: 'TimeSlot', assignment: 'Assignment') -> bool:
        """配置前チェック: 学習ルールに違反しないか確認"""
        if not assignment.teacher:
            return True
        
        # 現在の同時刻の割り当てを取得（同じ教師のみ）
        existing_assignments = []
        for class_ref in school.get_all_classes():
            # 自分自身のクラスはスキップ
            if class_ref == assignment.class_ref:
                continue
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing and existing.teacher and existing.teacher.name == assignment.teacher.name:
                existing_assignments.append(existing)
        
        # 学習ルールのデバッグ情報（必要に応じて）
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"\n*** 学習ルール制約チェック @ {time_slot} ***")
            self.logger.debug(f"  チェック対象: {assignment.class_ref.full_name} - {assignment.subject.name} ({assignment.teacher.name}先生)")
            self.logger.debug(f"  既存割り当て数: {len(existing_assignments)}")
            for i, existing in enumerate(existing_assignments):
                self.logger.debug(f"    {i+1}. {existing.class_ref.full_name} - {existing.subject.name}")
        
        # 既存の配置数が上限に達している場合は配置不可
        # 井上先生の場合、max_classes = 1なので、既に1つ配置されていたら追加不可
        for forbidden in self.learned_rule_service.forbidden_assignments:
            forbidden_teacher = forbidden['teacher']
            teacher_matches = (
                forbidden_teacher == assignment.teacher.name or 
                forbidden_teacher + '先生' == assignment.teacher.name or
                forbidden_teacher == assignment.teacher.name.replace('先生', '') or
                forbidden_teacher == assignment.teacher.name.replace('担当', '')
            )
            
            if (teacher_matches and
                forbidden['time_slot'].day == time_slot.day and
                forbidden['time_slot'].period == time_slot.period
            ):
                max_allowed = forbidden['max_classes']
                if len(existing_assignments) >= max_allowed:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"{assignment.teacher.name}先生の{time_slot}配置を拒否: 既に{len(existing_assignments)}クラス配置済み（上限{max_allowed}）")
                    return False
        
        return True
    
    def validate(self, schedule: 'Schedule', school: 'School') -> 'ConstraintResult':
        """スケジュール全体の検証"""
        from .base import ConstraintResult
        violations = self.check_after_assignment(schedule, school)
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations,
            message=f"学習ルール検証完了: {len(violations)}件の違反"
        )
    
    def check_after_assignment(self, schedule: 'Schedule', school: 'School') -> List[ConstraintViolation]:
        """配置後チェック: 全体的な学習ルール違反を検出"""
        violations = []
        
        # 禁止されている配置パターンをチェック
        for forbidden in self.learned_rule_service.forbidden_assignments:
            teacher_name = forbidden['teacher']
            time_slot = forbidden['time_slot']
            max_classes = forbidden['max_classes']
            
            # 該当する時間帯での教師の配置数を数える
            teacher_count = 0
            affected_classes = []
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                    teacher_count += 1
                    affected_classes.append(str(class_ref))
            
            if teacher_count > max_classes:
                violations.append(ConstraintViolation(
                    constraint_name=self.name,
                    description=f"{teacher_name}先生が{time_slot}に{teacher_count}クラス"
                              f"（{', '.join(affected_classes)}）を同時に教えています。"
                              f"学習ルールでは最大{max_classes}クラスまでです。",
                    priority=self.priority,
                    time_slot=time_slot
                ))
        
        return violations
    
    def fix_violation(self, violation: ConstraintViolation, schedule: 'Schedule', 
                     school: 'School') -> bool:
        """違反の修正: 学習ルールに基づいて違反を修正"""
        # ここでは修正は行わず、違反検出のみ
        return False