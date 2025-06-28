"""交流学級同期制約（リファクタリング版）

ExchangeClassServiceを使用して交流学級ロジックを一元化
"""
from typing import Dict, Tuple, Optional
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference
from ..value_objects.assignment import Assignment
from ..services.synchronizers.exchange_class_service import ExchangeClassService


class ExchangeClassSyncConstraintRefactored(Constraint):
    """交流学級同期制約（リファクタリング版）
    
    ExchangeClassServiceに委譲することで、交流学級関連のロジックを統一
    """
    
    def __init__(self, check_mode='normal'):
        """
        Args:
            check_mode: 'normal' - 通常のチェック（自立活動時は親学級の制約をチェック）
                       'full' - 完全同期チェック（保健体育も含めて全て同期）
        """
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="交流学級同期制約",
            description="交流学級は自立以外は親学級と同じ教科を行う"
        )
        self.check_mode = check_mode
        self.exchange_service = ExchangeClassService()
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """交流学級が適切に親学級と同期しているか検証"""
        violations = []
        
        # ExchangeClassServiceから違反を取得
        service_violations = self.exchange_service.get_exchange_violations(schedule)
        
        # サービスの違反情報をConstraintViolationに変換
        for violation_info in service_violations:
            time_slot = violation_info['time_slot']
            exchange_class = violation_info['exchange_class']
            
            # 該当する割り当てを取得
            assignment = schedule.get_assignment(time_slot, exchange_class)
            
            # ConstraintViolationオブジェクトを作成
            violation = ConstraintViolation(
                description=violation_info['message'],
                time_slot=time_slot,
                assignment=assignment,
                severity="ERROR"
            )
            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"交流学級同期チェック完了: {len(violations)}件の違反"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """
        指定された時間枠への割り当てが交流学級同期制約に違反しないかチェック
        
        ExchangeClassServiceのロジックを使用
        """
        class_ref = assignment.class_ref
        subject = assignment.subject
        
        # 交流学級の場合
        if self.exchange_service.is_exchange_class(class_ref):
            return self.exchange_service.can_place_subject_for_exchange_class(
                schedule, time_slot, class_ref, subject
            )
        
        # 親学級の場合
        if self.exchange_service.is_parent_class(class_ref):
            return self.exchange_service.can_place_subject_for_parent_class(
                schedule, time_slot, class_ref, subject
            )
        
        # 交流学級でも親学級でもない場合は制約なし
        return True


# Alias for backward compatibility
ExchangeClassSyncConstraint = ExchangeClassSyncConstraintRefactored