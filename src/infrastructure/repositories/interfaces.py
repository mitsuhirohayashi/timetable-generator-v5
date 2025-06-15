"""リポジトリインターフェース定義"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pathlib import Path

from ...domain.models.timetable import Timetable, TimeSlot, ClassReference, Subject, Teacher


class TimetableRepository(ABC):
    """時間割リポジトリインターフェース"""
    
    @abstractmethod
    def save_timetable(self, timetable: Timetable, suffix: str = "") -> Path:
        """時間割を保存"""
        pass
    
    @abstractmethod
    def load_timetable(self, path: str) -> Timetable:
        """時間割を読み込み"""
        pass
    
    @abstractmethod
    def load_latest_timetable(self) -> Timetable:
        """最新の時間割を読み込み"""
        pass
    
    @abstractmethod
    def load_input_timetable(self) -> Timetable:
        """入力（希望）時間割を読み込み"""
        pass
    
    @abstractmethod
    def export_to_csv(self, timetable: Timetable) -> str:
        """CSV形式でエクスポート"""
        pass
    
    @abstractmethod
    def export_to_excel(self, timetable: Timetable) -> str:
        """Excel形式でエクスポート"""
        pass
    
    @abstractmethod
    def export_to_json(self, timetable: Timetable) -> str:
        """JSON形式でエクスポート"""
        pass
    
    @abstractmethod
    def list_timetables(self) -> List[Dict[str, Any]]:
        """保存された時間割のリストを取得"""
        pass


class SchoolDataRepository(ABC):
    """学校データリポジトリインターフェース"""
    
    @abstractmethod
    def load_school_data(self) -> Dict[str, Any]:
        """学校データを読み込み"""
        pass
    
    @abstractmethod
    def get_all_classes(self) -> List[ClassReference]:
        """すべてのクラスを取得"""
        pass
    
    @abstractmethod
    def get_all_teachers(self) -> List[Teacher]:
        """すべての教員を取得"""
        pass
    
    @abstractmethod
    def get_all_subjects(self) -> List[Subject]:
        """すべての教科を取得"""
        pass
    
    @abstractmethod
    def get_teacher_for_subject(self, class_ref: ClassReference, subject: Subject) -> Optional[Teacher]:
        """教科の担当教員を取得"""
        pass
    
    @abstractmethod
    def get_standard_hours(self, class_ref: ClassReference, subject: Subject) -> float:
        """標準授業時数を取得"""
        pass
    
    @abstractmethod
    def get_required_subjects(self, class_ref: ClassReference) -> List[Subject]:
        """必要な教科リストを取得"""
        pass
    
    @abstractmethod
    def get_teacher_constraints(self, teacher: Teacher) -> Dict[str, Any]:
        """教員の制約を取得"""
        pass
    
    @abstractmethod
    def get_class_constraints(self, class_ref: ClassReference) -> Dict[str, Any]:
        """クラスの制約を取得"""
        pass


class ConfigRepository(ABC):
    """設定リポジトリインターフェース"""
    
    @abstractmethod
    def load_config(self) -> Dict[str, Any]:
        """設定を読み込み"""
        pass
    
    @abstractmethod
    def save_config(self, config: Dict[str, Any]) -> None:
        """設定を保存"""
        pass
    
    @abstractmethod
    def get_constraint_priorities(self) -> Dict[str, str]:
        """制約の優先度設定を取得"""
        pass
    
    @abstractmethod
    def get_fixed_periods(self) -> List[Dict[str, Any]]:
        """固定時限の設定を取得"""
        pass
    
    @abstractmethod
    def get_forbidden_placements(self) -> List[Dict[str, Any]]:
        """配置禁止の設定を取得"""
        pass
    
    @abstractmethod
    def get_meeting_schedules(self) -> List[Dict[str, Any]]:
        """会議スケジュールを取得"""
        pass
    
    @abstractmethod
    def get_exchange_class_mappings(self) -> Dict[ClassReference, ClassReference]:
        """交流学級のマッピングを取得"""
        pass
    
    @abstractmethod
    def get_system_constants(self) -> Dict[str, Any]:
        """システム定数を取得"""
        pass


class TeacherAbsenceRepository(ABC):
    """教員不在情報リポジトリインターフェース"""
    
    @abstractmethod
    def load_absences(self) -> List[Dict[str, Any]]:
        """不在情報を読み込み"""
        pass
    
    @abstractmethod
    def is_teacher_absent(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教員が不在かチェック"""
        pass
    
    @abstractmethod
    def get_absence_reason(self, teacher: Teacher, time_slot: TimeSlot) -> Optional[str]:
        """不在理由を取得"""
        pass
    
    @abstractmethod
    def add_absence(self, teacher: Teacher, time_slot: TimeSlot, reason: str) -> None:
        """不在情報を追加"""
        pass
    
    @abstractmethod
    def remove_absence(self, teacher: Teacher, time_slot: TimeSlot) -> None:
        """不在情報を削除"""
        pass


class ConstraintRepository(ABC):
    """制約リポジトリインターフェース"""
    
    @abstractmethod
    def load_constraints(self) -> List[Dict[str, Any]]:
        """制約を読み込み"""
        pass
    
    @abstractmethod
    def save_constraint(self, constraint: Dict[str, Any]) -> None:
        """制約を保存"""
        pass
    
    @abstractmethod
    def get_constraint_by_type(self, constraint_type: str) -> Optional[Dict[str, Any]]:
        """タイプ別に制約を取得"""
        pass
    
    @abstractmethod
    def get_active_constraints(self) -> List[Dict[str, Any]]:
        """有効な制約を取得"""
        pass
    
    @abstractmethod
    def enable_constraint(self, constraint_id: str) -> None:
        """制約を有効化"""
        pass
    
    @abstractmethod
    def disable_constraint(self, constraint_id: str) -> None:
        """制約を無効化"""
        pass