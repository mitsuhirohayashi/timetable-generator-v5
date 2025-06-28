"""スケジュール生成ユースケース（リファクタリング版 - 薄い協調層）"""
import logging
import time
from typing import Dict

from .request_models import GenerateScheduleRequest, GenerateScheduleResult
from .data_loading_use_case import DataLoadingUseCase
from .constraint_registration_use_case import ConstraintRegistrationUseCase
from .schedule_generation_use_case import ScheduleGenerationUseCase, ScheduleGenerationRequest, ScheduleGenerationResult
from .schedule_optimization_use_case import ScheduleOptimizationUseCase
from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from ...infrastructure.di_container import (
    get_container,
    get_path_manager,
    get_config_loader
)
from ...domain.interfaces.repositories import (
    IScheduleRepository,
    ISchoolRepository,
    ITeacherAbsenceRepository
)
from ...domain.interfaces.followup_parser import IFollowUpParser


class GenerateScheduleUseCase:
    """スケジュール生成のユースケース（薄い協調層）
    
    各種ユースケースを協調させて、スケジュール生成の全体フローを管理する。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        container = get_container()
        
        # DIコンテナから依存を取得
        self.path_manager = get_path_manager()
        self.config_loader = get_config_loader()
        self.schedule_repository = container.resolve(IScheduleRepository)
        self.school_repository = container.resolve(ISchoolRepository)
        self.followup_parser = container.resolve(IFollowUpParser)
        self.teacher_absence_loader = container.resolve(ITeacherAbsenceRepository)
        
        # 設定の初期化
        self.config_loader.initialize_validators()
        
        # 統一制約システム
        self.constraint_system = UnifiedConstraintSystem()
        
        # 各ユースケースの初期化
        self.data_loading_use_case = DataLoadingUseCase(
            school_repository=self.school_repository,
            schedule_repository=self.schedule_repository,
            followup_parser=self.followup_parser,
            teacher_absence_repository=self.teacher_absence_loader,
            data_dir=self.path_manager.data_dir
        )
        
        self.constraint_registration_use_case = ConstraintRegistrationUseCase(
            constraint_system=self.constraint_system,
            data_dir=self.path_manager.data_dir,
            teacher_absence_loader=self.teacher_absence_loader
        )
        
        self.schedule_generation_use_case = ScheduleGenerationUseCase()
        
        self.schedule_optimization_use_case = ScheduleOptimizationUseCase(
            constraint_system=self.constraint_system
        )
    
    def execute(self, request: GenerateScheduleRequest) -> GenerateScheduleResult:
        """スケジュール生成を実行
        
        各ユースケースを協調させて、以下の流れで処理を実行:
        1. データ読み込み（DataLoadingUseCase）
        2. 制約登録（ConstraintRegistrationUseCase）
        3. スケジュール生成（ScheduleGenerationUseCase）
        4. 最適化（ScheduleOptimizationUseCase）
        5. 結果の保存と返却
        """
        start_time = time.time()
        
        try:
            self.logger.info("=== スケジュール生成を開始 ===")
            
            # Step 1: データ読み込み
            self.logger.info("Step 1: データ読み込み")
            school, initial_schedule, followup_data, forbidden_cells = self.data_loading_use_case.execute()
            
            # Step 2: 制約登録
            self.logger.info("Step 2: 制約登録")
            self.constraint_registration_use_case.execute(
                school=school,
                schedule=initial_schedule,
                followup_data=followup_data,
                forbidden_cells=forbidden_cells,
                enable_soft_constraints=request.enable_soft_constraints
            )
            
            # 超最適化ジェネレーターを使用する場合
            self.logger.info(f"[DEBUG] request.use_ultra_optimized = {request.use_ultra_optimized}")
            if request.use_ultra_optimized:
                self.logger.info("Step 3: 超最適化スケジュール生成")
                from ..services.ultra_optimized_generator_service import UltraOptimizedGeneratorService
                
                with UltraOptimizedGeneratorService() as ultra_service:
                    ultra_service.initialize(request.ultra_config)
                    
                    # 制約情報を準備
                    constraints = {
                        'constraint_system': self.constraint_system,
                        'enable_soft_constraints': request.enable_soft_constraints,
                        'fixed_subjects': [
                            "欠", "YT", "学", "学活", "総", "総合",
                            "道", "道徳", "学総", "行", "行事", "テスト", "技家"
                        ],
                        'followup_data': followup_data
                    }
                    
                    from ...domain.entities.schedule import Schedule
                    schedule, metrics = ultra_service.generate(
                        initial_schedule if not request.start_empty else Schedule(),
                        school,
                        constraints,
                        time_limit=300  # 5分
                    )
                    
                    generation_result = ScheduleGenerationResult(
                        schedule=schedule,
                        success=True,
                        message="超最適化生成完了",
                        violations_count=metrics.get('total_violations', 0),
                        statistics=metrics
                    )
            else:
                # 通常のスケジュール生成
                self.logger.info("Step 3: スケジュール生成")
                generation_request = ScheduleGenerationRequest(
                    school=school,
                    initial_schedule=initial_schedule if not request.start_empty else None,
                    constraint_system=self.constraint_system,
                    max_iterations=request.max_iterations,
                    use_advanced_csp=request.use_advanced_csp,
                    use_improved_csp=request.use_improved_csp,
                    use_ultrathink=request.use_ultrathink,
                    use_grade5_priority=request.use_grade5_priority,
                    use_unified_hybrid=request.use_unified_hybrid,
                    search_mode=request.search_mode,
                    enable_jiritsu_priority=True,
                    enable_local_search=True
                )
                generation_result = self.schedule_generation_use_case.execute(generation_request)
            
            if not generation_result.success:
                raise Exception(f"スケジュール生成に失敗: {generation_result.message}")
            
            schedule = generation_result.schedule
            
            # Step 4: 最適化
            self.logger.info("Step 4: 最適化")
            optimization_options = {
                'fill_empty_slots': True,  # 常に空きスロットを埋める
                'optimize_meeting_times': request.optimize_meeting_times,
                'optimize_gym_usage': request.optimize_gym_usage,
                'optimize_workload': request.optimize_workload
            }
            optimization_stats = self.schedule_optimization_use_case.execute(
                schedule=schedule,
                school=school,
                options=optimization_options
            )
            
            # Step 5: 最終検証
            self.logger.info("Step 5: 最終検証")
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            
            # Step 6: 結果の保存
            self.logger.info("Step 6: 結果の保存")
            output_path = self.path_manager.resolve_path(request.output_file)
            self.schedule_repository.save_schedule(schedule, str(output_path))
            
            # 教師別時間割の保存（オプション）
            if request.use_support_hours:
                teacher_schedule_path = output_path.parent / "teacher_schedule.csv"
                self.schedule_repository.save_teacher_schedule(schedule, school, str(teacher_schedule_path))
            
            # 実行時間の計算
            execution_time = time.time() - start_time
            
            # 結果の作成
            return self._create_result(
                schedule=schedule,
                validation_result=validation_result,
                execution_time=execution_time,
                generation_result=generation_result,
                optimization_stats=optimization_stats
            )
            
        except Exception as e:
            return self._handle_error(e, start_time)
    
    def _create_result(
        self,
        schedule,
        validation_result,
        execution_time: float,
        generation_result,
        optimization_stats: Dict[str, int]
    ) -> GenerateScheduleResult:
        """実行結果を作成"""
        violations_count = len(validation_result.violations)
        success = validation_result.is_valid
        
        # メッセージの構築
        message_parts = [
            f"スケジュール生成完了",
            f"割り当て数={len(schedule.get_all_assignments())}",
            f"制約違反={violations_count}件"
        ]
        
        if optimization_stats['empty_slots_filled'] > 0:
            message_parts.append(f"空きスロット埋め={optimization_stats['empty_slots_filled']}個")
        if optimization_stats['meeting_optimized'] > 0:
            message_parts.append(f"会議調整={optimization_stats['meeting_optimized']}件")
        if optimization_stats['gym_conflicts_resolved'] > 0:
            message_parts.append(f"体育配置={optimization_stats['gym_conflicts_resolved']}件")
        if optimization_stats['workload_balanced'] > 0:
            message_parts.append(f"負担改善={optimization_stats['workload_balanced']}件")
        
        message_parts.append(f"実行時間={execution_time:.2f}秒")
        message = ", ".join(message_parts)
        
        self.logger.info(message)
        
        return GenerateScheduleResult(
            schedule=schedule,
            violations_count=violations_count,
            success=success,
            message=message,
            execution_time=execution_time,
            meeting_improvements=optimization_stats.get('meeting_optimized', 0),
            gym_improvements=optimization_stats.get('gym_conflicts_resolved', 0),
            workload_improvements=optimization_stats.get('workload_balanced', 0)
        )
    
    def _handle_error(self, error: Exception, start_time: float) -> GenerateScheduleResult:
        """エラーハンドリング"""
        import traceback
        execution_time = time.time() - start_time
        error_message = f"スケジュール生成エラー: {error}"
        self.logger.error(error_message)
        self.logger.error(f"詳細: {traceback.format_exc()}")
        
        from ...domain.entities.schedule import Schedule
        return GenerateScheduleResult(
            schedule=Schedule(),
            violations_count=-1,
            success=False,
            message=error_message,
            execution_time=execution_time
        )