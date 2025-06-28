"""リポジトリインターフェース定義

Clean Architectureの依存性逆転の原則に従い、
ドメイン層でインターフェースを定義し、インフラ層で実装する。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher


class IScheduleRepository(ABC):
    """スケジュールリポジトリのインターフェース"""
    
    @abstractmethod
    def load(self, filename: str, school: Optional[School] = None) -> Schedule:
        """スケジュールを読み込む"""
        pass
    
    @abstractmethod
    def save(self, schedule: Schedule, filename: str) -> None:
        """スケジュールを保存する"""
        pass
    
    @abstractmethod
    def get_forbidden_cells(self) -> Dict[Tuple[TimeSlot, ClassReference], Set[str]]:
        """配置禁止セルを取得"""
        pass


class ISchoolRepository(ABC):
    """学校データリポジトリのインターフェース"""
    
    @abstractmethod
    def load_school_data(self, base_timetable_file: str = "config/base_timetable.csv") -> School:
        """学校データを読み込む"""
        pass
    
    @abstractmethod
    def load_standard_hours(self, filename: str = "base_timetable.csv") -> Dict[tuple[ClassReference, Subject], float]:
        """標準時数データを読み込む"""
        pass


class ITeacherScheduleRepository(ABC):
    """教師スケジュールリポジトリのインターフェース"""
    
    @abstractmethod
    def save_teacher_schedule(self, schedule: Schedule, school: School, filename: str = "teacher_schedule.csv") -> None:
        """教師別時間割を保存"""
        pass


class ITeacherMappingRepository(ABC):
    """教師マッピングリポジトリのインターフェース"""
    
    @abstractmethod
    def load_teacher_mapping(self, filename: str = "teacher_subject_mapping.csv") -> Dict[str, List[Tuple[Subject, List[ClassReference]]]]:
        """教師マッピングを読み込む"""
        pass
    
    @abstractmethod
    def get_teacher_for_subject_class(self, mapping: Dict, subject: Subject, class_ref: ClassReference) -> Optional[Teacher]:
        """指定された教科・クラスの担当教員を取得"""
        pass
    
    @abstractmethod
    def get_all_teachers_for_subject_class(self, mapping: Dict, subject: Subject, class_ref: ClassReference) -> List[Teacher]:
        """指定された教科・クラスの全ての担当教員を取得"""
        pass
    
    @abstractmethod
    def get_permanent_absences(self) -> Dict[str, List[Tuple[str, str]]]:
        """恒久的な教師の休み情報を取得"""
        pass


class ITeacherAbsenceRepository(ABC):
    """教師不在情報リポジトリのインターフェース"""
    
    @abstractmethod
    def load_teacher_absences(self, filename: str = "Follow-up.csv") -> None:
        """教師の不在情報を読み込む"""
        pass
    
    @abstractmethod
    def is_teacher_absent(self, teacher_name: str, day: str, period: int) -> bool:
        """指定された時間に教師が不在かどうか"""
        pass
    
    @abstractmethod
    def get_test_periods(self) -> Dict[str, List[Tuple[str, int]]]:
        """テスト期間情報を取得"""
        pass