"""スケジュール最適化サービスのインターフェース"""
from abc import ABC, abstractmethod

from ..entities.schedule import Schedule
from ..entities.school import School


class ScheduleOptimizer(ABC):
    """スケジュール最適化サービスの抽象基底クラス"""
    
    @abstractmethod
    def optimize(self, schedule: Schedule, school: School, max_iterations: int = 1000) -> Schedule:
        """スケジュールを最適化する
        
        Args:
            schedule: 最適化対象のスケジュール
            school: 学校情報
            max_iterations: 最大イテレーション数
            
        Returns:
            最適化されたスケジュール
        """
        pass