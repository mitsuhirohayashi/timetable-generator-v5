"""テスト期間保護制約 - 元の科目を保持したまま変更を防ぐ"""
import logging
from typing import List, Dict, Set, Tuple

from .base import Constraint, ConstraintType, ConstraintPriority
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment


class TestPeriodProtectionConstraint(Constraint):
    """テスト期間保護制約
    
    テスト期間中のスロットを保護し、元の科目を保持したまま変更を防ぐ。
    これにより、テスト期間中でも各クラスの通常の時間割が表示される。
    """
    
    def __init__(self, test_periods: List[Tuple[TimeSlot, str]]):
        """初期化
        
        Args:
            test_periods: テスト期間のリスト [(TimeSlot, 説明)]
        """
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="テスト期間保護",
            description="テスト期間中の科目を保護し、変更を防ぐ"
        )
        self.test_periods = test_periods
        self.test_slots: Set[TimeSlot] = {ts for ts, _ in test_periods}
        self.logger = logging.getLogger(__name__)
        
        # テスト期間情報をログ出力
        if self.test_periods:
            self.logger.info(f"テスト期間保護制約を初期化: {len(self.test_periods)}スロット")
            for time_slot, desc in self.test_periods[:3]:  # 最初の3件を表示
                self.logger.debug(f"  - {time_slot}: {desc}")
    
    def is_satisfied(self, schedule: Schedule, school: School) -> bool:
        """制約が満たされているかチェック
        
        テスト期間のスロットがロックされているかを確認する。
        """
        if not self.test_slots:
            return True
        
        for time_slot in self.test_slots:
            # 5組以外の全クラスをチェック
            for class_ref in school.get_all_classes():
                if class_ref.class_number == 5:  # 5組はスキップ
                    continue
                
                # スロットがロックされているか確認
                if not schedule.is_locked(time_slot, class_ref):
                    return False
        
        return True
    
    def get_violations(self, schedule: Schedule, school: School) -> List[Dict]:
        """制約違反を検出
        
        ロックされていないテスト期間スロットを違反として報告。
        """
        violations = []
        
        if not self.test_slots:
            return violations
        
        for time_slot in self.test_slots:
            # 5組以外の全クラスをチェック
            for class_ref in school.get_all_classes():
                if class_ref.class_number == 5:  # 5組はスキップ
                    continue
                
                # スロットがロックされていない場合は違反
                if not schedule.is_locked(time_slot, class_ref):
                    violations.append({
                        'constraint': self.name,
                        'type': self.type.value,
                        'priority': self.priority.value,
                        'time_slot': str(time_slot),
                        'class_ref': str(class_ref),
                        'message': f"{time_slot} {class_ref}のテスト期間スロットが保護されていません"
                    })
        
        return violations
    
    def can_assign(self, schedule: Schedule, time_slot: TimeSlot, 
                   assignment: Assignment, school: School) -> bool:
        """割り当て可能かチェック
        
        テスト期間のスロットへの新規割り当てを防ぐ。
        既存の割り当ての変更も防ぐ。
        """
        # 5組は制限なし
        if assignment.class_ref.class_number == 5:
            return True
        
        # テスト期間でない場合は制限なし
        if time_slot not in self.test_slots:
            return True
        
        # テスト期間の場合、既存の割り当てと同じかチェック
        existing = schedule.get_assignment(time_slot, assignment.class_ref)
        if existing:
            # 既存の割り当てと同じ科目・教師の場合のみ許可
            return (existing.subject == assignment.subject and 
                    existing.teacher == assignment.teacher)
        
        # 新規割り当ては禁止
        return False
    
    def get_affected_slots(self) -> List[TimeSlot]:
        """影響を受けるタイムスロットを返す"""
        return list(self.test_slots)
    
    def validate(self, schedule: Schedule, school: School) -> 'ConstraintResult':
        """スケジュール全体を検証"""
        from ..value_objects.assignment import ConstraintViolation
        from .base import ConstraintResult
        
        violations = []
        violation_dicts = self.get_violations(schedule, school)
        
        for viol_dict in violation_dicts:
            violation = ConstraintViolation(
                constraint_name=self.name,
                constraint_type=self.type,
                priority=self.priority,
                message=viol_dict['message'],
                time_slot=viol_dict['time_slot'],
                class_ref=viol_dict['class_ref']
            )
            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations,
            message=f"{len(violations)}件のテスト期間保護違反" if violations else "OK"
        )