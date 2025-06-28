"""スケジュール生成専用ユースケース

スケジュール生成のコアロジックに特化したユースケース。
CSPアルゴリズムの実行とジェネレーター選択を担当。
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from ...domain.exceptions import (
    TimetableGenerationError,
    PhaseExecutionError,
    ConstraintViolationError
)


@dataclass
class ScheduleGenerationRequest:
    """スケジュール生成リクエスト"""
    school: School
    initial_schedule: Optional[Schedule]
    constraint_system: UnifiedConstraintSystem
    max_iterations: int = 100
    use_advanced_csp: bool = True
    use_improved_csp: bool = False
    use_ultrathink: bool = False
    use_grade5_priority: bool = False
    use_unified_hybrid: bool = False
    search_mode: str = "auto"
    enable_jiritsu_priority: bool = True
    enable_local_search: bool = True


@dataclass
class ScheduleGenerationResult:
    """スケジュール生成結果"""
    schedule: Schedule
    success: bool
    iterations_used: int = 0
    algorithm_used: str = "unknown"
    statistics: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    violations_count: int = 0


class ScheduleGenerationUseCase:
    """スケジュール生成専用ユースケース
    
    責務:
    - CSPアルゴリズムの選択と実行
    - 生成戦略の管理
    - 生成統計の収集
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._generators = {}
        self._initialize_generators()
    
    def _initialize_generators(self) -> None:
        """利用可能なジェネレーターを初期化"""
        # 遅延インポートで循環参照を回避
        from ...domain.services.implementations.advanced_csp_schedule_generator import (
            AdvancedCSPScheduleGenerator
        )
        from ...domain.services.implementations.backtrack_jiritsu_placement_service import (
            BacktrackJiritsuPlacementService
        )
        from ...domain.services.implementations.greedy_subject_placement_service import (
            GreedySubjectPlacementService
        )
        from ...domain.services.implementations.improved_csp_generator import (
            ImprovedCSPGenerator
        )
        from ..services.ultrathink.ultrathink_perfect_generator import (
            UltrathinkPerfectGenerator
        )
        
        # 利用可能なジェネレーターを登録
        self._generators = {
            'advanced_csp': AdvancedCSPScheduleGenerator,
            'improved_csp': ImprovedCSPGenerator,
            'backtrack_jiritsu': BacktrackJiritsuPlacementService,
            'greedy': GreedySubjectPlacementService,
            'ultrathink': UltrathinkPerfectGenerator
        }
        self.logger.info(f"Available generators: {list(self._generators.keys())}")
    
    def execute(self, request: ScheduleGenerationRequest) -> ScheduleGenerationResult:
        """スケジュール生成を実行
        
        Args:
            request: 生成リクエスト
            
        Returns:
            ScheduleGenerationResult: 生成結果
            
        Raises:
            TimetableGenerationError: 生成に失敗した場合
            ConstraintViolationError: 制約違反で解が見つからない場合
        """
        self.logger.info("=== スケジュール生成を開始 ===")
        
        try:
            # ジェネレーターの選択
            generator_class = self._select_generator(request)
            generator_name = generator_class.__name__
            
            self.logger.info(f"使用するジェネレーター: {generator_name}")
            
            # ジェネレーターのインスタンス化と設定
            generator = self._create_generator(generator_class, request)
            
            # 生成実行
            statistics = {}
            iterations_used = 0
            
            if hasattr(generator, 'generate'):
                # 新しいインターフェース
                if generator_class.__name__ == 'UltrathinkPerfectGenerator':
                    # UltrathinkPerfectGeneratorは制約リストが必要
                    constraints = []
                    for constraint in request.constraint_system.get_all_constraints():
                        constraints.append(constraint)
                    
                    result = generator.generate(
                        school=request.school,
                        constraints=constraints,
                        initial_schedule=request.initial_schedule
                    )
                else:
                    result = generator.generate(
                        school=request.school,
                        initial_schedule=request.initial_schedule,
                        max_iterations=request.max_iterations
                    )
                
                if isinstance(result, tuple):
                    schedule, stats = result
                    statistics = stats if isinstance(stats, dict) else {}
                else:
                    schedule = result
                    
                iterations_used = statistics.get('iterations', 0)
                
            else:
                # 旧インターフェース（互換性のため）
                schedule = self._generate_with_legacy_interface(
                    generator, request
                )
            
            # 生成結果の検証
            if not schedule or len(schedule.get_all_assignments()) == 0:
                raise ConstraintViolationError("有効なスケジュールを生成できませんでした")
            
            # 統計情報の収集
            statistics.update({
                'total_assignments': len(schedule.get_all_assignments()),
                'empty_slots': self._count_empty_slots(schedule, request.school),
                'algorithm': generator_name
            })
            
            self.logger.info(
                f"スケジュール生成完了: "
                f"割り当て数={statistics['total_assignments']}, "
                f"空きスロット={statistics['empty_slots']}"
            )
            
            return ScheduleGenerationResult(
                schedule=schedule,
                success=True,
                iterations_used=iterations_used,
                algorithm_used=generator_name,
                statistics=statistics
            )
            
        except ConstraintViolationError:
            raise
        except Exception as e:
            self.logger.error(f"スケジュール生成エラー: {e}")
            raise TimetableGenerationError(f"スケジュール生成に失敗しました: {e}")
    
    def _select_generator(self, request: ScheduleGenerationRequest):
        """リクエストに基づいてジェネレーターを選択
        
        Args:
            request: 生成リクエスト
            
        Returns:
            選択されたジェネレータークラス
        """
        # Unified Hybridフラグが設定されている場合
        if request.use_unified_hybrid:
            self.logger.info("Selecting Unified Hybrid generator")
            # Unified Hybridは別のサービスレイヤーで処理される
            # ここでは一時的にadvanced_cspを返す
            return self._generators['advanced_csp']
        
        # Ultrathinkフラグが設定されている場合
        self.logger.info(f"Generator selection - use_ultrathink: {request.use_ultrathink}, use_advanced_csp: {request.use_advanced_csp}")
        if request.use_ultrathink:
            self.logger.info("Selecting Ultrathink generator")
            return self._generators['ultrathink']
            
        # 明示的な指定がある場合
        if request.search_mode in self._generators:
            return self._generators[request.search_mode]
        
        # フラグに基づく選択
        if request.use_improved_csp:
            return self._generators['improved_csp']
        elif request.use_advanced_csp:
            return self._generators['advanced_csp']
        
        # デフォルトは高度なCSP
        return self._generators['advanced_csp']
    
    def _create_generator(self, generator_class, request: ScheduleGenerationRequest):
        """ジェネレーターのインスタンスを作成し設定
        
        Args:
            generator_class: ジェネレータークラス
            request: 生成リクエスト
            
        Returns:
            設定済みのジェネレーターインスタンス
        """
        # UltrathinkPerfectGeneratorは特別な初期化不要
        if generator_class.__name__ == 'UltrathinkPerfectGenerator':
            return generator_class()
            
        # 制約システムを渡してインスタンス化
        if 'constraint_system' in generator_class.__init__.__code__.co_varnames:
            generator = generator_class(constraint_system=request.constraint_system)
        else:
            generator = generator_class()
            # 制約システムを後から設定
            if hasattr(generator, 'set_constraint_system'):
                generator.set_constraint_system(request.constraint_system)
        
        # オプションの設定
        if hasattr(generator, 'set_options'):
            generator.set_options({
                'enable_jiritsu_priority': request.enable_jiritsu_priority,
                'enable_local_search': request.enable_local_search,
                'max_iterations': request.max_iterations
            })
        
        return generator
    
    def _generate_with_legacy_interface(self, generator, request: ScheduleGenerationRequest) -> Schedule:
        """旧インターフェースでの生成（互換性のため）
        
        Args:
            generator: ジェネレーターインスタンス
            request: 生成リクエスト
            
        Returns:
            生成されたスケジュール
        """
        if hasattr(generator, 'place_all_subjects'):
            # BacktrackJiritsuPlacementServiceなど
            schedule = request.initial_schedule or Schedule()
            generator.place_all_subjects(
                schedule=schedule,
                school=request.school
            )
            return schedule
            
        elif hasattr(generator, 'generate_schedule'):
            # その他の旧形式
            return generator.generate_schedule(
                school=request.school,
                initial_schedule=request.initial_schedule
            )
        
        else:
            raise TimetableGenerationError(
                f"ジェネレーター {type(generator).__name__} は"
                "サポートされていないインターフェースです"
            )
    
    def _count_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きスロット数をカウント
        
        Args:
            schedule: スケジュール
            school: 学校データ
            
        Returns:
            空きスロット数
        """
        total_slots = 0
        assigned_slots = 0
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                from ...domain.value_objects.time_slot import TimeSlot
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    total_slots += 1
                    if schedule.get_assignment(time_slot, class_ref) is not None:
                        assigned_slots += 1
        
        return total_slots - assigned_slots