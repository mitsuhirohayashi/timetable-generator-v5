"""最適化サービスのインターフェース定義"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional

from ..entities.schedule import Schedule
from ..entities.school import School


class IOptimizationService(ABC):
    """スケジュール最適化サービスのインターフェース"""
    
    @abstractmethod
    def optimize(self, schedule: Schedule, school: School, 
                iterations: int = 100) -> Tuple[Schedule, float]:
        """スケジュールを最適化する
        
        Args:
            schedule: 最適化対象のスケジュール
            school: 学校情報
            iterations: 最適化の反復回数
            
        Returns:
            (最適化されたスケジュール, 最終スコア)
        """
        pass


class ILocalSearchOptimizer(ABC):
    """局所探索最適化のインターフェース"""
    
    @abstractmethod
    def optimize_local(self, schedule: Schedule, school: School, 
                      max_iterations: int = 100) -> Schedule:
        """局所探索による最適化
        
        Args:
            schedule: 最適化対象のスケジュール  
            school: 学校情報
            max_iterations: 最大反復回数
            
        Returns:
            最適化されたスケジュール
        """
        pass


class IConstraintSpecificOptimizer(ABC):
    """制約特化型最適化のインターフェース"""
    
    @abstractmethod
    def optimize_gym_usage(self, schedule: Schedule, school: School) -> int:
        """体育館使用制約を最適化
        
        Returns:
            解決された違反数
        """
        pass
    
    @abstractmethod
    def optimize_daily_duplicates(self, schedule: Schedule, school: School) -> int:
        """日内重複制約を最適化
        
        Returns:
            解決された違反数
        """
        pass