"""
Ultrathink - 高度な制約違反学習システム

このパッケージは、時間割生成システムの制約違反を分析・学習し、
将来の生成時に同じ違反を回避するための機械学習ベースのシステムを提供します。
"""

from .violation_pattern_analyzer import (
    ViolationFeature,
    ViolationPattern,
    ViolationPatternAnalyzer
)

from .constraint_violation_learning_system import (
    AvoidanceStrategy,
    LearningState,
    ConstraintViolationLearningSystem
)

from .parallel.parallel_optimization_engine import (
    ParallelTask,
    TaskResult,
    OptimizationCandidate,
    ParallelOptimizationEngine
)

# HybridScheduleGeneratorV7は削除（archiveに移動済み）

from .teacher_pattern_analyzer import (
    TeacherPreference,
    TeachingPattern,
    TeacherPatternAnalyzer
)

from .teacher_preference_learning_system import (
    PlacementFeedback,
    TeacherPreferenceLearningSystem
)

from .hybrid_schedule_generator_v8 import HybridScheduleGeneratorV8
from .configs.teacher_optimization_config import TeacherOptimizationConfig

from .test_period_protector import TestPeriodProtector

__all__ = [
    'ViolationFeature',
    'ViolationPattern',
    'ViolationPatternAnalyzer',
    'AvoidanceStrategy',
    'LearningState',
    'ConstraintViolationLearningSystem',
    'ParallelTask',
    'TaskResult',
    'OptimizationCandidate',
    'ParallelOptimizationEngine',
    'TeacherPreference',
    'TeachingPattern',
    'TeacherPatternAnalyzer',
    'PlacementFeedback',
    'TeacherPreferenceLearningSystem',
    'TeacherOptimizationConfig',
    'HybridScheduleGeneratorV8',
    'TestPeriodProtector'
]

__version__ = '1.2.0'