"""並列最適化エンジン

リファクタリング版の並列最適化エンジンをインポートします。
後方互換性のために、このファイルは元の場所に残されています。
"""

# リファクタリング版のモジュールから全てインポート
from .parallel.parallel_optimization_engine import (
    ParallelOptimizationEngine,
    ParallelOptimizationConfig
)
from .parallel.task_definitions import (
    ParallelTask,
    TaskResult,
    OptimizationCandidate
)

# 後方互換性のためのエクスポート
__all__ = [
    'ParallelOptimizationEngine',
    'ParallelOptimizationConfig',
    'ParallelTask',
    'TaskResult',
    'OptimizationCandidate'
]