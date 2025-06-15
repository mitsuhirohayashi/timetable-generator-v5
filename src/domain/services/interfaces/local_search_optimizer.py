"""局所探索最適化のインターフェース"""
from abc import ABC, abstractmethod
from typing import List, Tuple
from dataclasses import dataclass

from ...entities.schedule import Schedule
from ...entities.school import School
from .jiritsu_placement_service import JiritsuRequirement


@dataclass
class OptimizationResult:
    """最適化結果"""
    initial_score: float
    final_score: float
    iterations_performed: int
    swap_attempts: int
    swap_successes: int
    improvement_percentage: float


class LocalSearchOptimizer(ABC):
    """局所探索最適化のインターフェース
    
    責務:
    - ランダムな授業交換による改善
    - 制約違反の解消
    - 教員負荷の平準化
    """
    
    @abstractmethod
    def optimize(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement],
                max_iterations: int) -> OptimizationResult:
        """局所探索による最適化を実行
        
        Args:
            schedule: スケジュール
            school: 学校情報
            jiritsu_requirements: 自立活動要件のリスト
            max_iterations: 最大反復回数
            
        Returns:
            最適化結果
        """
        pass
    
    @abstractmethod
    def try_swap(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement]) -> bool:
        """ランダムな交換を試みる
        
        Args:
            schedule: スケジュール
            school: 学校情報
            jiritsu_requirements: 自立活動要件のリスト
            
        Returns:
            交換が成功した場合True
        """
        pass
    
    @abstractmethod
    def select_swap_candidates(self, schedule: Schedule) -> Tuple[Tuple, Tuple]:
        """交換候補を選択
        
        Args:
            schedule: スケジュール
            
        Returns:
            交換候補のペア（スロット1, 割り当て1）、（スロット2, 割り当て2）
        """
        pass
    
    @abstractmethod
    def evaluate_swap(self, schedule: Schedule, school: School,
                     jiritsu_requirements: List[JiritsuRequirement],
                     before_score: float) -> bool:
        """交換の評価
        
        Args:
            schedule: スケジュール
            school: 学校情報
            jiritsu_requirements: 自立活動要件のリスト
            before_score: 交換前のスコア
            
        Returns:
            交換を受け入れる場合True
        """
        pass