"""制約パッケージ"""

from .base import (
    Constraint,
    ConstraintResult,
    ConstraintType,
    ConstraintPriority,
    ConstraintViolation,
    ConstraintValidator,
    HardConstraint,
    SoftConstraint
)
from .basic_constraints import (
    TeacherAvailabilityConstraint,
    StandardHoursConstraint
)
from .teacher_conflict_constraint import TeacherConflictConstraint
from .exchange_class_sync_constraint import ExchangeClassSyncConstraint as ExchangeClassConstraint
from .daily_duplicate_constraint import DailyDuplicateConstraint as DailySubjectDuplicateConstraint
from .subject_validity_constraint import (
    SubjectValidityConstraint,
    SpecialNeedsDuplicateConstraint
)
from .fixed_subject_constraint import FixedSubjectConstraint
from .fixed_subject_lock_constraint import FixedSubjectLockConstraint
from .placement_forbidden_constraint import PlacementForbiddenConstraint
from .monday_sixth_period_constraint import MondaySixthPeriodConstraint
from .grade5_same_subject_constraint import Grade5SameSubjectConstraint
from .exchange_class_sync_constraint import ExchangeClassSyncConstraint
from .part_time_teacher_constraint import PartTimeTeacherConstraint
from .meeting_lock_constraint import MeetingLockConstraint
from .tuesday_pe_constraint import TuesdayPEMultipleConstraint
from .cell_forbidden_subject_constraint import CellForbiddenSubjectConstraint
from .teacher_absence_constraint import TeacherAbsenceConstraint
from .grade5_test_exclusion_constraint import Grade5TestExclusionConstraint

__all__ = [
    # Base
    'Constraint',
    'ConstraintResult',
    'ConstraintType',
    'ConstraintPriority',
    'ConstraintViolation',
    'ConstraintValidator',
    'HardConstraint',
    'SoftConstraint',
    # Basic
    'TeacherConflictConstraint',
    'TeacherAvailabilityConstraint',
    'ExchangeClassConstraint',
    'DailySubjectDuplicateConstraint',
    'StandardHoursConstraint',
    # Subject validity
    'SubjectValidityConstraint',
    'SpecialNeedsDuplicateConstraint',
    # Other constraints
    'FixedSubjectConstraint',
    'FixedSubjectLockConstraint',
    'PlacementForbiddenConstraint',
    'MondaySixthPeriodConstraint',
    'Grade5SameSubjectConstraint',
    'ExchangeClassSyncConstraint',
    'PartTimeTeacherConstraint',
    'MeetingLockConstraint',
    'TuesdayPEMultipleConstraint',
    'CellForbiddenSubjectConstraint',
    'TeacherAbsenceConstraint',
    'Grade5TestExclusionConstraint',
]