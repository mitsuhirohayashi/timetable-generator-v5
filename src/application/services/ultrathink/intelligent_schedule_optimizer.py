"""
インテリジェント修正システム（Ultrathink版）

このファイルは後方互換性のために維持されています。
実際の実装は optimizer/ ディレクトリに移動されました。
"""

# リファクタリング版のモジュールから全てインポート
from .optimizer.intelligent_schedule_optimizer import IntelligentScheduleOptimizer
from .optimizer.data_models import Violation, SwapCandidate, SwapChain
from .optimizer.violation_graph import ViolationGraph

# 後方互換性のためのエクスポート
__all__ = [
    'IntelligentScheduleOptimizer',
    'Violation',
    'SwapCandidate', 
    'SwapChain',
    'ViolationGraph'
]