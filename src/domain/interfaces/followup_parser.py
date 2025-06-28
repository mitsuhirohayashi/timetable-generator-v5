"""フォローアップ情報の解析インターフェース"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any
from datetime import date
from ..value_objects import TimeSlot


class TestPeriodInfo:
    """テスト期間情報"""
    def __init__(self, start_date: date, end_date: date, description: str = ""):
        self.start_date = start_date
        self.end_date = end_date
        self.description = description


class IFollowUpParser(ABC):
    """Follow-up情報を解析するインターフェース"""
    
    @abstractmethod
    def parse_teacher_absences(self) -> Dict[str, List[TimeSlot]]:
        """教師の不在情報を解析
        
        Returns:
            Dict[str, List[TimeSlot]]: 教師名をキー、不在時間のリストを値とする辞書
        """
        pass
    
    @abstractmethod
    def parse_test_periods(self) -> List[TestPeriodInfo]:
        """テスト期間情報を解析
        
        Returns:
            List[TestPeriodInfo]: テスト期間情報のリスト
        """
        pass
    
    @abstractmethod
    def parse_meeting_changes(self) -> Dict[str, Dict[str, Any]]:
        """会議時間の変更情報を解析
        
        Returns:
            Dict[str, Dict[str, Any]]: 会議名をキー、変更情報を値とする辞書
        """
        pass
    
    @abstractmethod
    def is_test_period(self, target_date: date) -> bool:
        """指定された日付がテスト期間かどうかを判定
        
        Args:
            target_date: 判定する日付
            
        Returns:
            bool: テスト期間の場合True
        """
        pass
    
    @abstractmethod
    def get_special_instructions(self) -> List[str]:
        """特別な指示やコメントを取得
        
        Returns:
            List[str]: 指示・コメントのリスト
        """
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """Follow-up情報を再読み込み"""
        pass