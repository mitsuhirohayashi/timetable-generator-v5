"""パフォーマンスプロファイリングユーティリティ

時間割生成処理のパフォーマンスを計測・分析するためのユーティリティ
"""
import time
import functools
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    sub_metrics: List['PerformanceMetrics'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self):
        """計測を完了"""
        if self.end_time is None:
            self.end_time = time.time()
            self.duration = self.end_time - self.start_time
    
    def add_sub_metric(self, metric: 'PerformanceMetrics'):
        """サブメトリクスを追加"""
        self.sub_metrics.append(metric)
    
    def get_summary(self) -> Dict[str, Any]:
        """サマリーを取得"""
        summary = {
            'name': self.name,
            'duration': self.duration,
            'metadata': self.metadata
        }
        
        if self.sub_metrics:
            summary['sub_metrics'] = [m.get_summary() for m in self.sub_metrics]
            summary['total_sub_duration'] = sum(m.duration or 0 for m in self.sub_metrics)
        
        return summary


class PerformanceProfiler:
    """パフォーマンスプロファイラー"""
    
    def __init__(self):
        self.metrics_stack: List[PerformanceMetrics] = []
        self.completed_metrics: List[PerformanceMetrics] = []
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def measure(self, name: str, **metadata):
        """パフォーマンス計測コンテキストマネージャー
        
        Usage:
            with profiler.measure("phase_1", iteration=1):
                # 計測したい処理
                pass
        """
        metric = PerformanceMetrics(
            name=name,
            start_time=time.time(),
            metadata=metadata
        )
        
        # スタックに追加
        if self.metrics_stack:
            parent = self.metrics_stack[-1]
            parent.add_sub_metric(metric)
        
        self.metrics_stack.append(metric)
        
        try:
            yield metric
        finally:
            # 計測完了
            metric.complete()
            self.metrics_stack.pop()
            
            # トップレベルのメトリクスは完了リストに追加
            if not self.metrics_stack:
                self.completed_metrics.append(metric)
                self.logger.debug(f"Performance: {name} took {metric.duration:.3f}s")
    
    def time_function(self, func: Callable) -> Callable:
        """関数デコレーター形式でパフォーマンス計測
        
        Usage:
            @profiler.time_function
            def my_function():
                pass
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self.measure(func.__name__):
                return func(*args, **kwargs)
        return wrapper
    
    def get_report(self) -> Dict[str, Any]:
        """パフォーマンスレポートを取得"""
        return {
            'metrics': [m.get_summary() for m in self.completed_metrics],
            'total_duration': sum(m.duration or 0 for m in self.completed_metrics)
        }
    
    def print_report(self):
        """パフォーマンスレポートを出力"""
        report = self.get_report()
        
        print("\n=== パフォーマンスレポート ===")
        print(f"総実行時間: {report['total_duration']:.3f}秒\n")
        
        for metric in report['metrics']:
            self._print_metric(metric, level=0)
    
    def _print_metric(self, metric: Dict[str, Any], level: int = 0):
        """メトリクスを階層的に出力"""
        indent = "  " * level
        duration = metric.get('duration', 0)
        
        # メタデータを含めて出力
        metadata_str = ""
        if metric.get('metadata'):
            metadata_str = f" [{', '.join(f'{k}={v}' for k, v in metric['metadata'].items())}]"
        
        print(f"{indent}{metric['name']}: {duration:.3f}秒{metadata_str}")
        
        # サブメトリクスを出力
        if 'sub_metrics' in metric:
            for sub_metric in metric['sub_metrics']:
                self._print_metric(sub_metric, level + 1)


# グローバルプロファイラーインスタンス
global_profiler = PerformanceProfiler()


def measure_performance(name: str, **metadata):
    """パフォーマンス計測デコレーター
    
    Usage:
        @measure_performance("my_function", category="optimization")
        def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with global_profiler.measure(name, **metadata):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class MemoryProfiler:
    """メモリ使用量プロファイラー"""
    
    def __init__(self):
        self.snapshots: List[Dict[str, Any]] = []
    
    def take_snapshot(self, label: str):
        """メモリスナップショットを取得"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            snapshot = {
                'label': label,
                'timestamp': time.time(),
                'rss': memory_info.rss / 1024 / 1024,  # MB
                'vms': memory_info.vms / 1024 / 1024,  # MB
            }
            
            self.snapshots.append(snapshot)
            return snapshot
            
        except ImportError:
            # psutilがインストールされていない場合はスキップ
            return None
    
    def get_memory_report(self) -> Dict[str, Any]:
        """メモリ使用量レポートを取得"""
        if not self.snapshots:
            return {'available': False}
        
        return {
            'available': True,
            'snapshots': self.snapshots,
            'peak_rss': max(s['rss'] for s in self.snapshots),
            'peak_vms': max(s['vms'] for s in self.snapshots)
        }