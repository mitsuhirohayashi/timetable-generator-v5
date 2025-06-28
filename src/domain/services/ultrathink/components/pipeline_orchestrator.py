"""
パイプラインオーケストレーター

時間割生成の全体フローを管理し、各コンポーネントを協調動作させる。
エラー処理、リトライ、フォールバック戦略を実装。
"""
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import traceback

from ....entities.schedule import Schedule
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot
from ....value_objects.assignment import Assignment

from .core_placement_engine import CorePlacementEngine
from .constraint_manager import ConstraintManager
from .optimization_strategy_pool import OptimizationStrategyPool
from .learning_analytics_module import LearningAnalyticsModule
from .parallel_engine import ParallelEngine, ParallelTask
from .performance_cache import PerformanceCache
from .....shared.mixins.logging_mixin import LoggingMixin


class PipelineStage(Enum):
    """パイプラインステージ"""
    INITIALIZATION = "initialization"
    ANALYSIS = "analysis"
    PLACEMENT = "placement"
    OPTIMIZATION = "optimization"
    VALIDATION = "validation"
    LEARNING = "learning"
    FINALIZATION = "finalization"


class StageStatus(Enum):
    """ステージ実行状態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """ステージ実行結果"""
    stage: PipelineStage
    status: StageStatus
    execution_time: float
    result: Any = None
    error: Optional[Exception] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_successful(self) -> bool:
        return self.status in [StageStatus.COMPLETED, StageStatus.SKIPPED]


@dataclass
class PipelineContext:
    """パイプライン実行コンテキスト"""
    schedule: Schedule
    school: School
    constraints: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    stage_results: Dict[PipelineStage, StageResult] = field(default_factory=dict)
    
    def add_result(self, result: StageResult):
        """ステージ結果を追加"""
        self.stage_results[result.stage] = result
    
    def get_result(self, stage: PipelineStage) -> Optional[StageResult]:
        """ステージ結果を取得"""
        return self.stage_results.get(stage)


class PipelineOrchestrator(LoggingMixin):
    """パイプラインオーケストレーター"""
    
    def __init__(
        self,
        placement_engine: Optional['CorePlacementEngine'] = None,
        constraint_manager: Optional[ConstraintManager] = None,
        strategy_pool: Optional[OptimizationStrategyPool] = None,
        learning_module: Optional[LearningAnalyticsModule] = None,
        config: Optional[Any] = None,
        teacher_satisfaction: Optional[Any] = None,
        violation_learner: Optional[Any] = None,
        # 互換性のための旧パラメータ
        core_engine: Optional[CorePlacementEngine] = None,
        optimization_pool: Optional[OptimizationStrategyPool] = None,
        parallel_engine: Optional[ParallelEngine] = None,
        cache: Optional[PerformanceCache] = None
    ):
        super().__init__()
        
        # コンポーネント (新旧パラメータの互換性を保つ)
        self.core_engine = placement_engine or core_engine
        self.constraint_manager = constraint_manager
        self.optimization_pool = strategy_pool or optimization_pool
        self.learning_module = learning_module
        self.parallel_engine = parallel_engine
        self.cache = cache
        self.config = config
        self.teacher_satisfaction = teacher_satisfaction
        self.violation_learner = violation_learner
        
        # パイプライン設定
        self.pipeline_config = {
            PipelineStage.INITIALIZATION: {
                'handler': self._initialize_pipeline,
                'timeout': 10,
                'retry_count': 1,
                'critical': True
            },
            PipelineStage.ANALYSIS: {
                'handler': self._analyze_requirements,
                'timeout': 30,
                'retry_count': 2,
                'critical': False
            },
            PipelineStage.PLACEMENT: {
                'handler': self._execute_placement,
                'timeout': 120,
                'retry_count': 3,
                'critical': True
            },
            PipelineStage.OPTIMIZATION: {
                'handler': self._optimize_schedule,
                'timeout': 180,
                'retry_count': 2,
                'critical': False
            },
            PipelineStage.VALIDATION: {
                'handler': self._validate_result,
                'timeout': 30,
                'retry_count': 1,
                'critical': True
            },
            PipelineStage.LEARNING: {
                'handler': self._update_learning,
                'timeout': 20,
                'retry_count': 1,
                'critical': False
            },
            PipelineStage.FINALIZATION: {
                'handler': self._finalize_pipeline,
                'timeout': 10,
                'retry_count': 1,
                'critical': False
            }
        }
        
        # 実行統計
        self.execution_stats = defaultdict(lambda: {
            'executions': 0,
            'successes': 0,
            'failures': 0,
            'total_time': 0.0,
            'average_time': 0.0
        })
    
    def execute_pipeline(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any],
        skip_stages: Optional[List[PipelineStage]] = None
    ) -> Tuple[Schedule, Dict[str, Any]]:
        """
        パイプラインを実行
        
        Returns:
            Tuple[最終スケジュール, 実行メトリクス]
        """
        self.logger.info("パイプライン実行開始")
        start_time = time.time()
        
        # コンテキスト作成
        context = PipelineContext(
            schedule=schedule,
            school=school,
            constraints=constraints,
            metadata={
                'start_time': start_time,
                'skip_stages': skip_stages or []
            }
        )
        
        # 各ステージを実行
        for stage in PipelineStage:
            # スキップ判定
            if skip_stages and stage in skip_stages:
                context.add_result(StageResult(
                    stage=stage,
                    status=StageStatus.SKIPPED,
                    execution_time=0.0
                ))
                continue
            
            # ステージ実行
            result = self._execute_stage(stage, context)
            context.add_result(result)
            
            # クリティカルなステージが失敗した場合は中断
            if not result.is_successful and self.pipeline_config[stage]['critical']:
                self.logger.error(f"クリティカルステージ {stage.value} が失敗")
                break
        
        # 実行時間計算
        total_time = time.time() - start_time
        
        # メトリクス生成
        metrics = self._generate_metrics(context, total_time)
        
        self.logger.info(
            f"パイプライン実行完了: "
            f"時間={total_time:.2f}秒, "
            f"成功ステージ={metrics['successful_stages']}/{metrics['total_stages']}"
        )
        
        return context.schedule, metrics
    
    def _execute_stage(
        self,
        stage: PipelineStage,
        context: PipelineContext
    ) -> StageResult:
        """単一ステージを実行"""
        config = self.pipeline_config[stage]
        self.logger.info(f"ステージ実行開始: {stage.value}")
        
        start_time = time.time()
        retry_count = 0
        last_error = None
        
        # リトライループ
        while retry_count <= config['retry_count']:
            try:
                # タイムアウト付き実行（簡易版）
                result = config['handler'](context)
                
                # 成功
                execution_time = time.time() - start_time
                self._update_stats(stage, True, execution_time)
                
                return StageResult(
                    stage=stage,
                    status=StageStatus.COMPLETED,
                    execution_time=execution_time,
                    result=result
                )
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count <= config['retry_count']:
                    self.logger.warning(
                        f"ステージ {stage.value} 失敗 (リトライ {retry_count}/{config['retry_count']}): {e}"
                    )
                    time.sleep(min(2 ** retry_count, 10))  # 指数バックオフ
        
        # 最終的に失敗
        execution_time = time.time() - start_time
        self._update_stats(stage, False, execution_time)
        
        self.logger.error(
            f"ステージ {stage.value} 最終的に失敗: {last_error}\n"
            f"{traceback.format_exc()}"
        )
        
        return StageResult(
            stage=stage,
            status=StageStatus.FAILED,
            execution_time=execution_time,
            error=last_error
        )
    
    # ステージハンドラー
    
    def _initialize_pipeline(self, context: PipelineContext) -> Dict[str, Any]:
        """初期化ステージ"""
        # キャッシュクリア（必要に応じて）
        if context.constraints.get('clear_cache', False) and self.cache:
            self.cache.clear()
        
        # 制約の初期化
        if self.constraint_manager:
            self.constraint_manager.constraint_graph.clear()
        
        # 並列エンジンの起動
        if self.parallel_engine:
            self.parallel_engine._start_executor()
        
        # 初期統計
        initial_stats = {
            'total_classes': len(context.school.get_all_classes()),
            'total_teachers': len(context.school.get_all_teachers()),
            'total_subjects': len(context.school.get_all_subjects()),
            'initial_assignments': len(list(context.schedule.get_all_assignments()))
        }
        
        context.metadata['initial_stats'] = initial_stats
        return initial_stats
    
    def _analyze_requirements(self, context: PipelineContext) -> Dict[str, Any]:
        """要件分析ステージ"""
        # 難易度予測
        difficulty = self.learning_module.predict_difficulty(
            context.school,
            context.constraints
        )
        
        # 制約の複雑度分析
        constraint_complexity = self._analyze_constraint_complexity(context)
        
        # 配置戦略の決定
        placement_strategy = self._determine_placement_strategy(
            difficulty, constraint_complexity
        )
        
        analysis_result = {
            'difficulty': difficulty,
            'constraint_complexity': constraint_complexity,
            'placement_strategy': placement_strategy
        }
        
        context.metadata['analysis'] = analysis_result
        return analysis_result
    
    def _execute_placement(self, context: PipelineContext) -> Tuple[int, int]:
        """配置実行ステージ"""
        # 配置実行
        placed, failed = self.core_engine.place_assignments(
            context.schedule,
            context.school,
            context.constraints,
            time_limit=self.pipeline_config[PipelineStage.PLACEMENT]['timeout']
        )
        
        self.logger.info(f"配置結果: 成功={placed}, 失敗={failed}")
        
        # 結果をメタデータに保存
        context.metadata['placement_result'] = {
            'placed': placed,
            'failed': failed,
            'success_rate': placed / (placed + failed) if placed + failed > 0 else 0
        }
        
        return placed, failed
    
    def _optimize_schedule(self, context: PipelineContext) -> Schedule:
        """最適化ステージ"""
        # 初期評価
        initial_score, initial_violations, initial_conflicts = self._evaluate_schedule(
            context.schedule, context.school
        )
        
        # CRITICAL FIX: Keep a copy of the original schedule
        original_schedule = context.schedule.copy()
        
        # 最適化コンテキスト作成
        opt_context = {
            'violations': initial_violations,
            'teacher_conflicts': initial_conflicts,
            'time_limit': self.pipeline_config[PipelineStage.OPTIMIZATION]['timeout'],
            'optimization_level': context.constraints.get('optimization_level', 'balanced')
        }
        
        # 最適化実行
        optimized = self.optimization_pool.optimize(
            context.schedule,
            context.school,
            lambda s: self._evaluate_schedule(s, context.school),
            opt_context
        )
        
        # 最終評価
        final_score, final_violations, final_conflicts = self._evaluate_schedule(
            optimized, context.school
        )
        
        # CRITICAL FIX: If optimization made things worse, rollback
        if final_violations > initial_violations:
            self.logger.warning(f"⚠️ Optimization increased violations from {initial_violations} to {final_violations}, rolling back")
            optimized = original_schedule
            final_score = initial_score
            final_violations = initial_violations
            final_conflicts = initial_conflicts
        
        # 改善度を記録
        context.metadata['optimization_result'] = {
            'initial_score': initial_score,
            'final_score': final_score,
            'violations_reduced': initial_violations - final_violations,
            'conflicts_reduced': initial_conflicts - final_conflicts,
            'rolled_back': optimized == original_schedule
        }
        
        # 最適化されたスケジュールに更新
        context.schedule = optimized
        
        return optimized
    
    def _validate_result(self, context: PipelineContext) -> List[Any]:
        """検証ステージ"""
        # 全体制約チェック
        violations = self.constraint_manager.check_schedule(
            context.schedule,
            context.school,
            context.constraints
        )
        
        # 違反を重要度でグループ化
        grouped_violations = defaultdict(list)
        for violation in violations:
            grouped_violations[violation.priority.name].append(violation)
        
        # 検証結果
        validation_result = {
            'total_violations': len(violations),
            'critical_violations': len(grouped_violations.get('CRITICAL', [])),
            'high_violations': len(grouped_violations.get('HIGH', [])),
            'medium_violations': len(grouped_violations.get('MEDIUM', [])),
            'low_violations': len(grouped_violations.get('LOW', [])),
            'is_valid': len(grouped_violations.get('CRITICAL', [])) == 0
        }
        
        context.metadata['validation_result'] = validation_result
        
        # クリティカル違反がある場合はエラー
        if not validation_result['is_valid']:
            raise ValueError(f"クリティカル違反が{validation_result['critical_violations']}件あります")
        
        return violations
    
    def _update_learning(self, context: PipelineContext) -> Dict[str, Any]:
        """学習更新ステージ"""
        # 実行コンテキストの準備
        execution_context = {
            'school_size': len(context.school.get_all_classes()),
            'execution_time': sum(
                r.execution_time for r in context.stage_results.values()
            ),
            'strategy': context.metadata.get('analysis', {}).get('placement_strategy', 'unknown'),
            'parameters': context.constraints
        }
        
        # 違反情報
        violations = context.metadata.get('validation_result', {}).get('violations', [])
        
        # 学習モジュールで分析
        learning_result = self.learning_module.analyze_generation_result(
            context.schedule,
            context.school,
            violations,
            execution_context
        )
        
        context.metadata['learning_result'] = learning_result
        return learning_result
    
    def _finalize_pipeline(self, context: PipelineContext) -> Dict[str, Any]:
        """終了処理ステージ"""
        # キャッシュ最適化
        self.cache.optimize()
        
        # 統計情報の保存
        final_stats = {
            'cache_stats': self.cache.get_statistics(),
            'parallel_stats': self.parallel_engine.get_statistics(),
            'optimization_stats': self.optimization_pool.get_statistics()
        }
        
        # 成功したスケジュールをキャッシュ
        if context.metadata.get('validation_result', {}).get('is_valid', False):
            cache_key = self.cache.cache_schedule(context.schedule, context.constraints)
            final_stats['cache_key'] = cache_key
        
        return final_stats
    
    # ユーティリティメソッド
    
    def _analyze_constraint_complexity(
        self,
        context: PipelineContext
    ) -> Dict[str, Any]:
        """制約の複雑度を分析"""
        # 簡易実装
        return {
            'total_constraints': len(context.constraints),
            'teacher_absences': len(context.school._teacher_absences),
            'fixed_assignments': len([
                a for _, a in context.schedule.get_all_assignments()
                if context.schedule.is_locked(_, a.class_ref)
            ]),
            'complexity_score': 'medium'  # 簡易評価
        }
    
    def _determine_placement_strategy(
        self,
        difficulty: Dict[str, Any],
        complexity: Dict[str, Any]
    ) -> str:
        """配置戦略を決定"""
        # 難易度と複雑度から戦略を選択
        if difficulty.get('violation_risk', {}).get('CRITICAL', 0) > 0.5:
            return 'conservative'
        elif complexity.get('complexity_score') == 'high':
            return 'adaptive'
        else:
            return 'aggressive'
    
    def _evaluate_schedule(
        self,
        schedule: Schedule,
        school: School
    ) -> Tuple[float, int, int]:
        """スケジュールを評価"""
        # 簡易評価関数
        violations = self.constraint_manager.check_schedule(schedule, school)
        
        # 違反数をカウント
        violation_count = len(violations)
        conflict_count = len([v for v in violations if v.type.value == 'teacher_conflict'])
        
        # スコア計算（違反が少ないほど高スコア）
        score = 100.0 - violation_count * 10 - conflict_count * 5
        
        return max(0, score), violation_count, conflict_count
    
    def _update_stats(
        self,
        stage: PipelineStage,
        success: bool,
        execution_time: float
    ):
        """統計を更新"""
        stats = self.execution_stats[stage]
        stats['executions'] += 1
        
        if success:
            stats['successes'] += 1
        else:
            stats['failures'] += 1
        
        stats['total_time'] += execution_time
        stats['average_time'] = stats['total_time'] / stats['executions']
    
    def _generate_metrics(
        self,
        context: PipelineContext,
        total_time: float
    ) -> Dict[str, Any]:
        """実行メトリクスを生成"""
        # ステージ別の結果を集計
        successful_stages = sum(
            1 for r in context.stage_results.values()
            if r.is_successful
        )
        
        total_stages = len(context.stage_results)
        
        # 詳細メトリクス
        stage_metrics = {}
        for stage, result in context.stage_results.items():
            stage_metrics[stage.value] = {
                'status': result.status.value,
                'execution_time': result.execution_time,
                'metrics': result.metrics
            }
        
        return {
            'total_time': total_time,
            'successful_stages': successful_stages,
            'total_stages': total_stages,
            'success_rate': successful_stages / total_stages if total_stages > 0 else 0,
            'stage_metrics': stage_metrics,
            'metadata': context.metadata
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """パイプライン統計を取得"""
        stats = {}
        
        for stage, stage_stats in self.execution_stats.items():
            stats[stage.value] = {
                'executions': stage_stats['executions'],
                'success_rate': (
                    stage_stats['successes'] / stage_stats['executions']
                    if stage_stats['executions'] > 0 else 0
                ),
                'average_time': stage_stats['average_time']
            }
        
        return stats