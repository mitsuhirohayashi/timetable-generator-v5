"""スケジュール評価のインターフェース"""
from abc import ABC, abstractmethod
from typing import List, Dict
from dataclasses import dataclass

from ...entities.schedule import Schedule
from ...entities.school import School
from .jiritsu_placement_service import JiritsuRequirement


@dataclass
class EvaluationBreakdown:
    """評価の内訳"""
    jiritsu_violations: int
    constraint_violations: int
    teacher_load_variance: float
    total_score: float
    details: Dict[str, float]


class ScheduleEvaluator(ABC):
    """スケジュール評価のインターフェース
    
    責務:
    - 自立活動制約違反の評価
    - その他制約違反の評価
    - 教員負荷バランスの評価
    """
    
    @abstractmethod
    def evaluate(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement]) -> float:
        """スケジュールの品質を評価
        
        Args:
            schedule: スケジュール
            school: 学校情報
            jiritsu_requirements: 自立活動要件のリスト
            
        Returns:
            評価スコア（低いほど良い）
        """
        pass
    
    @abstractmethod
    def evaluate_with_breakdown(self, schedule: Schedule, school: School,
                               jiritsu_requirements: List[JiritsuRequirement]) -> EvaluationBreakdown:
        """詳細な評価内訳を含む評価
        
        Args:
            schedule: スケジュール
            school: 学校情報
            jiritsu_requirements: 自立活動要件のリスト
            
        Returns:
            評価の内訳
        """
        pass
    
    @abstractmethod
    def count_jiritsu_violations(self, schedule: Schedule, 
                                jiritsu_requirements: List[JiritsuRequirement]) -> int:
        """自立活動制約違反の数をカウント
        
        Args:
            schedule: スケジュール
            jiritsu_requirements: 自立活動要件のリスト
            
        Returns:
            違反数
        """
        pass
    
    @abstractmethod
    def calculate_teacher_load_variance(self, schedule: Schedule) -> float:
        """教員負荷の分散を計算
        
        Args:
            schedule: スケジュール
            
        Returns:
            教員負荷の分散
        """
        pass