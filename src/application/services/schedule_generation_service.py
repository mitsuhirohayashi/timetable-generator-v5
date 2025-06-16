"""スケジュール生成サービス

高度なCSPアルゴリズムを使用した時間割生成を管理するサービス。
このサービスは時間割生成の中心的な役割を担い、アルゴリズムの選択、
制約の管理、空きスロットの埋め込みなどを統合的に処理します。
"""
import logging
from typing import Optional, Dict, List, TYPE_CHECKING, Any
from datetime import datetime

if TYPE_CHECKING:
    from ...domain.entities.schedule import Schedule
    from ...domain.entities.school import School
    from ...domain.entities.class_reference import ClassReference
    from ...domain.value_objects.constraint_violation import ConstraintViolation
    from ...domain.services.unified_constraint_system import UnifiedConstraintSystem
    from ...infrastructure.config.path_manager import PathManager

class ScheduleGenerationService:
    """スケジュール生成サービス
    
    時間割生成の統合的な管理を行うサービスクラス。
    高度なCSPアルゴリズムとレガシーアルゴリズムの両方をサポートし、
    空きスロットの自動埋め込み機能も提供します。
    
    Attributes:
        constraint_system: 制約システム
        path_manager: パス管理
        logger: ロガー
        generation_stats: 生成統計情報
    """
    
    def __init__(self, 
                 constraint_system: 'UnifiedConstraintSystem',
                 path_manager: 'PathManager') -> None:
        """ScheduleGenerationServiceを初期化
        
        Args:
            constraint_system: 統一制約システムのインスタンス
            path_manager: パス管理のインスタンス
        """
        self.constraint_system = constraint_system
        self.path_manager = path_manager
        self.logger = logging.getLogger(__name__)
        
        # 統計情報の初期化
        self.generation_stats: Dict[str, Any] = {
            'start_time': None,
            'end_time': None,
            'iterations': 0,
            'assignments_made': 0,
            'assignments_failed': 0,
            'violations_fixed': 0,
            'final_violations': 0,
            'empty_slots_filled': 0,
            'algorithm_used': 'advanced_csp'
        }
    
    def generate_schedule(self, 
                         school: 'School',
                         initial_schedule: Optional['Schedule'] = None,
                         max_iterations: int = 100,
                         use_advanced_csp: bool = True,
                         ) -> 'Schedule':
        """スケジュールを生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            max_iterations: 最大反復回数
            use_advanced_csp: 高度なCSPアルゴリズムを使用するか（デフォルト: True）
            
        Returns:
            Schedule: 生成されたスケジュール
        """
        self.logger.info("=== スケジュール生成を開始 ===")
        self.generation_stats['start_time'] = datetime.now()
        
        try:
            if use_advanced_csp:
                # 高度なCSPアルゴリズムを使用（デフォルト）
                self.logger.info("高度なCSPアルゴリズムを使用してスケジュールを生成します")
                self.generation_stats['algorithm_used'] = 'advanced_csp'
                schedule = self._generate_with_advanced_csp(school, max_iterations, initial_schedule)
            else:
                # レガシーアルゴリズムを使用
                self.logger.info("レガシーアルゴリズムを使用してスケジュールを生成します")
                self.generation_stats['algorithm_used'] = 'legacy'
                schedule = self._generate_with_legacy_algorithm(school, max_iterations, initial_schedule)
            
            # 最終検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            self.generation_stats['final_violations'] = len(validation_result.violations)
            
            if not validation_result.is_valid:
                self.logger.warning(
                    f"生成完了しましたが、{len(validation_result.violations)}件の"
                    f"制約違反が残っています"
                )
                self._log_violations(validation_result.violations[:10])
            else:
                self.logger.info("すべての制約を満たすスケジュールを生成しました")
            
            return schedule
            
        finally:
            self.generation_stats['end_time'] = datetime.now()
            self._log_statistics()
    
    def _generate_with_advanced_csp(self, school: 'School', 
                                    max_iterations: int,
                                    initial_schedule: Optional['Schedule']) -> 'Schedule':
        """高度なCSPアルゴリズムでスケジュールを生成"""
        # 入力データの補正（初期スケジュールがある場合）
        if initial_schedule:
            from ...domain.services.input_data_corrector import InputDataCorrector
            corrector = InputDataCorrector()
            corrections = corrector.correct_input_schedule(initial_schedule, school)
            if corrections > 0:
                self.logger.info(f"入力データを{corrections}箇所補正しました")
        
        # CSPOrchestratorを直接使用（ファサードを経由せず）
        from ...domain.services.csp_orchestrator import CSPOrchestrator
        
        # ConstraintValidatorアダプターを作成
        class ConstraintValidatorAdapter:
            def __init__(self, unified_system):
                self.unified_system = unified_system
            
            def check_assignment(self, schedule, school, time_slot, assignment):
                """UnifiedConstraintSystemのcheck_before_assignmentメソッドをConstraintValidatorインターフェースに適合させる"""
                from ...domain.services.unified_constraint_system import AssignmentContext
                context = AssignmentContext(
                    schedule=schedule,
                    school=school,
                    time_slot=time_slot,
                    assignment=assignment
                )
                result, _ = self.unified_system.check_before_assignment(context)
                return result
            
            def validate_all(self, schedule, school):
                """スケジュール全体の検証"""
                validation_result = self.unified_system.validate_schedule(schedule, school)
                return validation_result.violations
        
        # アダプターを使ってCSPOrchestratorを作成
        adapter = ConstraintValidatorAdapter(self.constraint_system)
        csp_orchestrator = CSPOrchestrator(adapter)
        
        # 生成実行
        schedule = csp_orchestrator.generate(school, max_iterations, initial_schedule)
        
        # 統計情報を更新
        self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
        
        # 空きスロット埋め（常に実行）
        self._fill_empty_slots_smartly(schedule, school)
        
        return schedule
    
    def _generate_with_legacy_algorithm(self, school: 'School',
                                      max_iterations: int,
                                      initial_schedule: Optional['Schedule']) -> 'Schedule':
        """レガシーアルゴリズムでスケジュールを生成"""
        # 1. 初期スケジュールの準備
        if initial_schedule:
            schedule = self._prepare_initial_schedule(initial_schedule, school)
        else:
            from ...domain.entities.schedule import Schedule
            schedule = Schedule()
        
        # 2. 必須配置の実行
        self._place_required_subjects(schedule, school)
        
        # 3. 空きコマの埋め込み
        self._fill_empty_slots(schedule, school)
        
        # 4. 制約違反の修正
        self._fix_violations(schedule, school, max_iterations)
        
        return schedule
    
    def _prepare_initial_schedule(self, initial_schedule: 'Schedule', 
                                 school: 'School') -> 'Schedule':
        """初期スケジュールの準備
        
        初期スケジュールをコピーし、固定教科のロックと初期違反の削除を行います。
        
        Args:
            initial_schedule: 元となる初期スケジュール
            school: 学校情報
            
        Returns:
            準備された初期スケジュール（元のスケジュールは変更されません）
        """
        self.logger.info("初期スケジュールを準備中...")
        
        # 初期スケジュールのコピーを作成
        schedule = self._copy_schedule(initial_schedule)
        
        # 固定教科のロック
        self._lock_fixed_subjects(schedule)
        
        # 初期違反の削除
        self._remove_initial_violations(schedule, school)
        
        return schedule
    
    def _place_required_subjects(self, schedule: 'Schedule', school: 'School') -> None:
        """必須教科の配置"""
        self.logger.info("必須教科を配置中...")
        
        # 各クラスの必須教科を配置
        for class_ref in school.get_all_classes():
            self._place_class_requirements(schedule, school, class_ref)
    
    def _fill_empty_slots(self, schedule: 'Schedule', school: 'School') -> None:
        """空きコマの埋め込み"""
        self.logger.info("空きコマを埋め込み中...")
        
        # 5組の同期処理
        self._synchronize_grade5(schedule, school)
        
        # 交流学級の同期処理
        self._synchronize_exchange_classes(schedule, school)
        
        # 人間の時間割作成方法で空きコマを埋める
        self._fill_with_human_method(schedule, school)
    
    def _fix_violations(self, schedule: 'Schedule', school: 'School', 
                       max_iterations: int) -> None:
        """制約違反の修正"""
        self.logger.info("制約違反を修正中...")
        
        for iteration in range(max_iterations):
            self.generation_stats['iterations'] = iteration + 1
            
            # 現在の違反を検証
            validation_result = self.constraint_system.validate_schedule(schedule, school)
            
            if validation_result.is_valid:
                self.logger.info(f"反復{iteration + 1}回で全制約を満たしました")
                break
            
            # 違反を修正
            fixed_count = self._fix_specific_violations(
                schedule, school, validation_result.violations
            )
            
            if fixed_count == 0:
                self.logger.warning("これ以上の修正ができません")
                break
            
            self.generation_stats['violations_fixed'] += fixed_count
    
    def _copy_schedule(self, original: 'Schedule') -> 'Schedule':
        """スケジュールのコピーを作成"""
        from ...domain.entities.schedule import Schedule
        
        copy = Schedule()
        
        # すべての割り当てをコピー
        for time_slot, assignment in original.get_all_assignments():
            copy.assign(time_slot, assignment)
        
        # ロック状態をコピー
        for time_slot, assignment in original.get_all_assignments():
            if original.is_locked(time_slot, assignment.class_ref):
                copy.lock_cell(time_slot, assignment.class_ref)
        
        return copy
    
    def _lock_fixed_subjects(self, schedule: 'Schedule') -> None:
        """固定教科をロック"""
        fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
        
        locked_count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in fixed_subjects:
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    schedule.lock_cell(time_slot, assignment.class_ref)
                    locked_count += 1
        
        self.logger.info(f"{locked_count}個の固定教科をロックしました")
    
    def _remove_initial_violations(self, schedule: 'Schedule', school: 'School') -> None:
        """初期違反を削除"""
        # 教員不在違反の削除
        removed = self._remove_teacher_absence_violations(schedule, school)
        
        # 体育館制約違反の削除
        removed += self._remove_gym_violations(schedule, school)
        
        self.logger.info(f"初期違反を{removed}件削除しました")
    
    def _place_class_requirements(self, schedule: 'Schedule', school: 'School',
                                 class_ref: 'ClassReference') -> None:
        """クラスの必須教科を配置"""
        # レガシー実装の詳細は省略
        pass
    
    def _synchronize_grade5(self, schedule: 'Schedule', school: 'School') -> None:
        """5組の同期処理"""
        from ...domain.services.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
        
        synchronizer = RefactoredGrade5Synchronizer(self.constraint_system)
        synchronizer.synchronize_grade5_classes(schedule, school)
    
    def _synchronize_exchange_classes(self, schedule: 'Schedule', school: 'School') -> None:
        """交流学級の同期処理"""
        from ...domain.services.exchange_class_synchronizer import ExchangeClassSynchronizer
        
        synchronizer = ExchangeClassSynchronizer()
        synchronizer.synchronize_all_exchange_classes(schedule, school)
    
    def _fill_with_human_method(self, schedule: 'Schedule', school: 'School') -> None:
        """人間の時間割作成方法で空きコマを埋める"""
        from ...domain.services.human_like_scheduler import HumanLikeScheduler
        
        self.logger.info("人間の時間割作成方法で最適化中...")
        
        # HumanLikeSchedulerを使用
        human_scheduler = HumanLikeScheduler(self.constraint_system)
        
        # 人間の方法でスケジュールを最適化
        human_scheduler.optimize_schedule(schedule, school)
        
        # 結果を反映（scheduleは参照渡しなので、変更が反映される）
        self.logger.info("人間の時間割作成方法での最適化が完了しました")
    
    def _fix_specific_violations(self, schedule: 'Schedule', school: 'School',
                               violations: List['ConstraintViolation']) -> int:
        """特定の違反を修正"""
        fixed_count = 0
        
        for violation in violations:
            if self._try_fix_violation(schedule, school, violation):
                fixed_count += 1
        
        return fixed_count
    
    def _try_fix_violation(self, schedule: 'Schedule', school: 'School',
                          violation: 'ConstraintViolation') -> bool:
        """違反の修正を試みる"""
        # レガシー実装の詳細は省略
        return False
    
    def _remove_teacher_absence_violations(self, schedule: 'Schedule', 
                                         school: 'School') -> int:
        """教員不在違反を削除"""
        removed_count = 0
        
        # 固定科目のセット
        fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事"}
        
        for time_slot, assignment in list(schedule.get_all_assignments()):
            # 固定科目は削除しない
            if assignment.subject.name in fixed_subjects:
                continue
                
            if assignment.teacher and school.is_teacher_unavailable(
                time_slot.day, time_slot.period, assignment.teacher
            ):
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    schedule.remove_assignment(time_slot, assignment.class_ref)
                    removed_count += 1
        
        return removed_count
    
    def _remove_gym_violations(self, schedule: 'Schedule', school: 'School') -> int:
        """体育館制約違反を削除"""
        removed_count = 0
        
        from ...domain.value_objects.time_slot import TimeSlot
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間のPEクラスを収集
                pe_classes = []
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(class_ref)
                
                # 2つ目以降を削除
                if len(pe_classes) > 1:
                    for class_ref in pe_classes[1:]:
                        if not schedule.is_locked(time_slot, class_ref):
                            schedule.remove_assignment(time_slot, class_ref)
                            removed_count += 1
        
        return removed_count
    
    def _log_violations(self, violations: List['ConstraintViolation']) -> None:
        """違反をログ出力"""
        for violation in violations:
            self.logger.warning(f"  - {violation.description}")
    
    def _fill_empty_slots_smartly(self, schedule: 'Schedule', school: 'School') -> None:
        """スマート空きスロット埋め"""
        self.logger.info("=== 空きスロットを埋めています ===")
        
        # Follow-up.csvから教師不在情報を取得
        from ...infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
        from ...infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
        
        natural_parser = NaturalFollowUpParser(self.path_manager.input_dir)
        natural_result = natural_parser.parse_file("Follow-up.csv")
        
        # 教師不在情報のロード
        absence_loader = TeacherAbsenceLoader()
        if natural_result["parse_success"] and natural_result.get("teacher_absences"):
            absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
        
        # SmartEmptySlotFillerを使用
        from ...domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
        filler = SmartEmptySlotFiller(self.constraint_system, absence_loader)
        
        # 空きスロットを埋める（最大10パス）
        filled_count = filler.fill_empty_slots_smartly(schedule, school, max_passes=10)
        
        if filled_count > 0:
            self.logger.info(f"合計 {filled_count} 個の空きスロットを埋めました")
            self.generation_stats['empty_slots_filled'] = filled_count
        else:
            self.logger.info("埋められる空きスロットはありませんでした")
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        stats = self.generation_stats
        
        if stats['start_time'] and stats['end_time']:
            duration = (stats['end_time'] - stats['start_time']).total_seconds()
        else:
            duration = 0
        
        self.logger.info("=== 生成統計 ===")
        self.logger.info(f"使用アルゴリズム: {stats['algorithm_used']}")
        self.logger.info(f"実行時間: {duration:.2f}秒")
        self.logger.info(f"反復回数: {stats['iterations']}")
        self.logger.info(f"配置成功: {stats['assignments_made']}")
        self.logger.info(f"配置失敗: {stats['assignments_failed']}")
        self.logger.info(f"違反修正: {stats['violations_fixed']}")
        self.logger.info(f"最終違反: {stats['final_violations']}")
        
        # 空きスロット埋め統計
        if 'empty_slots_filled' in stats:
            self.logger.info(f"空きスロット埋め: {stats['empty_slots_filled']}")