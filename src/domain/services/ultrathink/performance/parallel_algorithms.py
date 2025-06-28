"""
並列アルゴリズム実装

独立した部分問題を並列に解決するための
高度な並列アルゴリズムを提供します。
"""
import logging
import numpy as np
from typing import List, Dict, Tuple, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, Future
import multiprocessing as mp
from queue import Queue, Empty
import threading
from collections import defaultdict
import time
import heapq
from functools import partial
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class SubProblem:
    """部分問題"""
    id: str
    variables: List[Tuple[int, int]]  # (slot_idx, class_idx)
    constraints: List[Any]
    priority: int = 0
    dependencies: Set[str] = field(default_factory=set)
    
    def __lt__(self, other):
        return self.priority > other.priority  # 高優先度を先に


@dataclass
class PartialSolution:
    """部分解"""
    subproblem_id: str
    assignments: Dict[Tuple[int, int], Any]
    violations: int = 0
    computation_time: float = 0.0


@dataclass
class ParallelResult:
    """並列実行結果"""
    combined_solution: Dict[Tuple[int, int], Any]
    total_violations: int
    execution_time: float
    speedup: float
    subproblem_count: int
    worker_stats: Dict[int, Dict[str, Any]]


class ParallelAlgorithms(LoggingMixin):
    """並列アルゴリズム実装"""
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        use_processes: bool = False,
        chunk_size: int = 10
    ):
        super().__init__()
        self.max_workers = max_workers or mp.cpu_count()
        self.use_processes = use_processes
        self.chunk_size = chunk_size
        
        # 実行統計
        self.stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'average_speedup': 0.0,
            'total_subproblems': 0
        }
        
        # ワーカープール
        self.executor = None
        self._initialize_executor()
    
    def _initialize_executor(self):
        """実行エンジンを初期化"""
        if self.use_processes:
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
    
    def decompose_problem(
        self,
        schedule_shape: Tuple[int, int],
        constraints: List[Any],
        decomposition_strategy: str = "spatial"
    ) -> List[SubProblem]:
        """
        問題を部分問題に分解
        
        Args:
            schedule_shape: (時間スロット数, クラス数)
            constraints: 制約リスト
            decomposition_strategy: 分解戦略
        """
        num_slots, num_classes = schedule_shape
        subproblems = []
        
        if decomposition_strategy == "spatial":
            # 空間的分解（クラスごと）
            subproblems = self._spatial_decomposition(
                num_slots, num_classes, constraints
            )
        elif decomposition_strategy == "temporal":
            # 時間的分解（曜日ごと）
            subproblems = self._temporal_decomposition(
                num_slots, num_classes, constraints
            )
        elif decomposition_strategy == "hybrid":
            # ハイブリッド分解
            subproblems = self._hybrid_decomposition(
                num_slots, num_classes, constraints
            )
        else:
            # 制約ベース分解
            subproblems = self._constraint_based_decomposition(
                num_slots, num_classes, constraints
            )
        
        self.logger.info(f"問題を{len(subproblems)}個の部分問題に分解")
        return subproblems
    
    def _spatial_decomposition(
        self,
        num_slots: int,
        num_classes: int,
        constraints: List[Any]
    ) -> List[SubProblem]:
        """空間的分解（クラスベース）"""
        subproblems = []
        classes_per_subproblem = max(1, num_classes // self.max_workers)
        
        for i in range(0, num_classes, classes_per_subproblem):
            end_class = min(i + classes_per_subproblem, num_classes)
            
            # このクラス範囲の変数
            variables = [
                (slot, cls)
                for slot in range(num_slots)
                for cls in range(i, end_class)
            ]
            
            # 関連する制約を抽出
            relevant_constraints = [
                c for c in constraints
                if self._is_constraint_relevant(c, i, end_class)
            ]
            
            subproblem = SubProblem(
                id=f"spatial_{i}_{end_class}",
                variables=variables,
                constraints=relevant_constraints,
                priority=len(variables)
            )
            subproblems.append(subproblem)
        
        return subproblems
    
    def _temporal_decomposition(
        self,
        num_slots: int,
        num_classes: int,
        constraints: List[Any]
    ) -> List[SubProblem]:
        """時間的分解（曜日ベース）"""
        subproblems = []
        slots_per_day = 6
        num_days = num_slots // slots_per_day
        
        for day in range(num_days):
            start_slot = day * slots_per_day
            end_slot = start_slot + slots_per_day
            
            variables = [
                (slot, cls)
                for slot in range(start_slot, end_slot)
                for cls in range(num_classes)
            ]
            
            subproblem = SubProblem(
                id=f"temporal_day{day}",
                variables=variables,
                constraints=constraints,  # 全制約（後でフィルタリング）
                priority=num_days - day  # 早い曜日を優先
            )
            subproblems.append(subproblem)
        
        return subproblems
    
    def _hybrid_decomposition(
        self,
        num_slots: int,
        num_classes: int,
        constraints: List[Any]
    ) -> List[SubProblem]:
        """ハイブリッド分解（時空間）"""
        subproblems = []
        
        # グリッド分割
        time_blocks = 3  # 朝、昼、午後
        class_blocks = min(self.max_workers // time_blocks, num_classes)
        
        slots_per_block = num_slots // time_blocks
        classes_per_block = num_classes // class_blocks
        
        for t_block in range(time_blocks):
            for c_block in range(class_blocks):
                start_slot = t_block * slots_per_block
                end_slot = min(start_slot + slots_per_block, num_slots)
                start_class = c_block * classes_per_block
                end_class = min(start_class + classes_per_block, num_classes)
                
                variables = [
                    (slot, cls)
                    for slot in range(start_slot, end_slot)
                    for cls in range(start_class, end_class)
                ]
                
                subproblem = SubProblem(
                    id=f"hybrid_t{t_block}_c{c_block}",
                    variables=variables,
                    constraints=constraints,
                    priority=len(variables)
                )
                subproblems.append(subproblem)
        
        return subproblems
    
    def _constraint_based_decomposition(
        self,
        num_slots: int,
        num_classes: int,
        constraints: List[Any]
    ) -> List[SubProblem]:
        """制約ベース分解（制約グラフのクラスタリング）"""
        # 制約グラフを構築
        constraint_graph = defaultdict(set)
        
        # 簡易的な実装（実際は制約の詳細な解析が必要）
        for slot in range(num_slots):
            for cls in range(num_classes):
                var = (slot, cls)
                # 隣接変数を追加
                if cls > 0:
                    constraint_graph[var].add((slot, cls - 1))
                if cls < num_classes - 1:
                    constraint_graph[var].add((slot, cls + 1))
        
        # 連結成分を見つける
        visited = set()
        components = []
        
        for var in constraint_graph:
            if var not in visited:
                component = self._dfs_component(var, constraint_graph, visited)
                components.append(component)
        
        # 各連結成分を部分問題に
        subproblems = []
        for i, component in enumerate(components[:self.max_workers]):
            subproblem = SubProblem(
                id=f"constraint_cluster_{i}",
                variables=list(component),
                constraints=constraints,
                priority=len(component)
            )
            subproblems.append(subproblem)
        
        return subproblems
    
    def _dfs_component(
        self,
        start: Tuple[int, int],
        graph: Dict[Tuple[int, int], Set[Tuple[int, int]]],
        visited: Set[Tuple[int, int]]
    ) -> Set[Tuple[int, int]]:
        """DFSで連結成分を探索"""
        component = set()
        stack = [start]
        
        while stack:
            var = stack.pop()
            if var not in visited:
                visited.add(var)
                component.add(var)
                stack.extend(graph[var] - visited)
        
        return component
    
    def _is_constraint_relevant(
        self,
        constraint: Any,
        start_class: int,
        end_class: int
    ) -> bool:
        """制約が指定クラス範囲に関連するか"""
        # 実際の実装では制約の型に応じて判定
        return True
    
    def solve_parallel(
        self,
        subproblems: List[SubProblem],
        solver_func: Callable[[SubProblem], PartialSolution],
        combine_func: Optional[Callable[[List[PartialSolution]], Dict]] = None
    ) -> ParallelResult:
        """
        部分問題を並列に解く
        
        Args:
            subproblems: 部分問題リスト
            solver_func: 部分問題を解く関数
            combine_func: 部分解を結合する関数
        """
        start_time = time.time()
        self.stats['total_executions'] += 1
        self.stats['total_subproblems'] += len(subproblems)
        
        # デフォルトの結合関数
        if combine_func is None:
            combine_func = self._default_combine_solutions
        
        # 依存関係を考慮した実行順序
        execution_order = self._topological_sort(subproblems)
        
        # 並列実行
        futures = {}
        partial_solutions = []
        worker_stats = defaultdict(lambda: {'solved': 0, 'time': 0.0})
        
        with self.executor as executor:
            # 独立した部分問題を並列実行
            for batch in self._batch_independent_subproblems(execution_order):
                batch_futures = {}
                
                for subproblem in batch:
                    future = executor.submit(solver_func, subproblem)
                    batch_futures[future] = subproblem
                
                # バッチの完了を待つ
                for future in as_completed(batch_futures):
                    subproblem = batch_futures[future]
                    try:
                        solution = future.result()
                        partial_solutions.append(solution)
                        
                        # ワーカー統計を更新
                        worker_id = hash(threading.current_thread().ident) % self.max_workers
                        worker_stats[worker_id]['solved'] += 1
                        worker_stats[worker_id]['time'] += solution.computation_time
                        
                    except Exception as e:
                        self.logger.error(f"部分問題{subproblem.id}の解決失敗: {e}")
        
        # 部分解を結合
        combined_solution = combine_func(partial_solutions)
        
        # 統計計算
        execution_time = time.time() - start_time
        sequential_time = sum(sol.computation_time for sol in partial_solutions)
        speedup = sequential_time / execution_time if execution_time > 0 else 1.0
        
        # 違反数計算
        total_violations = sum(sol.violations for sol in partial_solutions)
        
        # 成功判定
        if total_violations == 0:
            self.stats['successful_executions'] += 1
        
        # 平均スピードアップ更新
        n = self.stats['total_executions']
        self.stats['average_speedup'] = (
            (self.stats['average_speedup'] * (n - 1) + speedup) / n
        )
        
        return ParallelResult(
            combined_solution=combined_solution,
            total_violations=total_violations,
            execution_time=execution_time,
            speedup=speedup,
            subproblem_count=len(subproblems),
            worker_stats=dict(worker_stats)
        )
    
    def _topological_sort(self, subproblems: List[SubProblem]) -> List[SubProblem]:
        """依存関係に基づくトポロジカルソート"""
        # 入次数を計算
        in_degree = {sp.id: len(sp.dependencies) for sp in subproblems}
        id_to_subproblem = {sp.id: sp for sp in subproblems}
        
        # 入次数0のノードをキューに追加
        queue = [sp for sp in subproblems if in_degree[sp.id] == 0]
        result = []
        
        while queue:
            # 優先度でソート
            queue.sort(key=lambda x: x.priority, reverse=True)
            current = queue.pop(0)
            result.append(current)
            
            # 依存関係を更新
            for sp in subproblems:
                if current.id in sp.dependencies:
                    in_degree[sp.id] -= 1
                    if in_degree[sp.id] == 0:
                        queue.append(sp)
        
        return result
    
    def _batch_independent_subproblems(
        self,
        ordered_subproblems: List[SubProblem]
    ) -> List[List[SubProblem]]:
        """独立した部分問題をバッチ化"""
        batches = []
        processed = set()
        
        for subproblem in ordered_subproblems:
            # 依存関係が全て処理済みか確認
            if all(dep in processed for dep in subproblem.dependencies):
                # 現在のバッチに追加可能か確認
                added = False
                for batch in batches:
                    # バッチ内の他の問題と独立か確認
                    if self._are_independent(subproblem, batch):
                        batch.append(subproblem)
                        added = True
                        break
                
                if not added:
                    batches.append([subproblem])
                
                processed.add(subproblem.id)
        
        return batches
    
    def _are_independent(
        self,
        subproblem: SubProblem,
        batch: List[SubProblem]
    ) -> bool:
        """部分問題が独立か確認"""
        # 変数の重複をチェック
        sp_vars = set(subproblem.variables)
        for other in batch:
            if sp_vars.intersection(set(other.variables)):
                return False
        return True
    
    def _default_combine_solutions(
        self,
        partial_solutions: List[PartialSolution]
    ) -> Dict[Tuple[int, int], Any]:
        """デフォルトの解結合関数"""
        combined = {}
        
        for solution in partial_solutions:
            # 単純にマージ（競合は考慮しない）
            combined.update(solution.assignments)
        
        return combined
    
    def map_reduce_optimization(
        self,
        data: np.ndarray,
        map_func: Callable[[np.ndarray], Any],
        reduce_func: Callable[[List[Any]], Any],
        chunk_size: Optional[int] = None
    ) -> Any:
        """
        Map-Reduceパターンの最適化
        
        大規模データを分割して並列処理
        """
        if chunk_size is None:
            chunk_size = max(1, len(data) // self.max_workers)
        
        # データをチャンクに分割
        chunks = [
            data[i:i + chunk_size]
            for i in range(0, len(data), chunk_size)
        ]
        
        # Map フェーズ（並列）
        with self.executor as executor:
            map_results = list(executor.map(map_func, chunks))
        
        # Reduce フェーズ
        return reduce_func(map_results)
    
    def pipeline_parallel_execution(
        self,
        stages: List[Callable],
        initial_data: Any,
        buffer_size: int = 10
    ) -> Any:
        """
        パイプライン並列実行
        
        各ステージを並列に実行
        """
        # パイプラインバッファ
        buffers = [Queue(maxsize=buffer_size) for _ in range(len(stages) - 1)]
        
        def stage_worker(stage_idx: int, stage_func: Callable):
            """ステージワーカー"""
            input_buffer = buffers[stage_idx - 1] if stage_idx > 0 else None
            output_buffer = buffers[stage_idx] if stage_idx < len(stages) - 1 else None
            
            while True:
                try:
                    # 入力を取得
                    if input_buffer:
                        data = input_buffer.get(timeout=1.0)
                        if data is None:  # 終了シグナル
                            break
                    else:
                        data = initial_data
                    
                    # 処理実行
                    result = stage_func(data)
                    
                    # 出力
                    if output_buffer:
                        output_buffer.put(result)
                    else:
                        return result  # 最終ステージ
                    
                    if stage_idx == 0:
                        break  # 最初のステージは1回のみ
                        
                except Empty:
                    continue
        
        # 各ステージを並列実行
        with ThreadPoolExecutor(max_workers=len(stages)) as executor:
            futures = []
            for i, stage in enumerate(stages):
                future = executor.submit(stage_worker, i, stage)
                futures.append(future)
            
            # 最終ステージの結果を取得
            return futures[-1].result()
    
    def adaptive_work_stealing(
        self,
        tasks: List[Callable],
        max_steal_attempts: int = 3
    ) -> List[Any]:
        """
        適応的ワークスティーリング
        
        アイドルワーカーが他のワーカーからタスクを奪う
        """
        # タスクキュー（ワーカーごと）
        task_queues = [Queue() for _ in range(self.max_workers)]
        results = [None] * len(tasks)
        completed = threading.Event()
        
        # 初期タスク分配
        for i, task in enumerate(tasks):
            task_queues[i % self.max_workers].put((i, task))
        
        def worker(worker_id: int):
            """ワーカー関数"""
            local_queue = task_queues[worker_id]
            steal_attempts = 0
            
            while not completed.is_set():
                try:
                    # ローカルキューから取得
                    task_id, task = local_queue.get(timeout=0.1)
                    results[task_id] = task()
                    steal_attempts = 0
                    
                except Empty:
                    # ワークスティーリング
                    if steal_attempts < max_steal_attempts:
                        for i in range(self.max_workers):
                            if i != worker_id and not task_queues[i].empty():
                                try:
                                    task_id, task = task_queues[i].get_nowait()
                                    results[task_id] = task()
                                    steal_attempts = 0
                                    break
                                except Empty:
                                    continue
                        steal_attempts += 1
                    else:
                        # 全てのタスクが完了したか確認
                        if all(r is not None for r in results):
                            completed.set()
        
        # ワーカーを起動
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(worker, i)
                for i in range(self.max_workers)
            ]
            
            # 全ワーカーの完了を待つ
            for future in futures:
                future.result()
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """並列実行統計を取得"""
        return {
            'total_executions': self.stats['total_executions'],
            'successful_executions': self.stats['successful_executions'],
            'success_rate': (
                self.stats['successful_executions'] / 
                self.stats['total_executions'] * 100
                if self.stats['total_executions'] > 0 else 0
            ),
            'average_speedup': self.stats['average_speedup'],
            'total_subproblems_solved': self.stats['total_subproblems'],
            'max_workers': self.max_workers,
            'executor_type': 'process' if self.use_processes else 'thread'
        }
    
    def cleanup(self):
        """リソースのクリーンアップ"""
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None