"""
高度な配置エンジン

フェーズ2で実装した高度なアルゴリズムを統合した配置エンジン。
制約伝播、スマートバックトラッキング、ヒューリスティクスを活用。
"""
import logging
import time
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass
from contextlib import nullcontext

from ....entities.schedule import Schedule
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment

from ..algorithms import (
    ConstraintPropagation, Variable, Domain,
    SmartBacktracking,
    AdvancedHeuristics,
    ConstraintGraphOptimizer,
    PreprocessingEngine
)
from .performance_cache import PerformanceCache
from .parallel_engine import ParallelEngine

# パフォーマンス最適化（フェーズ3）
from ..performance.jit_compiler import JITOptimizer
from ..performance.memory_pool import get_memory_pool, PoolContext
from ..performance.cpu_optimizer import get_cpu_optimizer
from ..performance.parallel_algorithms import ParallelAlgorithms
from ..performance.profiling_engine import get_profiler
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class PlacementResult:
    """配置結果"""
    schedule: Schedule
    success: bool
    placed_count: int
    failed_count: int
    violations: List[Any]
    execution_time: float
    algorithm_stats: Dict[str, Any]


class AdvancedPlacementEngine(LoggingMixin):
    """高度な配置エンジン"""
    
    def __init__(
        self,
        cache: Optional[PerformanceCache] = None,
        parallel_engine: Optional[ParallelEngine] = None,
        enable_preprocessing: bool = True,
        enable_learning: bool = True,
        enable_performance_optimization: bool = True
    ):
        super().__init__()
        self.cache = cache
        self.parallel_engine = parallel_engine
        self.enable_preprocessing = enable_preprocessing
        self.enable_learning = enable_learning
        self.enable_performance_optimization = enable_performance_optimization
        
        # アルゴリズムコンポーネント
        self.constraint_propagation = None
        self.smart_backtracking = None
        self.heuristics = None
        self.graph_optimizer = None
        self.preprocessing_engine = None
        
        # パフォーマンス最適化コンポーネント（フェーズ3）
        if self.enable_performance_optimization:
            self.jit_optimizer = None  # 遅延初期化
            self.memory_pool = get_memory_pool()
            self.cpu_optimizer = get_cpu_optimizer()
            self.parallel_algorithms = ParallelAlgorithms()
            self.profiler = get_profiler()
        else:
            self.jit_optimizer = None
            self.memory_pool = None
            self.cpu_optimizer = None
            self.parallel_algorithms = None
            self.profiler = None
        
        # 統計情報
        self.stats = {
            'total_placements': 0,
            'successful_placements': 0,
            'preprocessing_time': 0.0,
            'search_time': 0.0,
            'total_time': 0.0,
            'jit_speedup': 0.0,
            'memory_saved_mb': 0.0,
            'parallel_speedup': 0.0
        }
    
    def place_assignments(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any],
        time_limit: Optional[float] = None
    ) -> PlacementResult:
        """
        高度なアルゴリズムを使用して割り当てを配置
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            constraints: 制約情報
            time_limit: 制限時間
            
        Returns:
            PlacementResult: 配置結果
        """
        self.logger.info("高度な配置エンジン: 配置開始")
        
        # プロファイリング開始
        if self.profiler:
            self.profiler.start_profiling()
        
        # メモリプールコンテキスト使用
        with PoolContext(self.memory_pool) if self.memory_pool else nullcontext():
            start_time = time.time()
            
            self.stats['total_placements'] += 1
        
        # コンポーネントの初期化
        self._initialize_components(school)
        
        # 既存の固定割り当てを取得
        fixed_assignments = self._get_fixed_assignments(schedule, constraints)
        
        # 制約伝播の初期化
        self.constraint_propagation.initialize_from_schedule(
            schedule, fixed_assignments
        )
        
        # 前処理
        preprocessing_result = None
        if self.enable_preprocessing:
            preprocessing_start = time.time()
            preprocessing_result = self._run_preprocessing(fixed_assignments)
            self.stats['preprocessing_time'] += time.time() - preprocessing_start
        
        # グラフ最適化
        if self.graph_optimizer:
            self.graph_optimizer.build_constraint_graph(
                self.constraint_propagation.variables,
                self.constraint_propagation.arcs
            )
            decomposition = self.graph_optimizer.optimize_graph_structure()
        
        # 探索開始
        search_start = time.time()
        search_result = self._run_search(
            schedule,
            school,
            preprocessing_result.implied_assignments if preprocessing_result else fixed_assignments,
            time_limit
        )
        self.stats['search_time'] += time.time() - search_start
        
        # 結果の作成
        execution_time = time.time() - start_time
        self.stats['total_time'] += execution_time
        
        if search_result:
            self.stats['successful_placements'] += 1
            
            # スケジュールに適用
            final_schedule = self._apply_assignments(schedule, search_result)
            
            # 統計情報の収集
            algorithm_stats = self._collect_statistics()
            
            # プロファイリング停止
            if self.profiler:
                perf_report = self.profiler.stop_profiling()
                algorithm_stats['performance_report'] = {
                    'total_time': perf_report.total_execution_time,
                    'bottlenecks': [
                        {'function': b.function_name, 'impact': b.impact_score}
                        for b in perf_report.bottlenecks[:3]
                    ],
                    'memory_peak_mb': perf_report.memory_usage.get('peak_mb', 0)
                }
                
                # 自動チューニング
                tuning_params = self.profiler.auto_tune_parameters()
                self.logger.info(f"自動チューニング: {tuning_params}")
            
            return PlacementResult(
                schedule=final_schedule,
                success=True,
                placed_count=len(search_result),
                failed_count=0,
                violations=[],
                execution_time=execution_time,
                algorithm_stats=algorithm_stats
            )
        else:
            # 失敗した場合
            if self.profiler:
                self.profiler.stop_profiling()
                
            return PlacementResult(
                schedule=schedule,
                success=False,
                placed_count=0,
                failed_count=len(self.constraint_propagation.variables) - len(fixed_assignments),
                violations=self._analyze_failure_reasons(),
                execution_time=execution_time,
                algorithm_stats=self._collect_statistics()
            )
    
    def _initialize_components(self, school: School):
        """コンポーネントを初期化"""
        # JIT最適化の初期化（学校データ依存）
        if self.enable_performance_optimization and self.jit_optimizer is None:
            school_data = {
                'classes': school.get_all_classes(),
                'teachers': school.get_all_teachers(),
                'subjects': school.get_all_subjects()
            }
            self.jit_optimizer = JITOptimizer(school_data)
        
        # 制約伝播
        self.constraint_propagation = ConstraintPropagation(school, self.cache)
        
        # スマートバックトラッキング
        self.smart_backtracking = SmartBacktracking(
            school,
            self.constraint_propagation,
            enable_learning=self.enable_learning
        )
        
        # ヒューリスティクス
        self.heuristics = AdvancedHeuristics(school)
        
        # グラフ最適化
        self.graph_optimizer = ConstraintGraphOptimizer(school)
        
        # 前処理エンジン
        if self.enable_preprocessing:
            self.preprocessing_engine = PreprocessingEngine(school)
    
    def _get_fixed_assignments(
        self,
        schedule: Schedule,
        constraints: Dict[str, Any]
    ) -> Set[Tuple[TimeSlot, ClassReference]]:
        """固定割り当てを取得"""
        fixed = set()
        
        # 固定科目
        fixed_subjects = constraints.get('fixed_subjects', [])
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in fixed_subjects:
                fixed.add((time_slot, assignment.class_ref))
            elif schedule.is_locked(time_slot, assignment.class_ref):
                fixed.add((time_slot, assignment.class_ref))
        
        return fixed
    
    def _run_preprocessing(
        self,
        initial_assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> 'PreprocessingResult':
        """前処理を実行"""
        self.logger.debug("前処理を実行中")
        
        return self.preprocessing_engine.preprocess(
            self.constraint_propagation.variables,
            self.constraint_propagation.domains,
            self.constraint_propagation.arcs,
            initial_assignments
        )
    
    def _run_search(
        self,
        schedule: Schedule,
        school: School,
        initial_assignments: Dict[Variable, Tuple[str, Optional[str]]],
        time_limit: Optional[float]
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """探索を実行"""
        self.logger.debug("探索を開始")
        
        # AC-3による初期伝播
        if not self.constraint_propagation.ac3():
            self.logger.warning("初期制約伝播で矛盾を検出")
            return None
        
        # カスタマイズされたバックトラッキング探索
        return self._enhanced_backtrack_search(
            initial_assignments,
            time_limit or 300
        )
    
    def _enhanced_backtrack_search(
        self,
        initial_assignments: Dict[Variable, Tuple[str, Optional[str]]],
        time_limit: float
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """強化されたバックトラッキング探索"""
        # 並列アルゴリズムが使用可能な場合
        if self.parallel_algorithms and len(self.constraint_propagation.variables) > 50:
            self.logger.info("並列探索を使用")
            return self._parallel_search(initial_assignments, time_limit)
        
        # プロファイリングデコレータ適用
        if self.profiler:
            search_func = self.profiler.profile_decorator(self.smart_backtracking.search)
            result = search_func(
                initial_assignments=initial_assignments,
                time_limit=time_limit
            )
        else:
            # スマートバックトラッキングを使用
            result = self.smart_backtracking.search(
                initial_assignments=initial_assignments,
                time_limit=time_limit
            )
        
        if result:
            return result
        
        # フォールバック：シンプルな探索
        self.logger.info("スマートバックトラッキングが失敗、シンプル探索にフォールバック")
        return self._simple_backtrack_search(initial_assignments, time_limit)
    
    def _simple_backtrack_search(
        self,
        assignments: Dict[Variable, Tuple[str, Optional[str]]],
        time_limit: float
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """シンプルなバックトラッキング探索（フォールバック）"""
        start_time = time.time()
        
        # 未割り当て変数を取得
        unassigned = [
            v for v in self.constraint_propagation.variables
            if v not in assignments
        ]
        
        # JIT最適化が有効な場合、高速制約チェックを使用
        if self.jit_optimizer:
            return self._jit_optimized_backtrack(
                assignments,
                unassigned,
                start_time,
                time_limit
            )
        else:
            return self._simple_backtrack(
                assignments,
                unassigned,
                start_time,
                time_limit
            )
    
    def _simple_backtrack(
        self,
        assignments: Dict[Variable, Tuple[str, Optional[str]]],
        unassigned: List[Variable],
        start_time: float,
        time_limit: float
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """シンプルなバックトラッキング（再帰）"""
        # 時間制限チェック
        if time.time() - start_time > time_limit:
            return None
        
        # 完全割り当てチェック
        if not unassigned:
            return assignments.copy()
        
        # 変数選択（ヒューリスティクス使用）
        var = self.heuristics.select_variable(
            unassigned,
            self.constraint_propagation.domains,
            assignments,
            {'teacher_conflict': self.constraint_propagation.arcs}
        )
        
        remaining = [v for v in unassigned if v != var]
        domain = self.constraint_propagation.domains[var]
        
        # 値順序付け（ヒューリスティクス使用）
        ordered_values = self.heuristics.order_values(
            var,
            domain,
            assignments,
            self.constraint_propagation
        )
        
        for value in ordered_values:
            # 割り当て
            assignments[var] = value
            
            # MAC（Maintaining Arc Consistency）
            if self.constraint_propagation.maintain_arc_consistency(var, value):
                # 再帰的探索
                result = self._simple_backtrack(
                    assignments,
                    remaining,
                    start_time,
                    time_limit
                )
                
                if result:
                    return result
            
            # バックトラック
            del assignments[var]
        
        return None
    
    def _apply_assignments(
        self,
        schedule: Schedule,
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> Schedule:
        """割り当てをスケジュールに適用"""
        new_schedule = Schedule()
        
        # 既存の割り当てをコピー
        for time_slot, assignment in schedule.get_all_assignments():
            new_schedule.assign(time_slot, assignment)
        
        # 新しい割り当てを追加
        for var, (subject_name, teacher_name) in assignments.items():
            assignment = Assignment(
                var.class_ref,
                next(s for s in self.constraint_propagation.school.get_all_subjects() 
                     if s.name == subject_name),
                next(t for t in self.constraint_propagation.school.get_all_teachers() 
                     if t.name == teacher_name) if teacher_name else None
            )
            
            new_schedule.assign(var.time_slot, assignment)
        
        return new_schedule
    
    def _analyze_failure_reasons(self) -> List[Any]:
        """失敗理由を分析"""
        reasons = []
        
        # 空ドメインの変数
        empty_domains = [
            var for var, domain in self.constraint_propagation.domains.items()
            if domain.is_empty()
        ]
        
        if empty_domains:
            reasons.append({
                'type': 'empty_domains',
                'count': len(empty_domains),
                'variables': empty_domains[:10]  # 最初の10個
            })
        
        # 高競合の変数
        if self.smart_backtracking:
            stats = self.smart_backtracking.get_statistics()
            if stats['conflicts_detected'] > 100:
                reasons.append({
                    'type': 'high_conflicts',
                    'count': stats['conflicts_detected']
                })
        
        return reasons
    
    def _collect_statistics(self) -> Dict[str, Any]:
        """統計情報を収集"""
        stats = {
            'engine_stats': self.stats,
            'constraint_propagation': self.constraint_propagation.get_statistics() if self.constraint_propagation else {},
            'smart_backtracking': self.smart_backtracking.get_statistics() if self.smart_backtracking else {},
            'heuristics': self.heuristics.get_statistics() if self.heuristics else {},
            'graph_optimizer': self.graph_optimizer.get_statistics() if self.graph_optimizer else {},
            'preprocessing': self.preprocessing_engine.get_statistics() if self.preprocessing_engine else {}
        }
        
        return stats
    
    def _parallel_search(
        self,
        initial_assignments: Dict[Variable, Tuple[str, Optional[str]]],
        time_limit: float
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """並列探索の実装"""
        # 問題を部分問題に分解
        subproblems = self.parallel_algorithms.decompose_problem(
            (30, len(self.constraint_propagation.variables)),  # (時間スロット, クラス数)
            self.constraint_propagation.arcs,
            decomposition_strategy="hybrid"
        )
        
        # 部分問題ソルバー
        def solve_subproblem(subproblem):
            # 部分問題用の制約伝播を作成
            sub_assignments = {
                var: val for var, val in initial_assignments.items()
                if var in subproblem.variables
            }
            
            # 簡易探索実行
            return self._simple_backtrack(
                sub_assignments,
                [v for v in subproblem.variables if v not in sub_assignments],
                time.time(),
                time_limit / len(subproblems)
            )
        
        # 並列実行
        parallel_result = self.parallel_algorithms.solve_parallel(
            subproblems,
            solve_subproblem
        )
        
        if parallel_result.total_violations == 0:
            self.stats['parallel_speedup'] = parallel_result.speedup
            return parallel_result.combined_solution
        
        return None
    
    def _jit_optimized_backtrack(
        self,
        assignments: Dict[Variable, Tuple[str, Optional[str]]],
        unassigned: List[Variable],
        start_time: float,
        time_limit: float
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """JIT最適化されたバックトラッキング"""
        # 高速MRV変数選択
        if self.jit_optimizer:
            next_var_info = self.jit_optimizer.select_mrv_variable()
            if next_var_info:
                time_slot, class_ref = next_var_info
                var = next(v for v in unassigned 
                          if v.time_slot.day == time_slot[0] and 
                          v.time_slot.period == time_slot[1] and
                          v.class_ref.grade == class_ref[0] and
                          v.class_ref.class_number == class_ref[1])
            else:
                var = unassigned[0]
        else:
            var = unassigned[0]
        
        remaining = [v for v in unassigned if v != var]
        domain = self.constraint_propagation.domains[var]
        
        for value in domain.values:
            # JIT高速制約チェック
            if self.jit_optimizer:
                if not self.jit_optimizer.check_constraints_fast(
                    (var.time_slot.day, var.time_slot.period),
                    (var.class_ref.grade, var.class_ref.class_number),
                    value[0],  # subject_name
                    value[1]   # teacher_name
                ):
                    continue
            
            assignments[var] = value
            
            # 再帰探索
            if remaining:
                result = self._jit_optimized_backtrack(
                    assignments,
                    remaining,
                    start_time,
                    time_limit
                )
                if result:
                    return result
            else:
                return assignments.copy()
            
            del assignments[var]
            
            # 時間制限チェック
            if time.time() - start_time > time_limit:
                return None
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """エンジンの統計情報を取得"""
        stats = self._collect_statistics()
        
        # パフォーマンス最適化統計を追加
        if self.enable_performance_optimization:
            perf_stats = {
                'jit_enabled': self.jit_optimizer is not None,
                'memory_pool_stats': self.memory_pool.get_statistics() if self.memory_pool else {},
                'cpu_optimization': self.cpu_optimizer.get_optimization_stats() if self.cpu_optimizer else {},
                'parallel_stats': self.parallel_algorithms.get_statistics() if self.parallel_algorithms else {},
                'profiling_stats': self.profiler.get_statistics() if self.profiler else {}
            }
            stats['performance_optimization'] = perf_stats
        
        return stats