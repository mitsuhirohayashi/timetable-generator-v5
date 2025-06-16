"""テスト期間除外制約

テスト期間中の教科変更を禁止する制約です。
"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference
from ..value_objects.assignment import Assignment
from .base import Constraint, ConstraintViolation


class TestPeriodExclusionConstraint(Constraint):
    """テスト期間除外制約
    
    テスト期間として指定されたスロットの教科を保護し、
    変更を禁止します。
    """
    
    def __init__(self, test_periods: Dict[Tuple[str, int], str]):
        """初期化
        
        Args:
            test_periods: テスト期間の情報
                         {(曜日, 校時): "説明"} の形式
        """
        super().__init__(
            name="テスト期間除外制約",
            description="テスト期間中の教科変更を禁止"
        )
        self.test_periods = test_periods
        self.logger = logging.getLogger(__name__)
        
        # テスト期間のスロットをセットに変換（高速検索用）
        self.test_slots: Set[Tuple[str, int]] = set(test_periods.keys())
    
    def check(self, schedule: Schedule, school: School, 
              time_slot: Optional[TimeSlot] = None,
              assignment: Optional[Assignment] = None) -> List[ConstraintViolation]:
        """制約をチェック
        
        テスト期間のスロットに配置しようとしている場合、
        既存の割り当てと異なる場合は違反とする。
        """
        violations = []
        
        # 特定のスロットと割り当てが指定されている場合
        if time_slot and assignment:
            # テスト期間かチェック
            if (time_slot.day, time_slot.period) in self.test_slots:
                # 既存の割り当てを取得
                existing = schedule.get_assignment(time_slot, assignment.class_ref)
                
                # 既存の割り当てがあり、教科が異なる場合は違反
                if existing and existing.subject != assignment.subject:
                    violation = ConstraintViolation(
                        constraint_name=self.name,
                        description=(
                            f"テスト期間違反: {time_slot}の{assignment.class_ref}は"
                            f"テスト期間のため{existing.subject.name}から"
                            f"{assignment.subject.name}への変更不可"
                        ),
                        time_slot=time_slot,
                        class_ref=assignment.class_ref,
                        subject=assignment.subject,
                        teacher=assignment.teacher
                    )
                    violations.append(violation)
        
        # 全体チェックの場合
        else:
            # この制約は配置時のチェックのみ行う
            pass
        
        return violations
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたスロットがテスト期間かどうか判定"""
        return (time_slot.day, time_slot.period) in self.test_slots
    
    def get_test_period_description(self, time_slot: TimeSlot) -> Optional[str]:
        """テスト期間の説明を取得"""
        return self.test_periods.get((time_slot.day, time_slot.period))