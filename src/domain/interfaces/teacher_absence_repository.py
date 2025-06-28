"""教師不在情報のリポジトリインターフェース"""

from abc import ABC, abstractmethod
from typing import Dict, List, Set, Optional
from ..value_objects import TimeSlot


class ITeacherAbsenceRepository(ABC):
    """教師の不在情報を管理するリポジトリのインターフェース"""
    
    @abstractmethod
    def get_absences(self) -> Dict[str, List[TimeSlot]]:
        """すべての教師の不在情報を取得
        
        Returns:
            Dict[str, List[TimeSlot]]: 教師名をキー、不在時間のリストを値とする辞書
        """
        pass
    
    @abstractmethod
    def is_teacher_absent(self, teacher_name: str, time_slot: TimeSlot) -> bool:
        """指定された教師が指定された時間に不在かどうかを判定
        
        Args:
            teacher_name: 教師名
            time_slot: 時間枠
            
        Returns:
            bool: 不在の場合True
        """
        pass
    
    @abstractmethod
    def get_absent_teachers_at(self, time_slot: TimeSlot) -> Set[str]:
        """指定された時間に不在の教師のセットを取得
        
        Args:
            time_slot: 時間枠
            
        Returns:
            Set[str]: 不在教師のセット
        """
        pass
    
    @abstractmethod
    def get_teacher_absence_slots(self, teacher_name: str) -> List[TimeSlot]:
        """指定された教師の不在時間のリストを取得
        
        Args:
            teacher_name: 教師名
            
        Returns:
            List[TimeSlot]: 不在時間のリスト
        """
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """不在情報を再読み込み"""
        pass