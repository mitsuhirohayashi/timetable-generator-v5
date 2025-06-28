"""割り当てを表す値オブジェクト"""
from dataclasses import dataclass
from typing import Optional

from .time_slot import ClassReference, Subject, Teacher
from ...shared.mixins.validation_mixin import ValidationError


@dataclass(frozen=True)
class Assignment:
    """時間割の1つの割り当て（クラス・教科・教員）を表す不変オブジェクト"""
    
    class_ref: ClassReference
    subject: Subject
    teacher: Optional[Teacher] = None
    
    def __str__(self) -> str:
        teacher_str = f"({self.teacher})" if self.teacher else ""
        return f"{self.class_ref}: {self.subject}{teacher_str}"
    
    def has_teacher(self) -> bool:
        """教員が割り当てられているかどうか"""
        return self.teacher is not None
    
    def is_same_subject(self, other: 'Assignment') -> bool:
        """同じ教科かどうか判定"""
        return self.subject == other.subject
    
    def is_same_teacher(self, other: 'Assignment') -> bool:
        """同じ教員かどうか判定"""
        return self.teacher == other.teacher and self.teacher is not None
    
    def involves_teacher(self, teacher: Teacher) -> bool:
        """指定された教員が関与しているかどうか"""
        return self.teacher == teacher


@dataclass(frozen=True)
class ConstraintViolation:
    """制約違反を表す値オブジェクト"""
    
    description: str
    time_slot: 'TimeSlot'
    assignment: Assignment
    severity: str = "ERROR"  # ERROR, WARNING, INFO
    
    # 以下は互換性のための追加フィールド（無視される）
    constraint_name: str = None
    message: str = None
    class_ref: 'ClassReference' = None
    related_data: dict = None
    
    def __post_init__(self):
        # messageが設定されていてdescriptionが空の場合、messageをdescriptionとして使用
        if self.message and not self.description:
            object.__setattr__(self, 'description', self.message)
    
    def __str__(self) -> str:
        return f"[{self.severity}] {self.time_slot}: {self.description}"


@dataclass(frozen=True)
class StandardHours:
    """標準時数を表す値オブジェクト"""
    
    class_ref: ClassReference
    subject: Subject
    hours_per_week: float
    
    def __post_init__(self):
        if self.hours_per_week < 0:
            raise ValidationError("Hours per week cannot be negative")
    
    def __str__(self) -> str:
        return f"{self.class_ref} {self.subject}: {self.hours_per_week}時間/週"