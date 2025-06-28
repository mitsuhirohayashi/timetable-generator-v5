"""評価サービスのインターフェース定義"""
from abc import ABC, abstractmethod
from typing import Tuple

from ..entities.schedule import Schedule
from ..entities.school import School


class IScheduleEvaluator(ABC):
    """スケジュール評価器のインターフェース"""
    
    @abstractmethod
    def evaluate(self, schedule: Schedule, school: School) -> float:
        """スケジュールを評価してスコアを返す
        
        Args:
            schedule: 評価対象のスケジュール
            school: 学校情報
            
        Returns:
            評価スコア（低いほど良い）
        """
        pass
    
    @abstractmethod
    def evaluate_with_details(self, schedule: Schedule, school: School) -> Tuple[float, dict]:
        """スケジュールを評価してスコアと詳細を返す
        
        Args:
            schedule: 評価対象のスケジュール
            school: 学校情報
            
        Returns:
            (評価スコア, 詳細情報の辞書)
        """
        pass