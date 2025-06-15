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
    TeacherConflictConstraint,
    TeacherAvailabilityConstraint,
    ExchangeClassConstraint,
    DailySubjectDuplicateConstraint,
    StandardHoursConstraint
)
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
from .test_period_exclusion import TestPeriodProtectionConstraint

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
    'TestPeriodProtectionConstraint',
]