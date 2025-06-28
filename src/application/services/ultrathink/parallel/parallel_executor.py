"""並列タスク実行エンジン

並列処理のコア機能を提供します。
"""
import logging
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional

from .task_definitions import ParallelTask, TaskResult


class ParallelExecutor:
    """並列タスク実行エンジン"""
    
    def __init__(self, max_workers: int, use_threads: bool = False):
        """初期化
        
        Args:
            max_workers: 最大ワーカー数
            use_threads: スレッドを使用するか（デフォルトはプロセス）
        """
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        self.use_threads = use_threads
        
        # 統計情報
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_time': 0.0
        }
    
    def execute_tasks(self, tasks: List[ParallelTask]) -> List[TaskResult]:
        """タスクを並列実行
        
        Args:
            tasks: 実行するタスクのリスト
            
        Returns:
            実行結果のリスト
        """
        if not tasks:
            return []
        
        # 優先度順にソート
        tasks.sort(key=lambda t: t.priority, reverse=True)
        
        results = []
        executor_class = ThreadPoolExecutor if self.use_threads else ProcessPoolExecutor
        
        start_time = time.time()
        
        try:
            with executor_class(max_workers=self.max_workers) as executor:
                # タスクを投入
                future_to_task = {}
                for task in tasks:
                    future = executor.submit(self._execute_single_task, task)
                    future_to_task[future] = task
                    self.stats['total_tasks'] += 1
                
                # 結果を収集
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result(timeout=300)  # 5分タイムアウト
                        results.append(result)
                        if result.success:
                            self.stats['successful_tasks'] += 1
                        else:
                            self.stats['failed_tasks'] += 1
                            self.logger.warning(f"タスク失敗: {task.task_id} - {result.error}")
                    except Exception as e:
                        self.logger.error(f"タスク実行エラー: {task.task_id} - {str(e)}")
                        results.append(TaskResult(
                            task_id=task.task_id,
                            success=False,
                            error=str(e)
                        ))
                        self.stats['failed_tasks'] += 1
        
        except Exception as e:
            self.logger.error(f"並列実行エラー: {str(e)}")
            # フォールバック：シーケンシャル実行
            self.logger.info("シーケンシャル実行にフォールバック")
            for task in tasks:
                result = self._execute_single_task(task)
                results.append(result)
        
        self.stats['total_time'] += time.time() - start_time
        
        return results
    
    def _execute_single_task(self, task: ParallelTask) -> TaskResult:
        """単一タスクを実行（サブクラスでオーバーライド）"""
        # デフォルト実装（実際のタスク実行はサブクラスで実装）
        return TaskResult(
            task_id=task.task_id,
            success=False,
            error="Not implemented"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        success_rate = 0.0
        if self.stats['total_tasks'] > 0:
            success_rate = (self.stats['successful_tasks'] / self.stats['total_tasks']) * 100
        
        return {
            'total_tasks': self.stats['total_tasks'],
            'successful_tasks': self.stats['successful_tasks'],
            'failed_tasks': self.stats['failed_tasks'],
            'success_rate': success_rate,
            'total_time': self.stats['total_time'],
            'workers': self.max_workers,
            'executor_type': 'threads' if self.use_threads else 'processes'
        }
    
    def reset_stats(self):
        """統計情報をリセット"""
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_time': 0.0
        }