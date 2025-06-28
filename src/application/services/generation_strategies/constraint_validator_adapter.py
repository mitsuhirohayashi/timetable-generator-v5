"""制約バリデーターアダプター

UnifiedConstraintSystemをConstraintValidatorインターフェースに適合させるアダプターです。
"""
import logging
from typing import Tuple, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ....domain.services.core.unified_constraint_system import UnifiedConstraintSystem, AssignmentContext
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School
    from ....domain.value_objects.time_slot import TimeSlot
    from ....domain.value_objects.assignment import Assignment
    from ....domain.value_objects.constraint_violation import ConstraintViolation


class ConstraintValidatorAdapter:
    """UnifiedConstraintSystemをConstraintValidatorインターフェースに適合させるアダプター"""
    
    def __init__(self, unified_system: 'UnifiedConstraintSystem'):
        self.unified_system = unified_system
        self.logger = logging.getLogger(__name__)
    
    def check_assignment(
        self,
        schedule: 'Schedule',
        school: 'School',
        time_slot: 'TimeSlot',
        assignment: 'Assignment'
    ) -> Tuple[bool, Optional[str]]:
        """配置前の制約チェック
        
        Args:
            schedule: スケジュール
            school: 学校情報
            time_slot: タイムスロット
            assignment: 配置する授業
            
        Returns:
            制約を満たすかどうかとエラーメッセージのタプル
        """
        from ....domain.services.core.unified_constraint_system import AssignmentContext
        
        context = AssignmentContext(
            schedule=schedule,
            school=school,
            time_slot=time_slot,
            assignment=assignment
        )
        
        result, reasons = self.unified_system.check_before_assignment(context)
        
        # タプル(bool, str)を返す
        error_msg = "; ".join(reasons) if reasons else None
        
        # デバッグログ
        if not result and reasons:
            self.logger.debug(
                f"制約違反: {assignment.class_ref} {assignment.subject.name} "
                f"@ {time_slot} - {error_msg}"
            )
        
        return result, error_msg
    
    def can_place_assignment(
        self,
        schedule: 'Schedule',
        school: 'School',
        time_slot: 'TimeSlot',
        assignment: 'Assignment',
        check_level: str = 'normal'
    ) -> Tuple[bool, Optional[str]]:
        """配置可能かチェック（ConstraintValidatorImproved互換用）
        
        Args:
            schedule: スケジュール
            school: 学校情報
            time_slot: タイムスロット
            assignment: 配置する授業
            check_level: チェックレベル（互換性のため、実際には使用しない）
            
        Returns:
            制約を満たすかどうかとエラーメッセージのタプル
        """
        return self.check_assignment(schedule, school, time_slot, assignment)
    
    def validate_all(
        self,
        schedule: 'Schedule',
        school: 'School'
    ) -> List['ConstraintViolation']:
        """スケジュール全体の検証
        
        Args:
            schedule: 検証するスケジュール
            school: 学校情報
            
        Returns:
            制約違反のリスト
        """
        validation_result = self.unified_system.validate_schedule(schedule, school)
        return validation_result.violations
    
    def clear_cache(self) -> None:
        """キャッシュクリア（互換性のため空実装）"""
        pass
    
    def validate_all_constraints(
        self,
        schedule: 'Schedule',
        school: 'School'
    ) -> List['ConstraintViolation']:
        """全ての制約を検証（互換性のため）
        
        Args:
            schedule: 検証するスケジュール
            school: 学校情報
            
        Returns:
            制約違反のリスト
        """
        return self.validate_all(schedule, school)
    
    def validate_schedule(
        self,
        schedule: 'Schedule',
        school: 'School'
    ) -> 'ValidationResult':
        """スケジュール全体の検証（ConstraintValidatorImproved互換用）
        
        Args:
            schedule: 検証するスケジュール
            school: 学校情報
            
        Returns:
            検証結果
        """
        return self.unified_system.validate_schedule(schedule, school)