"""
超最適化時間割生成器

全バージョン（V2-V8）の最良機能を統合した、高性能で拡張可能な時間割生成システム。
プラグイン可能なコンポーネント設計により、必要な機能のみを有効化できます。

主な特徴:
- 設定駆動型アーキテクチャ
- 並列処理対応
- 自動最適化
- 学習機能統合
- 高速キャッシング
"""
import logging
import time
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing
from enum import Enum
import numpy as np

# コンポーネントインポート
from ....domain.services.ultrathink.components.core_placement_engine import CorePlacementEngine
from ....domain.services.ultrathink.components.constraint_manager import ConstraintManager
from ....domain.services.ultrathink.components.optimization_strategy_pool import OptimizationStrategyPool
from ....domain.services.ultrathink.components.learning_analytics_module import LearningAnalyticsModule
from ....domain.services.ultrathink.components.parallel_engine import ParallelEngine
from ....domain.services.ultrathink.components.performance_cache import PerformanceCache
from ....domain.services.ultrathink.components.pipeline_orchestrator import PipelineOrchestrator
from ....domain.services.ultrathink.components.advanced_placement_engine import AdvancedPlacementEngine
from ....domain.services.ultrathink.components.teacher_satisfaction_optimizer import TeacherSatisfactionOptimizer
from ....domain.services.ultrathink.components.violation_pattern_learner import ViolationPatternLearner

# 既存のインポート
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Teacher, Subject
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment
from ....domain.services.validators.constraint_validator import ConstraintValidator
from ....domain.services.synchronizers.exchange_class_synchronizer import ExchangeClassSynchronizer
from ....domain.services.synchronizers.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
from .test_period_protector import TestPeriodProtector
from .flexible_standard_hours_guarantee_system import FlexibleStandardHoursGuaranteeSystem
from .auto_optimizer import AutoOptimizer


class OptimizationLevel(Enum):
    """最適化レベル"""
    FAST = "fast"           # 高速モード（3秒以内）
    BALANCED = "balanced"   # バランスモード（5秒以内）
    QUALITY = "quality"     # 品質重視モード（10秒以内）
    EXTREME = "extreme"     # 極限最適化（時間無制限）


@dataclass
class UltraOptimizationConfig:
    """超最適化設定"""
    # 基本設定
    optimization_level: OptimizationLevel = OptimizationLevel.BALANCED
    time_limit: int = 300
    target_violations: int = 0
    
    # 機能フラグ
    enable_parallel_processing: bool = True
    enable_caching: bool = True
    enable_learning: bool = True
    enable_teacher_satisfaction: bool = True
    enable_flexible_hours: bool = True
    enable_test_period_protection: bool = True
    enable_violation_learning: bool = True  # 制約違反パターン学習
    
    # パフォーマンス設定
    max_workers: int = field(default_factory=lambda: multiprocessing.cpu_count())
    cache_size_mb: int = 200
    batch_size: int = 50
    
    # アルゴリズム設定
    use_constraint_propagation: bool = True
    use_beam_search: bool = True
    beam_width: int = 10
    early_termination_threshold: float = 0.95
    use_advanced_algorithms: bool = True  # 高度なアルゴリズムを使用
    enable_preprocessing: bool = True     # 前処理を有効化
    enable_graph_optimization: bool = True  # グラフ最適化を有効化
    
    # 学習設定
    learning_rate: float = 0.1
    pattern_recognition_threshold: float = 0.7
    auto_parameter_tuning: bool = True
    
    @classmethod
    def from_school_size(cls, school: 'School') -> 'UltraOptimizationConfig':
        """学校規模に基づいて自動設定"""
        total_classes = len(school.get_all_classes())
        total_teachers = len(school.get_all_teachers())
        
        if total_classes <= 10:
            return cls(
                optimization_level=OptimizationLevel.FAST,
                max_workers=2,
                beam_width=5
            )
        elif total_classes <= 20:
            return cls(
                optimization_level=OptimizationLevel.BALANCED,
                max_workers=4,
                beam_width=10
            )
        else:
            return cls(
                optimization_level=OptimizationLevel.QUALITY,
                max_workers=multiprocessing.cpu_count(),
                beam_width=15
            )
    
    @classmethod
    def auto_configure(
        cls,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        auto_optimizer: Optional['AutoOptimizer'] = None
    ) -> 'UltraOptimizationConfig':
        """自動最適化を使用して設定を生成"""
        if auto_optimizer is None:
            auto_optimizer = AutoOptimizer()
        
        recommendation = auto_optimizer.recommend_config(
            school=school,
            initial_schedule=initial_schedule
        )
        
        return recommendation.config


@dataclass
class OptimizationResult:
    """最適化結果"""
    schedule: Schedule
    violations: int = 0
    teacher_conflicts: int = 0
    execution_time: float = 0
    
    # 詳細統計
    statistics: Dict[str, Any] = field(default_factory=dict)
    improvements: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # 実行メトリクス
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    
    def is_successful(self) -> bool:
        """成功判定"""
        return self.violations == 0 and self.teacher_conflicts == 0


class UltraOptimizedScheduleGenerator:
    """超最適化時間割生成器"""
    
    @classmethod
    def create_with_auto_optimization(
        cls,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        enable_logging: bool = True
    ) -> 'UltraOptimizedScheduleGenerator':
        """自動最適化を使用して生成器を作成"""
        auto_optimizer = AutoOptimizer()
        
        # 最適な設定を自動推奨
        config = UltraOptimizationConfig.auto_configure(
            school=school,
            initial_schedule=initial_schedule,
            auto_optimizer=auto_optimizer
        )
        
        return cls(
            config=config,
            enable_logging=enable_logging,
            auto_optimizer=auto_optimizer
        )
    
    def __init__(
        self,
        config: Optional[UltraOptimizationConfig] = None,
        enable_logging: bool = True,
        auto_optimizer: Optional[AutoOptimizer] = None
    ):
        """
        Args:
            config: 最適化設定
            enable_logging: ログ出力を有効化
            auto_optimizer: 自動最適化システム
        """
        self.config = config or UltraOptimizationConfig()
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # CRITICAL FIX: Disable parallel processing to avoid race conditions
        if self.config.enable_parallel_processing:
            self.logger.warning("⚠️ Disabling parallel processing to avoid race conditions")
            self.config.enable_parallel_processing = False
        
        # 自動最適化システム
        self.auto_optimizer = auto_optimizer
        
        # コンポーネント初期化
        self._initialize_components()
        
        # 実行統計
        self.execution_stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'average_time': 0,
            'best_time': float('inf'),
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def _initialize_components(self):
        """コンポーネントの初期化"""
        # キャッシュ
        if self.config.enable_caching:
            self.cache = PerformanceCache(
                max_size_mb=self.config.cache_size_mb,
                default_ttl=3600
            )
        else:
            self.cache = None
        
        # 並列処理エンジン
        if self.config.enable_parallel_processing:
            self.parallel_engine = ParallelEngine(
                max_workers=self.config.max_workers,
                use_process_pool=self.config.optimization_level == OptimizationLevel.EXTREME
            )
        else:
            self.parallel_engine = None
        
        # コア配置エンジン
        if self.config.use_advanced_algorithms:
            self.placement_engine = AdvancedPlacementEngine(
                cache=self.cache,
                parallel_engine=self.parallel_engine,
                enable_preprocessing=self.config.enable_preprocessing,
                enable_learning=self.config.enable_learning
            )
        else:
            self.placement_engine = CorePlacementEngine(
            cache=self.cache,
            parallel_engine=self.parallel_engine
        )
        
        # 制約管理システム
        self.constraint_manager = ConstraintManager(
            enable_propagation=self.config.use_constraint_propagation,
            cache=self.cache
        )
        
        # 最適化戦略プール
        self.strategy_pool = OptimizationStrategyPool(
            beam_search_enabled=self.config.use_beam_search,
            beam_width=self.config.beam_width
        )
        
        # 学習・分析モジュール
        if self.config.enable_learning:
            self.learning_module = LearningAnalyticsModule(
                learning_rate=self.config.learning_rate,
                pattern_threshold=self.config.pattern_recognition_threshold
            )
        else:
            self.learning_module = None
        
        # 新しいコンポーネント（フェーズ4で追加）- パイプライン作成前に初期化
        if self.config.enable_teacher_satisfaction:
            self.teacher_satisfaction = TeacherSatisfactionOptimizer()
        else:
            self.teacher_satisfaction = None
            
        if self.config.enable_violation_learning:
            self.violation_learner = ViolationPatternLearner()
        else:
            self.violation_learner = None
        
        # パイプラインオーケストレーター
        self.pipeline = PipelineOrchestrator(
            placement_engine=self.placement_engine,
            constraint_manager=self.constraint_manager,
            strategy_pool=self.strategy_pool,
            learning_module=self.learning_module,
            config=self.config,
            teacher_satisfaction=self.teacher_satisfaction,
            violation_learner=self.violation_learner
        )
        
        # 既存のサービス統合
        self.constraint_validator = ConstraintValidator()
        self.grade5_synchronizer = RefactoredGrade5Synchronizer(self.constraint_validator)
        self.exchange_synchronizer = ExchangeClassSynchronizer()
        self.test_period_protector = TestPeriodProtector()
        
        # CRITICAL FIX: Add simple violation fixer
        from .simple_violation_fixer import SimpleViolationFixer
        self.violation_fixer = SimpleViolationFixer()
        
        if self.config.enable_flexible_hours:
            self.flexible_hours_system = FlexibleStandardHoursGuaranteeSystem()
        else:
            self.flexible_hours_system = None
        
        # Components already initialized above
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        followup_data: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """
        時間割を生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            followup_data: Follow-upデータ
            
        Returns:
            OptimizationResult: 生成結果
        """
        start_time = time.time()
        self.execution_stats['total_runs'] += 1
        
        self.logger.info("=== 超最適化時間割生成開始 ===")
        self.logger.info(f"最適化レベル: {self.config.optimization_level.value}")
        self.logger.info(f"並列処理: {'有効' if self.config.enable_parallel_processing else '無効'}")
        self.logger.info(f"キャッシュ: {'有効' if self.config.enable_caching else '無効'}")
        
        try:
            # 自動設定調整
            if self.config.auto_parameter_tuning:
                self._auto_tune_parameters(school)
            
            # テスト期間保護の初期化
            if self.config.enable_test_period_protection and followup_data:
                self.test_period_protector.load_followup_data(followup_data)
                if initial_schedule:
                    self.test_period_protector.load_initial_schedule(initial_schedule)
            
            # パイプライン実行
            # 初期スケジュールまたは空のスケジュールを準備
            if initial_schedule is None:
                initial_schedule = Schedule()
            
            # 制約情報を準備
            constraints = {
                'followup_data': followup_data,
                'time_limit': self.config.time_limit,
                'target_violations': self.config.target_violations
            }
            
            # パイプライン実行
            final_schedule, metrics = self.pipeline.execute_pipeline(
                schedule=initial_schedule,
                school=school,
                constraints=constraints
            )
            
            # CRITICAL FIX: Apply violation fixing after pipeline
            violations = metrics.get('violations', [])
            
            # If there are too many violations, use simplified approach
            if len(violations) > 50:
                self.logger.warning(f"⚠️ 違反が多すぎます ({len(violations)}件)。簡略化アプローチに切り替えます。")
                from .simplified_ultrathink_generator import SimplifiedUltrathinkGenerator
                
                simplified = SimplifiedUltrathinkGenerator()
                simplified_result = simplified.generate(school, initial_schedule, followup_data)
                
                # 簡略化結果を使用
                final_schedule = simplified_result.schedule
                violations = []
                for _ in range(simplified_result.violations):
                    violations.append(None)  # プレースホルダー
                
                # 統計を更新
                self.execution_stats['simplified_fallback'] = True
                
            elif violations and self.violation_fixer:
                self.logger.info(f"違反修正を実行: {len(violations)}件の違反")
                final_schedule, fixed_count = self.violation_fixer.fix_violations(
                    final_schedule, school, violations
                )
                
                # Re-validate after fixing
                new_violations = self.constraint_validator.validate_all(final_schedule)
                if len(new_violations) < len(violations):
                    self.logger.info(f"✅ 違反を {len(violations)} → {len(new_violations)} に削減")
                    violations = new_violations
            
            # 結果をOptimizationResultに変換
            result = OptimizationResult(
                schedule=final_schedule,
                violations=len(violations),
                execution_time=0.0  # 後で設定される
            )
            
            # 実行時間記録
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            # 統計更新
            self._update_statistics(result, execution_time)
            
            # 結果の評価
            self._evaluate_result(result, school)
            
            # 違反パターン学習
            if self.config.enable_violation_learning and result.violations > 0:
                self._learn_from_violations(result)
            
            # サマリー出力
            self._print_summary(result)
            
            # 自動最適化に実行結果を記録
            if self.auto_optimizer:
                self.auto_optimizer.record_execution(school, self.config, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"生成中にエラーが発生: {e}")
            # 最小限の結果を返す
            return OptimizationResult(
                schedule=initial_schedule or Schedule(),
                violations=-1,
                teacher_conflicts=-1,
                execution_time=time.time() - start_time,
                warnings=[f"生成エラー: {str(e)}"]
            )
    
    def _auto_tune_parameters(self, school: School):
        """パラメータの自動調整"""
        # 学校規模に基づく調整
        total_classes = len(school.get_all_classes())
        total_slots = total_classes * 30  # 5日 * 6時限
        
        # 実行履歴に基づく調整
        if self.execution_stats['total_runs'] > 5:
            avg_time = self.execution_stats['average_time']
            if avg_time > 10:
                # 遅い場合は並列度を上げる
                self.config.max_workers = min(
                    multiprocessing.cpu_count() * 2,
                    self.config.max_workers + 2
                )
                self.config.beam_width = max(5, self.config.beam_width - 2)
            elif avg_time < 3:
                # 速い場合は品質を上げる
                self.config.beam_width = min(20, self.config.beam_width + 2)
        
        self.logger.debug(f"パラメータ自動調整: workers={self.config.max_workers}, beam={self.config.beam_width}")
    
    def _update_statistics(self, result: OptimizationResult, execution_time: float):
        """統計情報の更新"""
        if result.is_successful():
            self.execution_stats['successful_runs'] += 1
        
        # 実行時間の更新
        total_runs = self.execution_stats['total_runs']
        prev_avg = self.execution_stats['average_time']
        self.execution_stats['average_time'] = (
            (prev_avg * (total_runs - 1) + execution_time) / total_runs
        )
        
        if execution_time < self.execution_stats['best_time']:
            self.execution_stats['best_time'] = execution_time
        
        # キャッシュ統計
        if self.cache:
            cache_stats = self.cache.get_statistics()
            self.execution_stats['cache_hits'] = cache_stats['hits']
            self.execution_stats['cache_misses'] = cache_stats['misses']
    
    def _evaluate_result(self, result: OptimizationResult, school: School):
        """結果の評価と改善点の記録"""
        # 成功率
        success_rate = (
            self.execution_stats['successful_runs'] / 
            self.execution_stats['total_runs'] * 100
        )
        
        # 教師満足度評価
        if self.teacher_satisfaction and result.schedule:
            satisfaction_scores = self.teacher_satisfaction.evaluate_schedule(
                result.schedule, school
            )
            avg_satisfaction = sum(s.total_score for s in satisfaction_scores.values()) / len(satisfaction_scores)
            result.statistics['teacher_satisfaction'] = {
                'average': avg_satisfaction,
                'scores': {name: score.total_score for name, score in satisfaction_scores.items()}
            }
            
            if avg_satisfaction > 0.8:
                result.improvements.append(f"高い教師満足度: {avg_satisfaction:.1%}")
        
        # パフォーマンス評価
        if result.execution_time < 3:
            result.improvements.append(f"高速実行: {result.execution_time:.1f}秒")
        
        if result.is_successful():
            result.improvements.append("全ての制約を満たす完璧な時間割を生成")
        
        # キャッシュ効率
        if self.cache:
            hit_rate = self.cache.get_hit_rate()
            if hit_rate > 0.5:
                result.improvements.append(f"キャッシュヒット率: {hit_rate:.1%}")
        
        # 並列処理効率
        if self.parallel_engine:
            speedup = result.performance_metrics.get('parallel_speedup', 1.0)
            if speedup > 1.5:
                result.improvements.append(f"並列処理による{speedup:.1f}倍高速化")
    
    def _print_summary(self, result: OptimizationResult):
        """結果サマリーの出力"""
        self.logger.info("\n=== 超最適化生成結果 ===")
        self.logger.info(f"実行時間: {result.execution_time:.2f}秒")
        self.logger.info(f"制約違反: {result.violations}件")
        self.logger.info(f"教師重複: {result.teacher_conflicts}件")
        
        if result.statistics:
            self.logger.info("\n統計情報:")
            for key, value in result.statistics.items():
                if isinstance(value, (int, float)):
                    self.logger.info(f"  {key}: {value}")
        
        if result.improvements:
            self.logger.info("\n改善点:")
            for improvement in result.improvements:
                self.logger.info(f"  ✓ {improvement}")
        
        if result.warnings:
            self.logger.info("\n警告:")
            for warning in result.warnings:
                self.logger.warning(f"  ⚠ {warning}")
    
    def _learn_from_violations(self, result: OptimizationResult):
        """違反から学習"""
        if not self.violation_learner or not result.schedule:
            return
            
        # 違反を記録
        # 注: 実際の実装では、resultに詳細な違反情報を含める必要があります
        # ここでは簡略化
        
        # 学習実行
        learning_result = self.violation_learner.learn()
        
        if learning_result.patterns_found > 0:
            self.logger.info(f"違反パターンを{learning_result.patterns_found}個発見")
            
            # 予防ルールを次回実行時に適用
            for rule in learning_result.preventive_rules[:3]:
                self.logger.info(f"  予防ルール: {rule['description']}")
        
        # 実行統計
        self.logger.info("\n累積統計:")
        self.logger.info(f"  総実行回数: {self.execution_stats['total_runs']}")
        self.logger.info(f"  成功率: {self.execution_stats['successful_runs'] / self.execution_stats['total_runs'] * 100:.1f}%")
        self.logger.info(f"  平均実行時間: {self.execution_stats['average_time']:.2f}秒")
        self.logger.info(f"  最速実行時間: {self.execution_stats['best_time']:.2f}秒")
        
        if self.cache:
            self.logger.info(f"  キャッシュヒット率: {self.cache.get_hit_rate():.1%}")
        
        # 教師満足度情報
        if 'teacher_satisfaction' in result.statistics:
            avg_sat = result.statistics['teacher_satisfaction']['average']
            self.logger.info(f"  教師満足度: {avg_sat:.1%}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポートの取得"""
        report = {
            'execution_stats': self.execution_stats,
            'cache_stats': self.cache.get_statistics() if self.cache else None,
            'parallel_stats': self.parallel_engine.get_statistics() if self.parallel_engine else None,
            'config': {
                'optimization_level': self.config.optimization_level.value,
                'parallel_enabled': self.config.enable_parallel_processing,
                'cache_enabled': self.config.enable_caching,
                'learning_enabled': self.config.enable_learning,
                'teacher_satisfaction_enabled': self.config.enable_teacher_satisfaction,
                'violation_learning_enabled': self.config.enable_violation_learning
            },
            'teacher_satisfaction': self.teacher_satisfaction.get_statistics() if self.teacher_satisfaction else None,
            'violation_learning': self.violation_learner.get_statistics() if self.violation_learner else None
        }
        
        # 自動最適化情報を追加
        if self.auto_optimizer:
            report['auto_optimization'] = self.auto_optimizer.get_statistics()
        
        return report