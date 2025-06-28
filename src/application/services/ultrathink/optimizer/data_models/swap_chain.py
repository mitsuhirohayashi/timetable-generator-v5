"""連鎖的な交換データモデル"""
from dataclasses import dataclass, field
from typing import List

from .swap_candidate import SwapCandidate


@dataclass
class SwapChain:
    """連鎖的な交換
    
    Attributes:
        swaps: 交換候補のリスト
        total_improvement: 総改善度
    """
    swaps: List[SwapCandidate] = field(default_factory=list)
    total_improvement: float = 0.0
    
    def add_swap(self, swap: SwapCandidate):
        """交換を追加"""
        self.swaps.append(swap)
        self.total_improvement += swap.net_improvement