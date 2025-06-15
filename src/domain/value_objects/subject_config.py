"""教科設定のデータクラス"""
from dataclasses import dataclass, field
from typing import Set, Dict, Optional


@dataclass
class SubjectConfig:
    """教科に関する設定を保持するデータクラス"""
    valid_subjects: Set[str] = field(default_factory=set)
    special_needs_subjects: Set[str] = field(default_factory=set)
    fixed_subjects: Set[str] = field(default_factory=set)
    subject_names: Dict[str, str] = field(default_factory=dict)
    default_teachers: Dict[str, str] = field(default_factory=dict)
    gym_subjects: Set[str] = field(default_factory=set)


@dataclass
class ClassConfig:
    """クラスに関する設定を保持するデータクラス"""
    regular_class_numbers: Set[int] = field(default_factory=set)
    special_needs_class_numbers: Set[int] = field(default_factory=set)
    exchange_class_numbers: Set[int] = field(default_factory=set)
    exchange_class_mappings: Dict[tuple[int, int], tuple[tuple[int, int], Set[str]]] = field(default_factory=dict)
    grade5_team_teaching_teachers: Set[str] = field(default_factory=set)