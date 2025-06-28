"""時間枠を表す値オブジェクト"""
from dataclasses import dataclass
from typing import Literal
from .subject_validator import SubjectValidator
from .class_validator import ClassValidator
from ...shared.utils.validation_utils import ValidationUtils
from ...shared.mixins.validation_mixin import ValidationError

DayOfWeek = Literal["月", "火", "水", "木", "金"]
Period = Literal[1, 2, 3, 4, 5, 6]


@dataclass(frozen=True)
class TimeSlot:
    """時間枠（曜日・校時）を表す不変オブジェクト"""
    
    day: DayOfWeek
    period: Period
    
    def __post_init__(self):
        # Handle full day names like "月曜" by stripping the 曜 suffix
        day = self.day
        if isinstance(day, str) and day.endswith("曜"):
            day = day[:-1]
            # Use object.__setattr__ since dataclass is frozen
            object.__setattr__(self, 'day', day)
        
        if not ValidationUtils.is_valid_day(self.day):
            raise ValidationError(f"Invalid day: {self.day}")
        if not ValidationUtils.is_valid_period(self.period):
            raise ValidationError(f"Invalid period: {self.period}")
    
    def __str__(self) -> str:
        return f"{self.day}曜{self.period}校時"
    
    def __format__(self, format_spec: str) -> str:
        """f-string内での表示をサポート"""
        return str(self)
    
    def is_same_day(self, other: 'TimeSlot') -> bool:
        """同じ曜日かどうか判定"""
        return self.day == other.day
    
    def is_same_period(self, other: 'TimeSlot') -> bool:
        """同じ校時かどうか判定"""
        return self.period == other.period
    
    def is_afternoon(self) -> bool:
        """午後の時間帯かどうか判定"""
        return self.period >= 4
    
    def __format__(self, format_spec: str) -> str:
        """フォーマット指定子に対応"""
        return str(self)


@dataclass(frozen=True)
class Subject:
    """教科を表す値オブジェクト"""
    
    name: str
    
    def __post_init__(self):
        # 科目名の正規化
        normalized = ValidationUtils.normalize_subject_name(self.name)
        if normalized != self.name:
            object.__setattr__(self, 'name', normalized)
        
        validator = SubjectValidator()
        if not validator.is_valid_subject(self.name):
            raise ValidationError(f"Invalid subject: {self.name}")
    
    def __str__(self) -> str:
        return self.name
    
    def __format__(self, format_spec: str) -> str:
        """f-string内での表示をサポート"""
        return str(self)
    
    def is_special_needs_subject(self) -> bool:
        """特別支援教科かどうか判定"""
        validator = SubjectValidator()
        return validator.is_special_needs_subject(self.name)
    
    def is_valid_for_class(self, class_ref: 'ClassReference') -> bool:
        """指定されたクラスで有効な教科かどうか判定"""
        # 特別支援教科は通常学級では使用不可
        if self.is_special_needs_subject():
            if class_ref.is_regular_class():
                return False
        
        # 自立活動は5組・6組・7組のみ
        if self.name == "自立":
            return class_ref.is_special_needs_class() or class_ref.is_exchange_class()
        
        # 日生・生単・作業は5組のみ
        if self.name in ["日生", "生単", "作業"]:
            return class_ref.is_special_needs_class()
        
        return True
    
    def is_protected_subject(self) -> bool:
        """固定教科（変更禁止）かどうか判定"""
        validator = SubjectValidator()
        return validator.is_fixed_subject(self.name)
    
    def __format__(self, format_spec: str) -> str:
        """フォーマット指定子に対応"""
        return str(self)


@dataclass(frozen=True)
class Teacher:
    """教員を表す値オブジェクト"""
    
    name: str
    
    def __post_init__(self):
        if not ValidationUtils.validate_teacher_name(self.name):
            raise ValidationError(f"Invalid teacher name: {self.name}")
    
    def __str__(self) -> str:
        return self.name
    
    def __format__(self, format_spec: str) -> str:
        """f-string内での表示をサポート"""
        return str(self)


@dataclass(frozen=True)
class ClassReference:
    """クラス参照を表す値オブジェクト"""
    
    grade: int
    class_number: int
    
    def __post_init__(self):
        if not ValidationUtils.is_valid_class_reference(self.grade, self.class_number):
            raise ValidationError(f"Invalid class reference: {self.grade}年{self.class_number}組")
    
    @property
    def full_name(self) -> str:
        """完全なクラス名を返す"""
        return f"{self.grade}年{self.class_number}組"
    
    def __str__(self) -> str:
        return self.full_name
    
    def __format__(self, format_spec: str) -> str:
        """f-string内での表示をサポート"""
        return str(self)
    
    def is_regular_class(self) -> bool:
        """通常学級かどうか判定"""
        validator = ClassValidator()
        return validator.is_regular_class(self.class_number)
    
    def is_special_needs_class(self) -> bool:
        """特別支援学級かどうか判定"""
        validator = ClassValidator()
        return validator.is_special_needs_class(self.class_number)
    
    def is_exchange_class(self) -> bool:
        """交流学級かどうか判定"""
        validator = ClassValidator()
        return validator.is_exchange_class(self.class_number)
    
    def get_parent_class(self) -> 'ClassReference':
        """交流学級の親学級を取得"""
        if not self.is_exchange_class():
            raise ValidationError(f"{self.full_name} is not an exchange class")
        
        # 交流学級の親学級マッピング
        validator = ClassValidator()
        parent_info = validator.get_exchange_parent_info(self.grade, self.class_number)
        if parent_info is None:
            raise ValidationError(f"Parent class not found for {self.full_name}")
        parent_grade, parent_class = parent_info[0]
        return ClassReference(parent_grade, parent_class)