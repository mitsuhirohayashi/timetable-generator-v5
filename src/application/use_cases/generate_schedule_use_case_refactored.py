"""スケジュール生成ユースケース（リファクタリング版）"""
import logging
import time
from typing import Tuple

from .request_models import GenerateScheduleRequest, GenerateScheduleResult
from ..services.constraint_registration_service import ConstraintRegistrationService
from ..services.data_loading_service import DataLoadingService
from ..services.optimization_orchestration_service import OptimizationOrchestrationService
from ..services.schedule_generation_service import ScheduleGenerationService
from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.entities.grade5_unit import Grade5Unit
from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem, ValidationResult
from ...infrastructure.di_container import (
    get_path_manager,
    get_config_loader
)


class GenerateScheduleUseCaseRefactored:
    """スケジュール生成のユースケース（リファクタリング版）
    
    単一責任原則に従い、以下の責任を他のサービスに委譲：
    - データ読み込み: DataLoadingService
    - 制約登録: ConstraintRegistrationService
    - 最適化: OptimizationOrchestrationService
    - 生成処理: ScheduleGenerationService
    
    このクラスは全体のオーケストレーションのみを担当します。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.path_manager = get_path_manager()
        
        # 依存サービスの初期化
        self.data_loading_service = DataLoadingService()
        self.constraint_registration_service = ConstraintRegistrationService()
        self.optimization_service = OptimizationOrchestrationService()
        
        # 統一制約システムの初期化
        self.constraint_system = UnifiedConstraintSystem()
        
        # スケジュール生成サービスの初期化（学習ルールサービスは後で設定）
        self.generation_service = None
        
        # Grade5ユニットの初期化（遅延）
        self._grade5_unit = None
        
        # 設定の初期化
        self._initialize_configuration()
    
    @property
    def grade5_unit(self):
        """5組ユニット（遅延初期化）"""
        if self._grade5_unit is None:
            self._grade5_unit = Grade5Unit()
        return self._grade5_unit
    
    def execute(self, request: GenerateScheduleRequest) -> GenerateScheduleResult:
        """スケジュール生成を実行
        
        高レベルのオーケストレーションのみを担当し、
        具体的な処理は各サービスに委譲します。
        """
        start_time = time.time()
        
        try:
            self._log_execution_start(request)
            
            # Step 1: データの読み込み
            school, use_enhanced_features = self._load_data(request)
            
            # Step 2: 制約の登録
            teacher_absences = self._register_constraints(request, school)
            
            # Step 3: 初期スケジュールの準備
            initial_schedule = self._prepare_initial_schedule(request, school)
            
            # Step 4: スケジュール生成
            generated_schedule = self._generate_schedule(
                request, school, initial_schedule
            )
            
            # Step 5: 最適化処理
            optimized_schedule, optimization_results = self._apply_optimizations(
                request, generated_schedule, school
            )
            
            # Step 6: 最終検証と保存
            validation_result = self._finalize_schedule(
                request, optimized_schedule, school, use_enhanced_features
            )
            
            # Step 7: 結果の作成
            execution_time = time.time() - start_time
            return self._create_success_result(
                optimized_schedule, validation_result, 
                execution_time, optimization_results
            )
            
        except Exception as e:
            return self._create_error_result(e, start_time)
    
    def _initialize_configuration(self) -> None:
        """設定の初期化"""
        config_loader = get_config_loader()
        config_loader.initialize_validators()
    
    def _log_execution_start(self, request: GenerateScheduleRequest) -> None:
        """実行開始ログ"""
        self.logger.info("=" * 80)
        self.logger.info("スケジュール生成を開始します（v3.0 - リファクタリング版）")
        self.logger.info(f"データディレクトリ: {request.data_directory}")
        if request.use_unified_hybrid:
            algorithm_name = "Unified Hybrid"
        elif request.use_ultrathink:
            algorithm_name = "Ultrathink"
        elif request.use_advanced_csp:
            algorithm_name = "Advanced CSP"
        else:
            algorithm_name = "Legacy"
        self.logger.info(f"アルゴリズム: {algorithm_name}")
        self.logger.info(f"最大反復回数: {request.max_iterations}")
        
        # 有効な最適化オプションをログ出力
        optimizations = []
        if request.optimize_meeting_times:
            optimizations.append("会議時間")
        if request.optimize_gym_usage:
            optimizations.append("体育館使用")
        if request.optimize_workload:
            optimizations.append("教師負担")
        
        if optimizations:
            self.logger.info(f"最適化: {', '.join(optimizations)}")
        
        self.logger.info("=" * 80)
    
    def _load_data(
        self, 
        request: GenerateScheduleRequest
    ) -> Tuple[School, bool]:
        """データを読み込む"""
        return self.data_loading_service.load_school_data(request.data_directory)
    
    def _register_constraints(
        self,
        request: GenerateScheduleRequest,
        school: School
    ) -> dict:
        """制約を登録し、教師不在情報を返す"""
        # 週次要望を読み込み
        weekly_requirements, teacher_absences = self.data_loading_service.load_weekly_requirements(
            request.data_directory, school
        )
        
        # 制約を登録
        self.constraint_registration_service.register_all_constraints(
            self.constraint_system,
            request.data_directory,
            teacher_absences
        )
        
        # スケジュール生成サービスを初期化（学習ルールサービスを共有）
        if self.generation_service is None:
            self.generation_service = ScheduleGenerationService(
                constraint_system=self.constraint_system,
                path_manager=self.path_manager,
                learned_rule_service=self.constraint_registration_service.learned_rule_service
            )
        
        return teacher_absences
    
    def _prepare_initial_schedule(
        self,
        request: GenerateScheduleRequest,
        school: School
    ) -> Schedule:
        """初期スケジュールを準備"""
        initial_schedule = self.data_loading_service.load_initial_schedule(
            request.data_directory,
            request.desired_timetable_file,
            request.start_empty,
            validate=True  # 初期スケジュールの検証を有効化
        )
        
        # 初期スケジュールがない場合は空のスケジュールを作成
        if initial_schedule is None:
            initial_schedule = Schedule()
        
        # 教師不在による授業を削除（テスト期間と固定科目を除く）
        if initial_schedule:
            self._remove_unavailable_teacher_assignments(initial_schedule, school)
        
        # 5組ユニットの設定は既に初期化済み
        
        return initial_schedule
    
    def _generate_schedule(
        self,
        request: GenerateScheduleRequest,
        school: School,
        initial_schedule: Schedule
    ) -> Schedule:
        """スケジュールを生成"""
        self.logger.info("スケジュール生成を開始...")
        self.logger.info(f"[DEBUG] use_unified_hybrid={request.use_unified_hybrid}")
        self.logger.info(f"[DEBUG] use_ultra_optimized={getattr(request, 'use_ultra_optimized', False)}")
        
        # 超最適化ジェネレーターを使用する場合
        if getattr(request, 'use_ultra_optimized', False):
            self.logger.info("超最適化スケジュール生成を使用します")
            from ..services.ultra_optimized_generator_service import UltraOptimizedGeneratorService
            
            with UltraOptimizedGeneratorService() as ultra_service:
                ultra_config = getattr(request, 'ultra_config', {})
                ultra_service.initialize(ultra_config)
                
                # 制約情報を準備
                constraints = {
                    'constraint_system': self.constraint_system,
                    'enable_soft_constraints': getattr(request, 'enable_soft_constraints', True),
                    'fixed_subjects': [
                        "欠", "YT", "学", "学活", "総", "総合",
                        "道", "道徳", "学総", "行", "行事", "テスト", "技家"
                    ]
                }
                
                schedule, metrics = ultra_service.generate(
                    initial_schedule,
                    school,
                    constraints,
                    time_limit=300  # 5分
                )
                
                return schedule
        
        # 通常のスケジュール生成
        return self.generation_service.generate_schedule(
            school=school,
            initial_schedule=initial_schedule,
            strategy=request.strategy,
            max_iterations=request.max_iterations,
            search_mode=request.search_mode
        )
    
    def _apply_optimizations(
        self,
        request: GenerateScheduleRequest,
        schedule: Schedule,
        school: School
    ) -> Tuple[Schedule, dict]:
        """最適化を適用"""
        return self.optimization_service.apply_optimizations(
            schedule=schedule,
            school=school,
            optimize_meeting_times=request.optimize_meeting_times,
            optimize_gym_usage=request.optimize_gym_usage,
            optimize_workload=request.optimize_workload
        )
    
    def _finalize_schedule(
        self,
        request: GenerateScheduleRequest,
        schedule: Schedule,
        school: School,
        use_enhanced_features: bool
    ) -> ValidationResult:
        """最終検証と保存"""
        # 検証
        validation_result = self.constraint_system.validate_schedule(schedule, school)
        
        # リポジトリを取得
        _, schedule_repo = self.data_loading_service.get_repositories(request.data_directory)
        
        # 結果の保存
        output_path = self.path_manager.resolve_path(request.output_file)
        schedule_repo.save(schedule, str(output_path))
        
        # 教師別時間割も保存（拡張機能使用時）
        if use_enhanced_features:
            teacher_schedule_path = output_path.parent / "teacher_schedule.csv"
            schedule_repo.save_teacher_schedule(schedule, school, str(teacher_schedule_path))
        
        # 統計情報の出力
        self.constraint_system.log_statistics()
        
        return validation_result
    
    def _create_success_result(
        self,
        schedule: Schedule,
        validation_result: ValidationResult,
        execution_time: float,
        optimization_results: dict
    ) -> GenerateScheduleResult:
        """成功時の結果を作成"""
        violations_count = len(validation_result.violations)
        
        # メッセージの構築
        message_parts = [
            f"スケジュール生成完了: ",
            f"割り当て数={len(schedule.get_all_assignments())}",
            f"制約違反={violations_count}件"
        ]
        
        if optimization_results['meeting_improvements'] > 0:
            message_parts.append(f"会議調整={optimization_results['meeting_improvements']}件")
        if optimization_results['gym_improvements'] > 0:
            message_parts.append(f"体育配置={optimization_results['gym_improvements']}件")
        if optimization_results['workload_improvements'] > 0:
            message_parts.append(f"負担改善={optimization_results['workload_improvements']}件")
        
        message_parts.append(f"実行時間={execution_time:.2f}秒")
        message = ", ".join(message_parts)
        
        self.logger.info(message)
        
        return GenerateScheduleResult(
            schedule=schedule,
            violations_count=violations_count,
            success=validation_result.is_valid,
            message=message,
            execution_time=execution_time,
            **optimization_results
        )
    
    def _create_error_result(
        self, 
        error: Exception, 
        start_time: float
    ) -> GenerateScheduleResult:
        """エラー時の結果を作成"""
        import traceback
        execution_time = time.time() - start_time
        error_message = f"スケジュール生成エラー: {error}"
        
        self.logger.error(error_message)
        self.logger.error(f"詳細: {traceback.format_exc()}")
        
        return GenerateScheduleResult(
            schedule=Schedule(),
            violations_count=-1,
            success=False,
            message=error_message,
            execution_time=execution_time
        )
    
    def _remove_unavailable_teacher_assignments(self, schedule: Schedule, school: School) -> None:
        """教員不在の授業を削除（テスト期間と固定科目を除く）"""
        removed_count = 0
        skipped_count = 0
        
        # TimeSlotのインポート
        from ...domain.value_objects.time_slot import TimeSlot
        
        # テスト期間チェック用のProtectorを初期化
        from ...domain.services.core.test_period_protector import TestPeriodProtector
        test_protector = TestPeriodProtector()
        
        # 固定科目のリストを取得
        from ...infrastructure.di_container import get_csp_configuration
        csp_config = get_csp_configuration()
        # CSPConfigurationAdapterから直接パラメータを取得
        all_params = csp_config.get_all_parameters()
        fixed_subjects = set(all_params.get('fixed_subjects', ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]))
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間の場合はスキップ
                if test_protector.is_test_period(time_slot):
                    self.logger.debug(f"テスト期間のためスキップ: {time_slot}")
                    continue
                
                unavailable_teachers = school.get_unavailable_teachers(day, period)
                
                if not unavailable_teachers:
                    continue
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher and assignment.teacher.name in unavailable_teachers:
                        # 固定科目の場合はスキップ
                        if assignment.subject.name in fixed_subjects:
                            self.logger.debug(f"固定科目のためスキップ: {time_slot} {class_ref} - {assignment.subject.name}")
                            skipped_count += 1
                            continue
                            
                        if not schedule.is_locked(time_slot, class_ref):
                            schedule.remove_assignment(time_slot, class_ref)
                            removed_count += 1
                            self.logger.debug(
                                f"削除: {time_slot} {class_ref} - "
                                f"{assignment.teacher.name}先生は不在"
                            )
                        else:
                            skipped_count += 1
        
        if removed_count > 0 or skipped_count > 0:
            self.logger.info(
                f"教員不在による授業を{removed_count}件削除、"
                f"{skipped_count}件は保護のためスキップしました"
            )