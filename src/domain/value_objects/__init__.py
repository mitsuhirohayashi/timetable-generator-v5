"""値オブジェクト（Value Objects）

このパッケージは、ドメインモデルで使用される値オブジェクトを定義します。
値オブジェクトは不変で、同値性によって識別されます。
"""

# 基本的な値オブジェクト
from .assignment import Assignment
from .time_slot import TimeSlot, ClassReference, Subject, Teacher
from .weekly_requirement import WeeklyRequirement

# 設定関連
from .subject_config import SubjectConfig, ClassConfig

# バリデーター（統合版）
from .class_validator import ClassValidator
from .subject_validator import SubjectValidator

# 特別支援時数表記（統合版）
from .special_support_hours import (
    SpecialSupportHour,
    Grade5SupportHour,
    SpecialSupportHourMapping,
    # 後方互換性のためのエイリアス
    SpecialSupportHourMappingEnhanced,
    Grade5SupportHourSystem,
)

__all__ = [
    # 基本的な値オブジェクト
    "Assignment",
    "TimeSlot",
    "ClassReference",
    "Subject",
    "Teacher",
    "WeeklyRequirement",
    # 設定関連
    "SubjectConfig",
    "ClassConfig",
    # バリデーター
    "ClassValidator",
    "SubjectValidator",
    # 特別支援時数表記
    "SpecialSupportHour",
    "Grade5SupportHour",
    "SpecialSupportHourMapping",
    "SpecialSupportHourMappingEnhanced",
    "Grade5SupportHourSystem",
]