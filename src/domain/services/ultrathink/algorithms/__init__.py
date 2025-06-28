"""
高度なアルゴリズムパッケージ

制約伝播、スマートバックトラッキング、ヒューリスティクス、
グラフ最適化、前処理などの高度なアルゴリズムを提供。
"""

from .constraint_propagation import (
    ConstraintPropagation,
    Variable,
    Domain,
    Arc
)

from .smart_backtracking import (
    SmartBacktracking,
    AssignmentNode,
    NoGood
)

from .heuristics import (
    AdvancedHeuristics,
    HeuristicScore
)

from .constraint_graph_optimizer import (
    ConstraintGraphOptimizer,
    ConstraintCluster,
    GraphDecomposition
)

from .preprocessing_engine import (
    PreprocessingEngine,
    PreprocessingResult,
    SymmetryGroup
)

__all__ = [
    # 制約伝播
    'ConstraintPropagation',
    'Variable',
    'Domain',
    'Arc',
    
    # スマートバックトラッキング
    'SmartBacktracking',
    'AssignmentNode',
    'NoGood',
    
    # ヒューリスティクス
    'AdvancedHeuristics',
    'HeuristicScore',
    
    # グラフ最適化
    'ConstraintGraphOptimizer',
    'ConstraintCluster',
    'GraphDecomposition',
    
    # 前処理
    'PreprocessingEngine',
    'PreprocessingResult',
    'SymmetryGroup'
]