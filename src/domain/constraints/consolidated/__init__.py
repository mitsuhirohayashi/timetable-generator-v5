"""統合制約パッケージ

従来の20以上の制約クラスを6つの統合制約に集約
"""

from .base import (
    # 基底クラス
    ConsolidatedConstraint,
    ConfigurableConstraint,
    CompositeConstraint,
    
    # 設定クラス
    ConstraintConfig,
    ValidationContext,
    ConstraintResult,
    
    # 列挙型
    ConstraintType,
    ConstraintPriority,
    ProtectionLevel,
    
    # バリデーター
    ConstraintValidator
)

from .protected_slots import ProtectedSlotConstraint
from .teacher_scheduling import TeacherSchedulingConstraint
from .class_synchronization import ClassSynchronizationConstraint
from .resource_usage import ResourceUsageConstraint
from .scheduling_rules import SchedulingRuleConstraint
from .validation import SubjectValidationConstraint

__all__ = [
    # Base classes
    'ConsolidatedConstraint',
    'ConfigurableConstraint',
    'CompositeConstraint',
    'ConstraintConfig',
    'ValidationContext',
    'ConstraintResult',
    'ConstraintType',
    'ConstraintPriority',
    'ProtectionLevel',
    'ConstraintValidator',
    
    # Consolidated constraints
    'ProtectedSlotConstraint',
    'TeacherSchedulingConstraint',
    'ClassSynchronizationConstraint',
    'ResourceUsageConstraint',
    'SchedulingRuleConstraint',
    'SubjectValidationConstraint',
]