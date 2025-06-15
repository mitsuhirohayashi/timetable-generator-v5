"""スケジュール生成ユースケース（統合版）"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
import time

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.entities.grade5_unit import Grade5Unit
from ...domain.value_objects.time_slot import TimeSlot
from ...domain.services.unified_constraint_system import UnifiedConstraintSystem, ConstraintPriority
from ...domain.services.teacher_workload_optimizer import TeacherWorkloadOptimizer
from ...domain.services.gym_usage_optimizer import GymUsageOptimizer
from ...domain.services.meeting_time_optimizer import MeetingTimeOptimizer
from ...application.services.schedule_generation_service import ScheduleGenerationService
from ...infrastructure.config.path_manager import get_path_manager
from ...domain.constraints import (
    TeacherAvailabilityConstraint,
    DailySubjectDuplicateConstraint,
    StandardHoursConstraint,
    MondaySixthPeriodConstraint,
    TuesdayPEMultipleConstraint,
    FixedSubjectLockConstraint,
    MeetingLockConstraint,
    TeacherAbsenceConstraint,
    PlacementForbiddenConstraint,
    CellForbiddenSubjectConstraint,
    SubjectValidityConstraint,
    PartTimeTeacherConstraint,
    Grade5SameSubjectConstraint
)
from ...domain.constraints.exchange_class_full_sync_constraint import ExchangeClassFullSyncConstraint
from ...domain.constraints.teacher_conflict_constraint_refactored import TeacherConflictConstraintRefactored
from ...domain.constraints.gym_usage_constraint import GymUsageConstraintRefactored
from ...infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from ...infrastructure.parsers.followup_parser import FollowUpPromptParser
from ...infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
from ...infrastructure.parsers.basics_parser import BasicsParser
from ...domain.services.followup_processor import FollowUpProcessor


@dataclass
class GenerateScheduleRequest:
    """スケジュール生成リクエスト"""
    # ファイル設定
    base_timetable_file: str = "base_timetable.csv"
    desired_timetable_file: str = "input.csv"
    followup_prompt_file: str = "Follow-up.csv"
    basics_file: str = "config/basics.csv"
    output_file: str = "output.csv"
    data_directory: Path = Path(".")
    
    # 基本生成設定
    max_iterations: int = 100
    enable_soft_constraints: bool = True
    use_random: bool = False
    randomness_level: float = 0.3
    exploration_range: int = 10
    start_empty: bool = False
    use_advanced_csp: bool = False
    # fill_empty_slotsは削除されました - 常にTrueとして動作
    
    # 拡張機能フラグ（デフォルトは無効）
    optimize_meeting_times: bool = False  # 会議時間最適化
    optimize_gym_usage: bool = False      # 体育館使用最適化
    optimize_workload: bool = False       # 教師負担最適化
    use_support_hours: bool = False       # 5組時数表記


@dataclass
class GenerateScheduleResult:
    """スケジュール生成結果"""
    schedule: Schedule
    violations_count: int
    success: bool
    message: str
    execution_time: float
    # 最適化結果
    meeting_improvements: int = 0
    gym_improvements: int = 0
    workload_improvements: int = 0


@dataclass
class ValidateScheduleUseCase:
    """スケジュール検証ユースケース"""
    def execute(self, schedule_file: str, data_dir: Path) -> dict:
        """スケジュールを検証"""
        # 簡易実装
        return {"is_valid": True, "violations": []}


class GenerateScheduleUseCase:
    """スケジュール生成のユースケース（統合版）"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.path_manager = get_path_manager()
        
        # 設定の初期化（Grade5チームティーチング教師を含む）
        from ...infrastructure.config.config_loader import ConfigLoader
        config_loader = ConfigLoader(self.path_manager.config_dir)
        config_loader.initialize_validators()
        
        # 統一制約システムの初期化
        self.constraint_system = UnifiedConstraintSystem()
        
        # スケジュール生成サービスの初期化
        self.generation_service = ScheduleGenerationService(
            constraint_system=self.constraint_system,
            path_manager=self.path_manager
        )
        
        # 最適化サービスの初期化（遅延初期化）
        self._workload_optimizer = None
        self._gym_optimizer = None
        self._meeting_optimizer = None
        self._grade5_unit = None
        
        self.school_repo = None
        self.schedule_repo = None
        self.teacher_absences = None
        self.followup_processor = FollowUpProcessor()
    
    @property
    def workload_optimizer(self):
        """教師負担最適化サービス（遅延初期化）"""
        if self._workload_optimizer is None:
            self._workload_optimizer = TeacherWorkloadOptimizer()
        return self._workload_optimizer
    
    @property
    def gym_optimizer(self):
        """体育館使用最適化サービス（遅延初期化）"""
        if self._gym_optimizer is None:
            self._gym_optimizer = GymUsageOptimizer()
        return self._gym_optimizer
    
    @property
    def meeting_optimizer(self):
        """会議時間最適化サービス（遅延初期化）"""
        if self._meeting_optimizer is None:
            self._meeting_optimizer = MeetingTimeOptimizer()
        return self._meeting_optimizer
    
    @property
    def grade5_unit(self):
        """5組ユニット（遅延初期化）"""
        if self._grade5_unit is None:
            self._grade5_unit = Grade5Unit()
        return self._grade5_unit
    
    def execute(self, request: GenerateScheduleRequest) -> GenerateScheduleResult:
        """スケジュール生成を実行"""
        start_time = time.time()
        
        try:
            version_str = "拡張版" if any([
                request.optimize_meeting_times,
                request.optimize_gym_usage,
                request.optimize_workload,
                request.use_support_hours
            ]) else "標準版"
            self.logger.info(f"=== スケジュール生成ユースケースを開始（{version_str}） ===")
            
            # Step 1: データの読み込み
            self.school_repo = CSVSchoolRepository(request.data_directory)
            
            # リポジトリの初期化（拡張機能の有無に応じて）
            use_enhanced_features = request.use_support_hours
            self.schedule_repo = CSVScheduleRepository(
                request.data_directory,
                use_enhanced_features=use_enhanced_features,
                use_support_hours=request.use_support_hours
            )
            
            if request.use_support_hours:
                self.logger.info("5組時数表記対応機能を有効化")
            
            self.logger.info("学校データを読み込み中...")
            school = self.school_repo.load_school_data(request.base_timetable_file)
            
            # Step 2: 週次要望の読み込み（制約登録前に実行）
            weekly_requirements = self._load_weekly_requirements(request, school)
            
            # Step 2.5: Follow-up処理（テスト期間保護など）
            followup_result = self.followup_processor.process_followup_file(
                self.path_manager.resolve_path(request.followup_prompt_file)
            )
            
            # Step 3: 基本制約の読み込みと登録（教師不在情報を含む）
            self._load_and_register_constraints(request)
            
            # Step 4: 希望時間割の読み込み
            initial_schedule = self._load_initial_schedule(request, school)
            
            # Step 4.5: テスト期間をスケジュールで保護（科目は変更せず）
            if initial_schedule and followup_result.get("test_periods"):
                self.followup_processor.protect_test_periods_in_schedule(initial_schedule, school)
                self.followup_processor.mark_schedule_as_protected(initial_schedule)
            
            # Step 5: スケジュール生成
            if initial_schedule:
                # 会議ロックセルを適用
                self._apply_meeting_locks(initial_schedule, school)
                
                # 週次要望を適用
                self._apply_weekly_requirements_to_schedule(initial_schedule, school, weekly_requirements)
                
                # 教員不在の授業を事前に削除
                self._remove_unavailable_teacher_assignments(initial_schedule, school)
                
                # 5組の時数表記を適用
                if request.use_support_hours:
                    self._apply_support_hours_to_grade5(initial_schedule, school)
            
            # 統一生成サービスを使用
            schedule = self.generation_service.generate_schedule(
                school=school,
                initial_schedule=initial_schedule,
                max_iterations=request.max_iterations,
                use_advanced_csp=request.use_advanced_csp
            )
            
            # Step 6: 最適化処理（フラグに応じて実行）
            meeting_improvements = 0
            gym_improvements = 0
            workload_improvements = 0
            
            # 会議時間最適化
            if request.optimize_meeting_times:
                self.logger.info("=== 会議時間・教師不在の最適化を開始 ===")
                optimized_schedule, improvements = self.meeting_optimizer.optimize_meeting_times(
                    schedule, school
                )
                schedule = optimized_schedule
                meeting_improvements = improvements
                self.logger.info(f"会議時間最適化完了: {improvements}件の変更")
            
            # 体育館使用最適化
            if request.optimize_gym_usage:
                self.logger.info("=== 体育館使用の最適化を開始 ===")
                optimized_schedule, improvements = self.gym_optimizer.optimize_gym_usage(
                    schedule, school
                )
                schedule = optimized_schedule
                gym_improvements = improvements
                self.logger.info(f"体育館使用最適化完了: {improvements}件の変更")
            
            # 教師負担バランス最適化
            if request.optimize_workload:
                self.logger.info("=== 教師負担バランス最適化を開始 ===")
                optimized_schedule, improvements = self.workload_optimizer.optimize_workload(
                    schedule, school, max_iterations=50
                )
                schedule = optimized_schedule
                workload_improvements = improvements
                self.logger.info(f"教師負担バランス最適化完了: {improvements}件改善")
            
            # Step 7: 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            violations_count = len(validation_result.violations)
            
            # Step 8: 結果の保存
            output_path = self.path_manager.resolve_path(request.output_file)
            self.schedule_repo.save_schedule(schedule, str(output_path))
            
            # 教師別時間割も保存（拡張機能使用時）
            if use_enhanced_features:
                teacher_schedule_path = output_path.parent / "teacher_schedule.csv"
                self.schedule_repo.save_teacher_schedule(schedule, school, str(teacher_schedule_path))
            
            execution_time = time.time() - start_time
            
            # 結果メッセージの構築
            success = validation_result.is_valid
            message_parts = [
                f"スケジュール生成完了: ",
                f"割り当て数={len(schedule.get_all_assignments())}",
                f"制約違反={violations_count}件"
            ]
            
            if meeting_improvements > 0:
                message_parts.append(f"会議調整={meeting_improvements}件")
            if gym_improvements > 0:
                message_parts.append(f"体育配置={gym_improvements}件")
            if workload_improvements > 0:
                message_parts.append(f"負担改善={workload_improvements}件")
            
            message_parts.append(f"実行時間={execution_time:.2f}秒")
            message = ", ".join(message_parts)
            
            self.logger.info(message)
            
            # 統計情報の出力
            self.constraint_system.log_statistics()
            
            return GenerateScheduleResult(
                schedule=schedule,
                violations_count=violations_count,
                success=success,
                message=message,
                execution_time=execution_time,
                meeting_improvements=meeting_improvements,
                gym_improvements=gym_improvements,
                workload_improvements=workload_improvements
            )
            
        except Exception as e:
            import traceback
            execution_time = time.time() - start_time
            error_message = f"スケジュール生成エラー: {e}"
            self.logger.error(error_message)
            self.logger.error(f"詳細: {traceback.format_exc()}")
            
            return GenerateScheduleResult(
                schedule=Schedule(),
                violations_count=-1,
                success=False,
                message=error_message,
                execution_time=execution_time
            )
    
    def _load_and_register_constraints(self, request: GenerateScheduleRequest) -> None:
        """制約を読み込んで統一システムに登録"""
        # 新しい統合制約ローダーを使用
        from ...infrastructure.config.constraint_loader import constraint_loader
        
        self.logger.info("制約条件を読み込み中...")
        
        # basics.csvとFollow-up.csvから制約を読み込み
        all_constraints = constraint_loader.load_all_constraints()
        
        # 各制約を統一システムに登録
        for constraint in all_constraints:
            # 制約の優先度を取得（デフォルトはHIGH）
            priority = getattr(constraint, 'priority', ConstraintPriority.HIGH)
            self.constraint_system.register_constraint(constraint, priority)
        
        self.logger.info(f"制約を{len(all_constraints)}件登録しました")
        
        # 追加の制約（互換性のため）
        # 教師不在制約（自然言語パーサーから取得した情報を使用）
        if self.teacher_absences:
            self.constraint_system.register_constraint(
                TeacherAbsenceConstraint(self.teacher_absences), ConstraintPriority.CRITICAL
            )
        
        # 固定教科ロック制約（初期スケジュールベース）
        if request.desired_timetable_file and not request.start_empty:
            try:
                initial_schedule = self.schedule_repo.load_desired_schedule(
                    request.desired_timetable_file, None
                )
                self.constraint_system.register_constraint(
                    FixedSubjectLockConstraint(initial_schedule), 
                    ConstraintPriority.CRITICAL
                )
                self.logger.info("固定教科ロック制約を追加")
            except:
                pass
        
        # セル別配置禁止制約
        if self.schedule_repo and hasattr(self.schedule_repo, 'get_forbidden_cells'):
            forbidden_cells = self.schedule_repo.get_forbidden_cells()
            if forbidden_cells:
                self.constraint_system.register_constraint(
                    CellForbiddenSubjectConstraint(forbidden_cells),
                    ConstraintPriority.MEDIUM
                )
                self.logger.info(f"セル別配置禁止制約を追加: {len(forbidden_cells)}セル")
        
        # LOW制約（ソフト制約）
        if request.enable_soft_constraints:
            self.constraint_system.register_constraint(
                StandardHoursConstraint(), ConstraintPriority.LOW
            )
            self.logger.info("ソフト制約を有効化")
    
    def _load_weekly_requirements(self, request: GenerateScheduleRequest, school: School) -> List:
        """週次要望を読み込み"""
        self.logger.info("週次要望を読み込み中...")
        
        # 自然言語パーサーを試行
        natural_parser = NaturalFollowUpParser(request.data_directory)
        natural_result = natural_parser.parse_file(request.followup_prompt_file)
        
        if natural_result["parse_success"]:
            self.logger.info("自然言語形式のFollow-upを解析しました")
            summary = natural_parser.get_summary(natural_result)
            self.logger.info(f"解析結果:\n{summary}")
            
            # 自然言語形式の要望を学校データに適用
            self._apply_natural_requirements_to_school(school, natural_result)
            
            # 教師不在情報を保存（制約システムで使用）
            if natural_result.get("teacher_absences"):
                self.teacher_absences = natural_result["teacher_absences"]
            
            return []
        else:
            # 旧形式のパーサーにフォールバック
            self.logger.info("旧形式のFollow-upパーサーを使用")
            followup_parser = FollowUpPromptParser(request.data_directory)
            weekly_requirements = followup_parser.parse_requirements(request.followup_prompt_file)
            
            # 学校データに週次要望を適用
            self._apply_weekly_requirements_to_school(school, weekly_requirements)
            
            return weekly_requirements
    
    def _load_initial_schedule(self, request: GenerateScheduleRequest, school: School) -> Optional[Schedule]:
        """初期スケジュールを読み込み"""
        if request.start_empty:
            self.logger.info("--start-emptyオプションが指定されたため、空の時間割から生成を開始します")
            return None
        
        try:
            self.logger.info("希望時間割を読み込み中...")
            
            # 入力ファイルの前処理を実行
            input_path = self.path_manager.resolve_path(request.desired_timetable_file)
            if input_path.exists():
                # 入力データの事前修正
                from ...domain.services.input_data_corrector import InputDataCorrector
                corrector = InputDataCorrector()
                corrected_path = input_path.parent / "corrected_input.csv"
                # TODO: Implement correct_input_file method
                # if corrector.correct_input_file(input_path, corrected_path):
                #     input_path = corrected_path
                #     self.logger.info("入力データを事前修正しました")
                
                from ...infrastructure.parsers.input_preprocessor import InputPreprocessor
                preprocessor = InputPreprocessor()
                
                # 特殊割り当ての抽出
                special_assignments = preprocessor.extract_special_assignments(input_path)
                if special_assignments:
                    self.logger.info(f"特殊割り当てを検出: {len(special_assignments)}件")
                    # 特殊割り当てを別途処理するためのフラグを設定
                    self._special_assignments = special_assignments
                
                # CSVファイルの前処理
                preprocessed_path = preprocessor.preprocess_csv(input_path)
                
                # 前処理済みファイルから読み込み
                initial_schedule = self.schedule_repo.load_desired_schedule(
                    str(preprocessed_path.relative_to(self.path_manager.data_dir)), school
                )
            else:
                initial_schedule = self.schedule_repo.load_desired_schedule(
                    request.desired_timetable_file, school
                )
            
            self.logger.info(f"希望時間割を読み込みました: {len(initial_schedule.get_all_assignments())}件の割り当て")
            
            # 特殊割り当てを適用
            if hasattr(self, '_special_assignments') and self._special_assignments:
                self._apply_special_assignments(initial_schedule, school)
            
            return initial_schedule
        except Exception as e:
            self.logger.warning(f"希望時間割の読み込みに失敗、新規生成します: {e}")
            return None
    
    def _apply_meeting_locks(self, schedule: Schedule, school: School) -> None:
        """会議ロックを適用"""
        # TODO: 実際の会議ロック処理の実装
        pass
    
    def _apply_weekly_requirements_to_schedule(self, schedule: Schedule, school: School, weekly_requirements: List) -> None:
        """週次要望をスケジュールに適用"""
        # TODO: 実際の週次要望適用処理の実装
        pass
    
    def _remove_unavailable_teacher_assignments(self, schedule: Schedule, school: School) -> None:
        """教員不在の授業を削除"""
        removed_count = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                unavailable_teachers = school.get_unavailable_teachers(day, period)
                
                if not unavailable_teachers:
                    continue
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher and assignment.teacher.name in unavailable_teachers:
                        if not schedule.is_locked(time_slot, class_ref):
                            schedule.remove_assignment(time_slot, class_ref)
                            removed_count += 1
                            self.logger.debug(
                                f"削除: {time_slot} {class_ref} - "
                                f"{assignment.teacher.name}先生は不在"
                            )
        
        if removed_count > 0:
            self.logger.info(f"教員不在による授業を{removed_count}件削除しました")
    
    def _apply_natural_requirements_to_school(self, school: School, natural_result: Dict) -> None:
        """自然言語形式の要望を学校データに適用"""
        # 教員不在情報の適用
        if natural_result.get("teacher_absences"):
            for absence in natural_result["teacher_absences"]:
                teacher_name = absence.teacher_name
                day = absence.day
                # periodsは複数の場合がある、空リストの場合は終日
                periods = absence.periods if absence.periods else list(range(1, 7))
                
                # Teacherオブジェクトを作成（教員名のみで検索）
                from ...domain.value_objects.time_slot import Teacher
                teacher = Teacher(teacher_name)
                
                for period in periods:
                    # 教員不在情報の登録
                    school.set_teacher_unavailable(day, period, teacher)
                    self.logger.info(f"教員不在情報を登録: {teacher_name}先生 - {day}曜{period}時限")
        
        # 会議情報の適用（会議参加メンバーのみが不在）
        if natural_result.get("meetings"):
            for meeting in natural_result["meetings"]:
                meeting_type = meeting.meeting_type
                day = meeting.day
                periods = meeting.periods if hasattr(meeting, 'periods') else [meeting.period]
                
                for period in periods:
                    # 会議時間情報のログ出力のみ（実際の登録は別の場所で行われる）
                    self.logger.info(f"会議時間情報: {meeting_type} - {day}曜{period}時限")
    
    def _apply_weekly_requirements_to_school(self, school: School, weekly_requirements: List) -> None:
        """週次要望を学校データに適用"""
        # 実装は既存のロジックを使用
        for req in weekly_requirements:
            if hasattr(req, 'teacher_name') and hasattr(req, 'day') and hasattr(req, 'period'):
                # 教員不在情報のログ出力のみ（実際の登録は別の場所で行われる）
                self.logger.info(f"教員不在情報: {req.teacher_name}先生 - {req.day}曜{req.period}時限")
    
    def _apply_support_hours_to_grade5(self, schedule: Schedule, school: School) -> None:
        """5組に時数表記を適用"""
        if not self._grade5_unit:
            return
        
        # Grade5Unitを使用して時数表記を適用
        self.logger.info("5組の時数表記を適用中...")
        # TODO: 実際の時数表記適用処理
    
    def _apply_special_assignments(self, schedule: Schedule, school: School) -> None:
        """特殊割り当て（17自、26自など）を適用"""
        if not hasattr(self, '_special_assignments') or not self._special_assignments:
            return
        
        from ...domain.value_objects.time_slot import TimeSlot, Subject, Teacher
        from ...domain.value_objects.assignment import Assignment
        from ...domain.utils import parse_class_reference
        
        self.logger.info("特殊割り当てを適用中...")
        applied_count = 0
        
        for (day, period), class_assignments in self._special_assignments.items():
            time_slot = TimeSlot(day, period)
            
            for class_ref_str, subject_name in class_assignments.items():
                class_ref = parse_class_reference(class_ref_str)
                if not class_ref:
                    self.logger.warning(f"無効なクラス参照: {class_ref_str}")
                    continue
                
                try:
                    # 教科を作成
                    subject = Subject(subject_name)
                    
                    # 教員を取得
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    if not teacher:
                        teacher = Teacher(f"{subject_name}担当")
                    
                    # 割り当てを作成
                    assignment = Assignment(class_ref, subject, teacher)
                    
                    # スケジュールに割り当て
                    schedule.assign(time_slot, assignment)
                    applied_count += 1
                    
                    self.logger.debug(
                        f"特殊割り当て適用: {time_slot} {class_ref} -> {subject_name}"
                    )
                    
                except ValueError as e:
                    self.logger.warning(f"特殊割り当ての適用エラー: {e}")
        
        if applied_count > 0:
            self.logger.info(f"特殊割り当てを{applied_count}件適用しました")