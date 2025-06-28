"""
プロファイリングエンジン

実行時のパフォーマンスを分析し、ボトルネックを特定。
自動チューニングのための情報を収集。
"""
import logging
import time
import cProfile
import pstats
import io
import functools
import tracemalloc
import gc
from typing import Dict, List, Callable, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager
import threading
import psutil
from .....shared.mixins.logging_mixin import LoggingMixin
import numpy as np


@dataclass
class FunctionProfile:
    """関数プロファイル"""
    name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    memory_delta: int = 0
    
    def update(self, execution_time: float, memory_delta: int = 0):
        """統計を更新"""
        self.call_count += 1
        self.total_time += execution_time
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        self.avg_time = self.total_time / self.call_count
        self.memory_delta += memory_delta


@dataclass
class Bottleneck:
    """ボトルネック情報"""
    function_name: str
    impact_score: float  # 0-100
    optimization_suggestions: List[str]
    metrics: Dict[str, float]


@dataclass
class PerformanceReport:
    """パフォーマンスレポート"""
    total_execution_time: float
    function_profiles: Dict[str, FunctionProfile]
    bottlenecks: List[Bottleneck]
    memory_usage: Dict[str, Any]
    optimization_opportunities: List[str]


class ProfilingEngine(LoggingMixin):
    """プロファイリングエンジン"""
    
    def __init__(
        self,
        enable_cpu_profiling: bool = True,
        enable_memory_profiling: bool = True,
        enable_io_profiling: bool = True,
        sample_rate: float = 0.001  # 1ms
    ):
        super().__init__()
        self.enable_cpu_profiling = enable_cpu_profiling
        self.enable_memory_profiling = enable_memory_profiling
        self.enable_io_profiling = enable_io_profiling
        self.sample_rate = sample_rate
        
        # プロファイルデータ
        self.function_profiles: Dict[str, FunctionProfile] = {}
        self.call_stack: deque = deque()
        self.io_operations: List[Dict[str, Any]] = []
        
        # CPUプロファイラ
        self.cpu_profiler = cProfile.Profile() if enable_cpu_profiling else None
        
        # メモリトラッカー
        if enable_memory_profiling:
            tracemalloc.start()
        
        # 統計情報
        self.stats = {
            'profiling_overhead': 0.0,
            'samples_collected': 0,
            'gc_collections': defaultdict(int)
        }
        
        # パフォーマンスカウンター
        self.performance_counters = {
            'cache_hits': 0,
            'cache_misses': 0,
            'constraint_checks': 0,
            'backtrack_count': 0
        }
        
        # 自動チューニングパラメータ
        self.tuning_parameters = {
            'optimal_batch_size': 50,
            'optimal_thread_count': 4,
            'optimal_cache_size': 100
        }
    
    @contextmanager
    def profile_function(self, function_name: str):
        """関数プロファイリングコンテキスト"""
        start_time = time.perf_counter()
        start_memory = 0
        
        if self.enable_memory_profiling:
            start_memory = self._get_current_memory()
        
        # GC状態を記録
        gc_stats_before = gc.get_stats()
        
        try:
            yield self
        finally:
            # 実行時間
            execution_time = time.perf_counter() - start_time
            
            # メモリ差分
            memory_delta = 0
            if self.enable_memory_profiling:
                memory_delta = self._get_current_memory() - start_memory
            
            # プロファイル更新
            if function_name not in self.function_profiles:
                self.function_profiles[function_name] = FunctionProfile(function_name)
            
            self.function_profiles[function_name].update(execution_time, memory_delta)
            
            # GC統計
            gc_stats_after = gc.get_stats()
            self._update_gc_stats(gc_stats_before, gc_stats_after)
    
    def profile_decorator(self, func: Callable) -> Callable:
        """プロファイリングデコレータ"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self.profile_function(func.__name__):
                return func(*args, **kwargs)
        return wrapper
    
    def start_profiling(self):
        """プロファイリング開始"""
        if self.cpu_profiler:
            self.cpu_profiler.enable()
        
        self.stats['profiling_start_time'] = time.time()
    
    def stop_profiling(self) -> PerformanceReport:
        """プロファイリング停止とレポート生成"""
        if self.cpu_profiler:
            self.cpu_profiler.disable()
        
        total_time = time.time() - self.stats.get('profiling_start_time', time.time())
        
        # ボトルネック分析
        bottlenecks = self._analyze_bottlenecks()
        
        # メモリ使用状況
        memory_usage = self._get_memory_usage()
        
        # 最適化機会の特定
        optimization_opportunities = self._identify_optimization_opportunities()
        
        return PerformanceReport(
            total_execution_time=total_time,
            function_profiles=self.function_profiles,
            bottlenecks=bottlenecks,
            memory_usage=memory_usage,
            optimization_opportunities=optimization_opportunities
        )
    
    def update_counter(self, counter_name: str, value: int = 1):
        """パフォーマンスカウンターを更新"""
        if counter_name in self.performance_counters:
            self.performance_counters[counter_name] += value
    
    def record_io_operation(self, operation_type: str, duration: float, size: int = 0):
        """I/O操作を記録"""
        if self.enable_io_profiling:
            self.io_operations.append({
                'type': operation_type,
                'duration': duration,
                'size': size,
                'timestamp': time.time()
            })
    
    def _analyze_bottlenecks(self) -> List[Bottleneck]:
        """ボトルネックを分析"""
        bottlenecks = []
        
        # 総実行時間を計算
        total_time = sum(p.total_time for p in self.function_profiles.values())
        
        if total_time == 0:
            return bottlenecks
        
        # 各関数の影響度を計算
        for func_name, profile in self.function_profiles.items():
            impact_score = (profile.total_time / total_time) * 100
            
            if impact_score > 5:  # 5%以上の時間を占める関数
                suggestions = self._generate_optimization_suggestions(func_name, profile)
                
                bottleneck = Bottleneck(
                    function_name=func_name,
                    impact_score=impact_score,
                    optimization_suggestions=suggestions,
                    metrics={
                        'call_count': profile.call_count,
                        'avg_time': profile.avg_time,
                        'total_time': profile.total_time,
                        'memory_per_call': profile.memory_delta / profile.call_count if profile.call_count > 0 else 0
                    }
                )
                bottlenecks.append(bottleneck)
        
        # 影響度でソート
        bottlenecks.sort(key=lambda b: b.impact_score, reverse=True)
        
        return bottlenecks[:10]  # トップ10
    
    def _generate_optimization_suggestions(
        self,
        func_name: str,
        profile: FunctionProfile
    ) -> List[str]:
        """最適化提案を生成"""
        suggestions = []
        
        # 呼び出し回数が多い
        if profile.call_count > 1000:
            suggestions.append(f"Consider caching results ({profile.call_count} calls)")
            suggestions.append("Use memoization or result caching")
        
        # 平均実行時間が長い
        if profile.avg_time > 0.1:  # 100ms以上
            suggestions.append("Consider algorithm optimization")
            suggestions.append("Use JIT compilation with Numba")
            
            if 'constraint' in func_name.lower():
                suggestions.append("Use constraint propagation to reduce search space")
        
        # メモリ使用量が多い
        if profile.memory_delta > 10 * 1024 * 1024:  # 10MB以上
            suggestions.append("Optimize memory usage with object pooling")
            suggestions.append("Consider using more efficient data structures")
        
        # I/O関連
        if any(keyword in func_name.lower() for keyword in ['read', 'write', 'load', 'save']):
            suggestions.append("Use asynchronous I/O operations")
            suggestions.append("Implement batch processing for I/O")
        
        return suggestions
    
    def _identify_optimization_opportunities(self) -> List[str]:
        """最適化機会を特定"""
        opportunities = []
        
        # キャッシュ効率
        if self.performance_counters['cache_hits'] + self.performance_counters['cache_misses'] > 0:
            hit_rate = self.performance_counters['cache_hits'] / (
                self.performance_counters['cache_hits'] + self.performance_counters['cache_misses']
            )
            if hit_rate < 0.8:
                opportunities.append(f"Cache hit rate is low ({hit_rate:.1%}). Consider increasing cache size.")
        
        # バックトラック頻度
        if self.performance_counters['constraint_checks'] > 0:
            backtrack_rate = self.performance_counters['backtrack_count'] / self.performance_counters['constraint_checks']
            if backtrack_rate > 0.3:
                opportunities.append(f"High backtrack rate ({backtrack_rate:.1%}). Use better heuristics.")
        
        # GCオーバーヘッド
        gc_overhead = sum(self.stats['gc_collections'].values())
        if gc_overhead > 100:
            opportunities.append(f"Frequent GC collections ({gc_overhead}). Use object pooling.")
        
        # 並列化の機会
        cpu_count = psutil.cpu_count()
        if self.tuning_parameters['optimal_thread_count'] < cpu_count:
            opportunities.append(f"Underutilizing CPUs. Increase thread count to {cpu_count}.")
        
        return opportunities
    
    def auto_tune_parameters(self) -> Dict[str, Any]:
        """パラメータを自動チューニング"""
        # バッチサイズの最適化
        if self.function_profiles:
            avg_processing_time = np.mean([p.avg_time for p in self.function_profiles.values()])
            if avg_processing_time < 0.001:  # 1ms未満
                self.tuning_parameters['optimal_batch_size'] = min(200, self.tuning_parameters['optimal_batch_size'] * 2)
            elif avg_processing_time > 0.01:  # 10ms以上
                self.tuning_parameters['optimal_batch_size'] = max(10, self.tuning_parameters['optimal_batch_size'] // 2)
        
        # スレッド数の最適化
        cpu_usage = psutil.cpu_percent(interval=0.1)
        if cpu_usage < 50:
            self.tuning_parameters['optimal_thread_count'] = min(
                psutil.cpu_count(),
                self.tuning_parameters['optimal_thread_count'] + 1
            )
        elif cpu_usage > 90:
            self.tuning_parameters['optimal_thread_count'] = max(
                1,
                self.tuning_parameters['optimal_thread_count'] - 1
            )
        
        # キャッシュサイズの最適化
        if self.performance_counters['cache_hits'] + self.performance_counters['cache_misses'] > 100:
            hit_rate = self.performance_counters['cache_hits'] / (
                self.performance_counters['cache_hits'] + self.performance_counters['cache_misses']
            )
            if hit_rate < 0.7:
                self.tuning_parameters['optimal_cache_size'] = int(
                    self.tuning_parameters['optimal_cache_size'] * 1.5
                )
        
        return self.tuning_parameters
    
    def _get_current_memory(self) -> int:
        """現在のメモリ使用量を取得"""
        if self.enable_memory_profiling:
            current, _ = tracemalloc.get_traced_memory()
            return current
        return 0
    
    def _get_memory_usage(self) -> Dict[str, Any]:
        """メモリ使用状況を取得"""
        memory_info = {
            'current_mb': 0,
            'peak_mb': 0,
            'available_mb': 0,
            'percent': 0
        }
        
        if self.enable_memory_profiling:
            current, peak = tracemalloc.get_traced_memory()
            memory_info['current_mb'] = current / (1024 * 1024)
            memory_info['peak_mb'] = peak / (1024 * 1024)
        
        # システムメモリ情報
        vm = psutil.virtual_memory()
        memory_info['available_mb'] = vm.available / (1024 * 1024)
        memory_info['percent'] = vm.percent
        
        return memory_info
    
    def _update_gc_stats(self, before: List[Dict], after: List[Dict]):
        """GC統計を更新"""
        for i, (b, a) in enumerate(zip(before, after)):
            collections_delta = a.get('collections', 0) - b.get('collections', 0)
            if collections_delta > 0:
                self.stats['gc_collections'][f'gen{i}'] += collections_delta
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'function_count': len(self.function_profiles),
            'total_samples': self.stats['samples_collected'],
            'profiling_overhead': self.stats['profiling_overhead'],
            'performance_counters': dict(self.performance_counters),
            'gc_collections': dict(self.stats['gc_collections']),
            'tuning_parameters': self.tuning_parameters,
            'top_functions': [
                {
                    'name': p.name,
                    'calls': p.call_count,
                    'total_time': p.total_time,
                    'avg_time': p.avg_time
                }
                for p in sorted(
                    self.function_profiles.values(),
                    key=lambda x: x.total_time,
                    reverse=True
                )[:5]
            ]
        }


# グローバルプロファイラ（シングルトン）
_global_profiler = None


def get_profiler() -> ProfilingEngine:
    """グローバルプロファイラを取得"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = ProfilingEngine()
    return _global_profiler


def profile(func: Callable) -> Callable:
    """プロファイリングデコレータ"""
    return get_profiler().profile_decorator(func)