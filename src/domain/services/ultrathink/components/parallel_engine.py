"""
並列処理エンジン

複数の処理を並列実行して高速化を実現。
スレッドプールと非同期処理を活用。
"""
import logging
import concurrent.futures
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, TypeVar
from dataclasses import dataclass
import time
from functools import partial
import multiprocessing as mp
from threading import Lock

from ....entities.schedule import Schedule
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


T = TypeVar('T')


@dataclass
class ParallelTask:
    """並列タスク"""
    name: str
    func: Callable
    args: tuple
    kwargs: dict
    priority: int = 0
    timeout: Optional[float] = None
    
    def __lt__(self, other):
        return self.priority > other.priority  # 優先度が高い方が先


@dataclass
class TaskResult:
    """タスク実行結果"""
    task_name: str
    success: bool
    result: Any
    error: Optional[Exception] = None
    execution_time: float = 0.0


class ParallelEngine(LoggingMixin):
    """並列処理エンジン"""
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        use_process_pool: bool = False,
        enable_async: bool = True
    ):
        super().__init__()
        
        # ワーカー数の決定
        if max_workers is None:
            max_workers = min(32, (mp.cpu_count() or 1) + 4)
        self.max_workers = max_workers
        
        # プロセスプールかスレッドプールか
        self.use_process_pool = use_process_pool
        self.enable_async = enable_async
        
        # エグゼキューター
        self.executor = None
        self._executor_lock = Lock()
        
        # 実行統計
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_execution_time': 0.0,
            'parallel_speedup': []
        }
    
    def __enter__(self):
        """コンテキストマネージャー開始"""
        self._start_executor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了"""
        self._stop_executor()
    
    def _start_executor(self):
        """エグゼキューターを開始"""
        with self._executor_lock:
            if self.executor is None:
                if self.use_process_pool:
                    self.executor = concurrent.futures.ProcessPoolExecutor(
                        max_workers=self.max_workers
                    )
                else:
                    self.executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=self.max_workers
                    )
                self.logger.info(
                    f"並列エンジン開始: "
                    f"{'プロセス' if self.use_process_pool else 'スレッド'}プール, "
                    f"ワーカー数={self.max_workers}"
                )
    
    def _stop_executor(self):
        """エグゼキューターを停止"""
        with self._executor_lock:
            if self.executor is not None:
                self.executor.shutdown(wait=True)
                self.executor = None
                self.logger.info("並列エンジン停止")
    
    def execute_parallel(
        self,
        tasks: List[ParallelTask],
        return_as_completed: bool = False
    ) -> List[TaskResult]:
        """
        タスクを並列実行
        
        Args:
            tasks: 実行するタスクのリスト
            return_as_completed: 完了順に結果を返すか
            
        Returns:
            TaskResultのリスト
        """
        if not tasks:
            return []
        
        # エグゼキューターが起動していない場合は起動
        if self.executor is None:
            self._start_executor()
        
        start_time = time.time()
        results = []
        
        # タスクを優先度順にソート
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        # フューチャーを作成
        futures = {}
        for task in sorted_tasks:
            future = self.executor.submit(
                self._execute_single_task,
                task
            )
            futures[future] = task
        
        # 結果を収集
        if return_as_completed:
            # 完了順に処理
            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                result = self._handle_future_result(future, task)
                results.append(result)
                
                # 早期終了の判定（オプション）
                if self._should_stop_early(results):
                    break
        else:
            # 順序を保持
            for future, task in futures.items():
                result = self._handle_future_result(future, task)
                results.append(result)
        
        # 統計更新
        execution_time = time.time() - start_time
        self._update_statistics(tasks, results, execution_time)
        
        return results
    
    async def execute_async(
        self,
        tasks: List[ParallelTask]
    ) -> List[TaskResult]:
        """
        タスクを非同期実行
        
        Args:
            tasks: 実行するタスクのリスト
            
        Returns:
            TaskResultのリスト
        """
        if not self.enable_async:
            return self.execute_parallel(tasks)
        
        # イベントループの取得または作成
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 非同期タスクを作成
        async_tasks = []
        for task in tasks:
            async_task = loop.run_in_executor(
                self.executor,
                self._execute_single_task,
                task
            )
            async_tasks.append(async_task)
        
        # 全タスクの完了を待つ
        results = await asyncio.gather(*async_tasks, return_exceptions=True)
        
        # 結果を整形
        task_results = []
        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                task_results.append(TaskResult(
                    task_name=task.name,
                    success=False,
                    result=None,
                    error=result
                ))
            else:
                task_results.append(result)
        
        return task_results
    
    def map_parallel(
        self,
        func: Callable[[T], Any],
        items: List[T],
        chunk_size: Optional[int] = None
    ) -> List[Any]:
        """
        マップ操作を並列実行
        
        Args:
            func: 適用する関数
            items: 処理対象のアイテム
            chunk_size: チャンクサイズ
            
        Returns:
            結果のリスト
        """
        if not items:
            return []
        
        if self.executor is None:
            self._start_executor()
        
        # チャンクサイズの決定
        if chunk_size is None:
            chunk_size = max(1, len(items) // (self.max_workers * 4))
        
        # マップ実行
        if chunk_size > 1:
            # チャンク化して実行
            results = list(self.executor.map(
                func, items, chunksize=chunk_size
            ))
        else:
            # 通常のマップ
            results = list(self.executor.map(func, items))
        
        return results
    
    def parallel_schedule_evaluation(
        self,
        schedules: List[Schedule],
        school: School,
        evaluate_func: Callable[[Schedule, School], Tuple[float, int, int]]
    ) -> List[Tuple[float, int, int]]:
        """
        スケジュールを並列評価
        
        特殊メソッド：スケジュール評価に特化
        """
        if not schedules:
            return []
        
        # 部分適用で評価関数を準備
        eval_func_partial = partial(evaluate_func, school=school)
        
        # 並列マップ実行
        results = self.map_parallel(eval_func_partial, schedules)
        
        return results
    
    def parallel_constraint_check(
        self,
        assignments: List[Tuple[TimeSlot, Assignment]],
        schedule: Schedule,
        school: School,
        check_func: Callable
    ) -> List[bool]:
        """
        制約チェックを並列実行
        
        特殊メソッド：制約チェックに特化
        """
        if not assignments:
            return []
        
        # タスクを作成
        tasks = []
        for i, (time_slot, assignment) in enumerate(assignments):
            task = ParallelTask(
                name=f"constraint_check_{i}",
                func=check_func,
                args=(schedule, time_slot, assignment, school),
                kwargs={},
                priority=1
            )
            tasks.append(task)
        
        # 並列実行
        results = self.execute_parallel(tasks)
        
        # 結果を抽出
        return [r.result if r.success else False for r in results]
    
    def _execute_single_task(self, task: ParallelTask) -> TaskResult:
        """単一タスクを実行"""
        start_time = time.time()
        
        try:
            # タイムアウト付き実行
            if task.timeout:
                # タイムアウト処理（簡易版）
                result = task.func(*task.args, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)
            
            execution_time = time.time() - start_time
            
            return TaskResult(
                task_name=task.name,
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"タスク '{task.name}' でエラー: {e}")
            
            return TaskResult(
                task_name=task.name,
                success=False,
                result=None,
                error=e,
                execution_time=execution_time
            )
    
    def _handle_future_result(
        self,
        future: concurrent.futures.Future,
        task: ParallelTask
    ) -> TaskResult:
        """フューチャーの結果を処理"""
        try:
            # タイムアウト付きで結果を取得
            timeout = task.timeout or 300  # デフォルト5分
            result = future.result(timeout=timeout)
            return result
            
        except concurrent.futures.TimeoutError:
            self.logger.error(f"タスク '{task.name}' がタイムアウト")
            return TaskResult(
                task_name=task.name,
                success=False,
                result=None,
                error=TimeoutError(f"Task timed out after {timeout}s")
            )
            
        except Exception as e:
            self.logger.error(f"タスク '{task.name}' の結果取得でエラー: {e}")
            return TaskResult(
                task_name=task.name,
                success=False,
                result=None,
                error=e
            )
    
    def _should_stop_early(self, results: List[TaskResult]) -> bool:
        """早期終了すべきか判定"""
        # 例：一定数の失敗があった場合
        failed_count = sum(1 for r in results if not r.success)
        return failed_count > 10
    
    def _update_statistics(
        self,
        tasks: List[ParallelTask],
        results: List[TaskResult],
        total_time: float
    ):
        """統計情報を更新"""
        self.stats['total_tasks'] += len(tasks)
        self.stats['successful_tasks'] += sum(1 for r in results if r.success)
        self.stats['failed_tasks'] += sum(1 for r in results if not r.success)
        self.stats['total_execution_time'] += total_time
        
        # 並列スピードアップの計算
        sequential_time = sum(r.execution_time for r in results)
        if sequential_time > 0:
            speedup = sequential_time / total_time
            self.stats['parallel_speedup'].append(speedup)
            
            # 最新100件のみ保持
            if len(self.stats['parallel_speedup']) > 100:
                self.stats['parallel_speedup'] = self.stats['parallel_speedup'][-100:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        avg_speedup = (
            sum(self.stats['parallel_speedup']) / len(self.stats['parallel_speedup'])
            if self.stats['parallel_speedup'] else 1.0
        )
        
        return {
            'total_tasks': self.stats['total_tasks'],
            'successful_tasks': self.stats['successful_tasks'],
            'failed_tasks': self.stats['failed_tasks'],
            'success_rate': (
                self.stats['successful_tasks'] / self.stats['total_tasks']
                if self.stats['total_tasks'] > 0 else 0
            ),
            'total_execution_time': self.stats['total_execution_time'],
            'average_speedup': avg_speedup,
            'max_workers': self.max_workers,
            'executor_type': 'process' if self.use_process_pool else 'thread'
        }
    
    def reset_statistics(self):
        """統計情報をリセット"""
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_execution_time': 0.0,
            'parallel_speedup': []
        }