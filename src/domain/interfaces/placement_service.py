"""配置サービスのインターフェース定義"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.assignment import Assignment


class IPlacementService(ABC):
    """科目配置サービスのインターフェース"""
    
    @abstractmethod
    def place_assignments(self, schedule: Schedule, school: School, 
                         assignments: List[Assignment]) -> int:
        """割り当てを配置する
        
        Args:
            schedule: 配置先のスケジュール
            school: 学校情報
            assignments: 配置する割り当てのリスト
            
        Returns:
            配置された割り当ての数
        """
        pass


class IJiritsuPlacementService(ABC):
    """自立活動配置サービスのインターフェース"""
    
    @abstractmethod
    def place_jiritsu_activities(self, schedule: Schedule, school: School) -> List[Assignment]:
        """自立活動を配置する
        
        Args:
            schedule: 配置先のスケジュール
            school: 学校情報
            
        Returns:
            配置された自立活動の割り当てリスト
        """
        pass


class IGrade5PlacementService(ABC):
    """5組配置サービスのインターフェース"""
    
    @abstractmethod
    def synchronize_grade5_classes(self, schedule: Schedule, school: School) -> int:
        """5組クラスを同期して配置する
        
        Args:
            schedule: 配置先のスケジュール
            school: 学校情報
            
        Returns:
            配置された割り当ての数
        """
        pass


class ISubjectPlacementService(ABC):
    """一般科目配置サービスのインターフェース"""
    
    @abstractmethod
    def place_remaining_subjects(self, schedule: Schedule, school: School) -> int:
        """残りの科目を配置する
        
        Args:
            schedule: 配置先のスケジュール
            school: 学校情報
            
        Returns:
            配置された割り当ての数
        """
        pass