"""ローカルサーチ最適化のインターフェース"""
from abc import ABC, abstractmethod
from typing import List, Optional
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
    
    def __repr__(self) -> str:
        return (f"OptimizationResult(改善: {self.initial_score:.2f} -> {self.final_score:.2f}, "
                f"改善率: {self.improvement_percentage:.1f}%, "
                f"反復: {self.iterations_performed}, 交換成功: {self.swap_successes}/{self.swap_attempts})")


class LocalSearchOptimizer(ABC):
    """ローカルサーチ最適化のインターフェース"""
    
    @abstractmethod
    def optimize(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement],
                max_iterations: int = 200) -> OptimizationResult:
        """スケジュールを最適化
        
        Args:
            schedule: 最適化対象のスケジュール
            school: 学校情報
            jiritsu_requirements: 自立活動要件
            max_iterations: 最大反復回数
            
        Returns:
            最適化結果
        """
        pass
    
    @abstractmethod
    def find_swap_candidates(self, schedule: Schedule, school: School) -> List[tuple]:
        """交換候補を見つける
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            
        Returns:
            交換候補のリスト（タプルのリスト）
        """
        pass
    
    @abstractmethod
    def evaluate_swap(self, schedule: Schedule, school: School, 
                     swap_candidate: tuple) -> float:
        """交換の評価
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            swap_candidate: 交換候補
            
        Returns:
            交換後のスコア改善量（正の値が改善）
        """
        pass