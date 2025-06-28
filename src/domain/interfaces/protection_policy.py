"""保護ポリシーのインターフェース定義"""
from abc import ABC, abstractmethod
from typing import Optional

from ..entities.schedule import Schedule
from ..value_objects.time_slot import TimeSlot
from ..value_objects.time_slot import ClassReference
from ..value_objects.assignment import Assignment


class IProtectionPolicy(ABC):
    """保護ポリシーの基底インターフェース"""
    
    @abstractmethod
    def can_modify_slot(self, schedule: Schedule, time_slot: TimeSlot, 
                       class_ref: ClassReference, 
                       new_assignment: Optional[Assignment]) -> bool:
        """指定されたスロットが変更可能かチェック
        
        Args:
            schedule: 現在のスケジュール
            time_slot: 時間枠
            class_ref: クラス参照
            new_assignment: 新しい割り当て（削除の場合はNone）
            
        Returns:
            変更可能な場合True
        """
        pass


class IFixedSubjectProtectionPolicy(IProtectionPolicy):
    """固定科目保護ポリシーのインターフェース"""
    
    @abstractmethod
    def is_fixed_subject(self, subject_name: str) -> bool:
        """指定された科目が固定科目かチェック
        
        Args:
            subject_name: 科目名
            
        Returns:
            固定科目の場合True
        """
        pass


class ITestPeriodProtectionPolicy(IProtectionPolicy):
    """テスト期間保護ポリシーのインターフェース"""
    
    @abstractmethod
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定された時間枠がテスト期間かチェック
        
        Args:
            time_slot: 時間枠
            
        Returns:
            テスト期間の場合True
        """
        pass