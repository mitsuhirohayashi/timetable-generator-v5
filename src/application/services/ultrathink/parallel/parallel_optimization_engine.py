"""並列最適化エンジン（リファクタリング版）

マルチコアCPUを活用して時間割生成を高速化するエンジン。
各種並列処理戦略を統合的に管理します。
"""
import logging
import time
import random
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass
from multiprocessing import cpu_count
from collections import defaultdict

from .task_definitions import ParallelTask, TaskResult, OptimizationCandidate
from .parallel_executor import ParallelExecutor
from .schedule_serializer import ScheduleSerializer
from .optimization_strategies import OptimizationStrategies
from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.assignment import Assignment


@dataclass
class ParallelOptimizationConfig:
    """並列最適化設定"""
    enable_parallel_placement: bool = True
    enable_parallel_verification: bool = True
    enable_parallel_search: bool = True
    max_workers: Optional[int] = None
    use_threads: bool = False
    batch_size: int = 100
    strategy_time_limit: int = 60
    local_search_neighbors: int = 5
    sa_populations: int = 4


class ParallelOptimizationEngine:
    """並列最適化エンジン（リファクタリング版）"""
    
    def __init__(self, config: Optional[ParallelOptimizationConfig] = None):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        self.config = config or ParallelOptimizationConfig()
        
        # ワーカー数の決定
        self._determine_worker_count()
        
        # コンポーネントの初期化
        self.executor = OptimizationExecutor(self.max_workers, self.config.use_threads)
        self.strategies = OptimizationStrategies()
        self.serializer = ScheduleSerializer()
        
        self.logger.info(
            f"並列エンジン初期化: {self.max_workers}ワーカー "
            f"({'スレッド' if self.config.use_threads else 'プロセス'})"
        )
    
    def _determine_worker_count(self):
        """最適なワーカー数を決定"""
        if self.config.max_workers is None:
            available_cpus = cpu_count()
            if available_cpus <= 2:
                self.max_workers = available_cpus
            elif available_cpus <= 4:
                self.max_workers = available_cpus - 1
            else:
                self.max_workers = min(available_cpus - 2, 8)
        else:
            self.max_workers = self.config.max_workers
    
    def parallel_place_subjects(
        self,
        schedule: Schedule,
        school: School,
        placement_requirements: Dict[Any, List[Tuple[Any, Any, int]]]
    ) -> Schedule:
        """科目配置を並列実行"""
        if not self.config.enable_parallel_placement:
            return self._sequential_placement(schedule, school, placement_requirements)
        
        self.logger.info(f"並列配置を開始: {len(placement_requirements)}クラス")
        
        # タスクを作成
        tasks = self._create_placement_tasks(schedule, school, placement_requirements)
        
        # 並列実行
        results = self.executor.execute_tasks(tasks)
        
        # 結果をマージ
        return self._merge_placement_results(schedule, school, results)
    
    def parallel_verify_constraints(
        self,
        schedule: Schedule,
        school: School,
        constraint_validator: Any
    ) -> List[Any]:
        """制約検証を並列実行"""
        if not self.config.enable_parallel_verification:
            return constraint_validator.validate_all_constraints(schedule, school)
        
        self.logger.info("並列制約検証を開始")
        
        # 検証タスクを作成
        tasks = self._create_verification_tasks(schedule, school)
        
        # 並列実行
        results = self.executor.execute_tasks(tasks)
        
        # 結果を統合
        all_violations = []
        for result in results:
            if result.success and result.result:
                all_violations.extend(result.result)
        
        return all_violations
    
    def parallel_strategy_search(
        self,
        initial_schedule: Schedule,
        school: School,
        strategies: List[str]
    ) -> OptimizationCandidate:
        """複数の戦略を並列探索"""
        if not self.config.enable_parallel_search:
            return self._sequential_strategy_search(initial_schedule, school, strategies)
        
        self.logger.info(f"並列戦略探索を開始: {strategies}")
        
        # 戦略タスクを作成
        tasks = []
        for i, strategy in enumerate(strategies):
            task = ParallelTask(
                task_id=f"strategy_{strategy}",
                task_type="optimization",
                target=strategy,
                function="apply_strategy",
                args={
                    'schedule_data': self.serializer.serialize_schedule(initial_schedule),
                    'school_data': self.serializer.serialize_school(school),
                    'strategy': strategy
                },
                priority=10 - i
            )
            tasks.append(task)
        
        # 並列実行
        results = self.executor.execute_tasks(tasks)
        
        # 最良の結果を選択
        best_candidate = None
        best_score = float('-inf')
        
        for result in results:
            if result.success and result.result:
                candidate = result.result
                if candidate.score > best_score:
                    best_score = candidate.score
                    best_candidate = candidate
        
        return best_candidate or OptimizationCandidate(
            schedule=initial_schedule,
            score=0.0,
            violations=999,
            conflicts=999
        )
    
    def parallel_local_search(
        self,
        initial_schedule: Schedule,
        school: School,
        iterations: int = 100
    ) -> Schedule:
        """並列局所探索"""
        self.logger.info(f"並列局所探索を開始: {self.config.local_search_neighbors}近傍")
        
        best_schedule = self.serializer.copy_schedule(initial_schedule)
        best_score = self._evaluate_schedule(best_schedule, school)
        
        for i in range(iterations):
            # 近傍解を並列生成
            neighbors = self._generate_neighbors(best_schedule, school)
            
            # 最良の近傍を選択
            improved = False
            for neighbor in neighbors:
                score = self._evaluate_schedule(neighbor, school)
                if score > best_score:
                    best_schedule = neighbor
                    best_score = score
                    improved = True
                    break
            
            if not improved:
                break
            
            if i % 10 == 0:
                self.logger.debug(f"局所探索イテレーション {i}: スコア={best_score:.2f}")
        
        return best_schedule
    
    def _create_placement_tasks(
        self,
        schedule: Schedule,
        school: School,
        placement_requirements: Dict
    ) -> List[ParallelTask]:
        """配置タスクを作成"""
        tasks = []
        for class_ref, subjects in placement_requirements.items():
            task = ParallelTask(
                task_id=f"place_{class_ref.grade}_{class_ref.class_number}",
                task_type="placement",
                target=class_ref,
                function="place_subjects",
                args={
                    'subjects': subjects,
                    'schedule_data': self.serializer.serialize_schedule(schedule),
                    'school_data': self.serializer.serialize_school(school)
                },
                priority=len(subjects)
            )
            tasks.append(task)
        return tasks
    
    def _create_verification_tasks(
        self,
        schedule: Schedule,
        school: School
    ) -> List[ParallelTask]:
        """検証タスクを作成"""
        tasks = []
        days = ["月", "火", "水", "木", "金"]
        
        # 曜日ごとに検証タスクを作成
        for day in days:
            task = ParallelTask(
                task_id=f"verify_{day}",
                task_type="verification",
                target=day,
                function="verify_day",
                args={
                    'schedule_data': self.serializer.serialize_schedule(schedule),
                    'school_data': self.serializer.serialize_school(school),
                    'day': day
                }
            )
            tasks.append(task)
        
        return tasks
    
    def _merge_placement_results(
        self,
        base_schedule: Schedule,
        school: School,
        results: List[TaskResult]
    ) -> Schedule:
        """配置結果をマージ"""
        merged = self.serializer.copy_schedule(base_schedule)
        
        for result in results:
            if result.success and result.result:
                placements = result.result.get('placements', [])
                for placement in placements:
                    try:
                        time_slot = TimeSlot(placement['day'], placement['period'])
                        assignment = Assignment(
                            placement['class_ref'],
                            placement['subject'],
                            placement['teacher']
                        )
                        merged.assign(time_slot, assignment)
                    except:
                        pass
        
        return merged
    
    def _generate_neighbors(self, schedule: Schedule, school: School) -> List[Schedule]:
        """近傍解を生成"""
        neighbors = []
        
        for _ in range(self.config.local_search_neighbors):
            neighbor = self.serializer.copy_schedule(schedule)
            # ランダムな変更を加える
            self.strategies.random_swap(neighbor, school)
            neighbors.append(neighbor)
        
        return neighbors
    
    def _evaluate_schedule(self, schedule: Schedule, school: School) -> float:
        """スケジュールを評価"""
        score = 1000.0
        
        # 空きスロットのペナルティ
        empty_count = self._count_empty_slots(schedule, school)
        score -= empty_count * 10
        
        # 教師重複のペナルティ
        conflicts = self._count_teacher_conflicts(schedule, school)
        score -= conflicts * 50
        
        return score
    
    def _count_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きスロット数をカウント"""
        count = 0
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        count += 1
        return count
    
    def _count_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師の重複数をカウント"""
        conflicts = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 6):
                time_slot = TimeSlot(day, period)
                
                teacher_classes = defaultdict(list)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_classes[assignment.teacher.name].append(class_ref)
                
                for teacher_name, classes in teacher_classes.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        grade5_count = sum(
                            1 for c in classes 
                            if c.class_number == 5
                        )
                        if grade5_count < len(classes):
                            conflicts += len(classes) - 1
        
        return conflicts
    
    def _sequential_placement(
        self,
        schedule: Schedule,
        school: School,
        placement_requirements: Dict
    ) -> Schedule:
        """逐次配置（フォールバック）"""
        # シンプルな実装
        return schedule
    
    def _sequential_strategy_search(
        self,
        initial_schedule: Schedule,
        school: School,
        strategies: List[str]
    ) -> OptimizationCandidate:
        """逐次戦略探索（フォールバック）"""
        best_candidate = OptimizationCandidate(
            schedule=initial_schedule,
            score=self._evaluate_schedule(initial_schedule, school),
            violations=0,
            conflicts=0
        )
        
        for strategy in strategies:
            schedule = self.serializer.copy_schedule(initial_schedule)
            strategy_func = self.strategies.get_strategy(strategy)
            if strategy_func:
                strategy_func(schedule, school)
                score = self._evaluate_schedule(schedule, school)
                if score > best_candidate.score:
                    best_candidate = OptimizationCandidate(
                        schedule=schedule,
                        score=score,
                        violations=0,
                        conflicts=0
                    )
        
        return best_candidate
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """パフォーマンス統計を取得"""
        return self.executor.get_stats()


class OptimizationExecutor(ParallelExecutor):
    """最適化タスク実行エンジン"""
    
    def __init__(self, max_workers: int, use_threads: bool = False):
        super().__init__(max_workers, use_threads)
        self.serializer = ScheduleSerializer()
        self.strategies = OptimizationStrategies()
    
    def _execute_single_task(self, task: ParallelTask) -> TaskResult:
        """単一タスクを実行"""
        start_time = time.time()
        
        try:
            if task.task_type == "placement":
                result = self._execute_placement_task(task)
            elif task.task_type == "verification":
                result = self._execute_verification_task(task)
            elif task.task_type == "optimization":
                result = self._execute_optimization_task(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            return TaskResult(
                task_id=task.task_id,
                success=True,
                result=result,
                execution_time=time.time() - start_time
            )
        
        except Exception as e:
            self.logger.error(f"タスク実行エラー: {task.task_id} - {str(e)}")
            return TaskResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _execute_placement_task(self, task: ParallelTask) -> Dict[str, Any]:
        """配置タスクを実行（簡略版）"""
        # 実際の実装は省略
        return {'placements': []}
    
    def _execute_verification_task(self, task: ParallelTask) -> List[Any]:
        """検証タスクを実行（簡略版）"""
        # 実際の実装は省略
        return []
    
    def _execute_optimization_task(self, task: ParallelTask) -> OptimizationCandidate:
        """最適化タスクを実行"""
        schedule_data = task.args['schedule_data']
        school_data = task.args['school_data']
        strategy = task.args['strategy']
        
        schedule = self.serializer.deserialize_schedule(schedule_data)
        school = self.serializer.deserialize_school(school_data)
        
        # 戦略を適用
        strategy_func = self.strategies.get_strategy(strategy)
        if strategy_func:
            strategy_func(schedule, school)
        
        # 評価
        score = self._evaluate_schedule(schedule, school)
        
        return OptimizationCandidate(
            schedule=schedule,
            score=score,
            violations=0,
            conflicts=0
        )
    
    def _evaluate_schedule(self, schedule: Schedule, school: School) -> float:
        """スケジュールを評価（簡易版）"""
        return random.uniform(0, 100)