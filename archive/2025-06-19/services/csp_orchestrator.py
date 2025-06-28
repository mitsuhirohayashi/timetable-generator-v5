"""CSPアルゴリズムの調整役"""
import logging
from typing import Optional

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject
from ..value_objects.assignment import Assignment
from ..constraints.base import ConstraintValidator
from ..interfaces.csp_configuration import ICSPConfiguration
from ..interfaces.followup_parser import IFollowUpParser
from ..interfaces.path_configuration import IPathConfiguration


class CSPOrchestrator:
    """CSPアルゴリズムの調整役
    
    各サービスを調整して、完全なスケジュールを生成する
    """
    
    def __init__(self, 
                 constraint_validator: ConstraintValidator,
                 csp_config: Optional[ICSPConfiguration] = None,
                 followup_parser: Optional[IFollowUpParser] = None,
                 path_config: Optional[IPathConfiguration] = None):
        """CSPオーケストレーターを初期化
        
        Args:
            constraint_validator: 制約検証器
            csp_config: CSP設定（Noneの場合はDIコンテナから取得）
            followup_parser: フォローアップパーサー（オプション）
            path_config: パス設定（オプション）
        """
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
        
        # 依存性注入: CSP設定が渡されない場合はDIコンテナから取得
        if csp_config is None:
            from ...infrastructure.di_container import get_csp_configuration
            csp_config = get_csp_configuration()
        if followup_parser is None:
            from ...infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
        if path_config is None:
            from ...infrastructure.di_container import get_path_configuration
            path_config = get_path_configuration()
        
        self.config = csp_config
        self.followup_parser = followup_parser
        self.path_config = path_config
        
        # テスト期間情報を初期化
        self.test_periods = set()
        
        # 各サービスを内部で作成（テスト期間読み込み前に作成）
        self._create_services()
        
        # テスト期間情報を読み込んで設定
        self._load_test_periods()
        self._update_jiritsu_service_test_periods()
    
    def _create_services(self) -> None:
        """必要なサービスを内部で作成"""
        # 評価器を最初に作成（他のサービスが依存するため）
        from .implementations.weighted_schedule_evaluator import WeightedScheduleEvaluator
        self.evaluator = WeightedScheduleEvaluator(self.config, self.constraint_validator)
        
        # 各サービス実装をインポートして作成
        from .implementations.backtrack_jiritsu_placement_service import BacktrackJiritsuPlacementService
        from .implementations.synchronized_grade5_service import SynchronizedGrade5Service
        from .implementations.greedy_subject_placement_service import GreedySubjectPlacementService
        from .implementations.random_swap_optimizer import RandomSwapOptimizer
        from .implementations.smart_csp_solver import SmartCSPSolver
        from .implementations.simulated_annealing_optimizer import SimulatedAnnealingOptimizer
        from .implementations.priority_based_placement_service import PriorityBasedPlacementService
        
        self.jiritsu_service = BacktrackJiritsuPlacementService(self.config, self.constraint_validator)
        self.grade5_service = SynchronizedGrade5Service(self.config, self.constraint_validator)
        self.regular_service = GreedySubjectPlacementService(self.config, self.constraint_validator)
        self.optimizer = RandomSwapOptimizer(self.config, self.constraint_validator, self.evaluator)
        self.smart_solver = SmartCSPSolver(self.config, self.constraint_validator)
        self.sa_optimizer = SimulatedAnnealingOptimizer(self.config, self.constraint_validator, self.evaluator)
        self.priority_service = PriorityBasedPlacementService(self.config, self.constraint_validator)
    
    def _load_test_periods(self) -> None:
        """テスト期間情報を読み込む"""
        try:
            # フォローアップパーサーを使用してテスト期間を読み込む
            test_periods_list = self.followup_parser.parse_test_periods()
            
            for test_period in test_periods_list:
                if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
                    day = test_period.day
                    for period in test_period.periods:
                        self.test_periods.add((day, period))
            
            if self.test_periods:
                self.logger.info(f"テスト期間を{len(self.test_periods)}スロット読み込みました: {sorted(self.test_periods)}")
        except Exception as e:
            self.logger.warning(f"テスト期間情報の読み込みに失敗: {e}")
    
    def _update_jiritsu_service_test_periods(self) -> None:
        """jiritsuサービスにテスト期間情報を設定"""
        test_periods_dict = {(day, period): "テスト期間" for day, period in self.test_periods}
        self.jiritsu_service.set_test_periods(test_periods_dict)
    
    def _is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたスロットがテスト期間かどうか判定"""
        if not hasattr(self, 'test_periods'):
            return False
        return (time_slot.day, time_slot.period) in self.test_periods
    
    def generate(self, school: School, max_iterations: int = 200,
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """CSPアプローチでスケジュールを生成
        
        Args:
            school: 学校情報
            max_iterations: 最大反復回数
            initial_schedule: 初期スケジュール（オプション）
            
        Returns:
            生成されたスケジュール
        """
        self.logger.info("=== CSPオーケストレーターによるスケジュール生成を開始 ===")
        
        # 初期スケジュールの準備
        schedule = initial_schedule if initial_schedule else Schedule()
        
        # デバッグ: テスト期間のデータを確認
        if initial_schedule:
            test_count = 0
            for day, period in self.test_periods:
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    if schedule.get_assignment(time_slot, class_ref):
                        test_count += 1
            self.logger.info(f"[DEBUG] 初期スケジュールのテスト期間データ数: {test_count}")
        else:
            self.logger.info("[DEBUG] 初期スケジュールなし")
        
        # テスト期間保護の準備
        from .test_period_protector import TestPeriodProtector
        protector = TestPeriodProtector()
        
        # 初期スケジュールがある場合は、すべての既存の割り当てをロック
        # テスト期間の内容も含めて保持する
        if initial_schedule:
            # デバッグ: 初期スケジュールのテスト期間データを確認
            test_period_count = 0
            for day, period in protector.test_periods:
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        test_period_count += 1
            self.logger.info(f"初期スケジュールのテスト期間データ数: {test_period_count}")
            
            self._lock_all_existing_assignments(schedule, school)
        
        # テスト期間を保護（内容を保持したまま）
        protector.protect_test_periods(schedule, school)
        
        # 固定科目の強制配置と保護
        self._enforce_and_lock_fixed_subjects(schedule, school)
        
        # Step 1: 自立活動要件を分析
        jiritsu_requirements = self.jiritsu_service.analyze_requirements(school, schedule)
        
        # Step 2: 自立活動を最優先で配置
        jiritsu_placed = self.jiritsu_service.place_activities(schedule, school, jiritsu_requirements)
        self.logger.info(f"自立活動配置完了: {jiritsu_placed}コマ")
        
        # Step 3: 5組の同期配置
        grade5_placed = self.grade5_service.synchronize_placement(schedule, school)
        self.logger.info(f"5組同期配置完了: {grade5_placed}コマ")
        
        # Step 4: 交流学級の早期同期（自立活動以外の時間）
        self._synchronize_exchange_classes_early(schedule, school)
        
        # Step 5: 残りの授業を配置（交流学級同期を考慮）
        regular_placed = self._place_regular_subjects(schedule, school)
        
        # デバッグ: 通常教科配置後のテスト期間データを確認
        test_count_after = 0
        for day, period in self.test_periods:
            time_slot = TimeSlot(day, period)
            for class_ref in school.get_all_classes():
                if schedule.get_assignment(time_slot, class_ref):
                    test_count_after += 1
        self.logger.info(f"[DEBUG] 通常教科配置後のテスト期間データ数: {test_count_after}")
        
        # 日内重複チェック（通常教科配置後）
        self._check_daily_duplicates(schedule, "通常教科配置後")
        
        # Step 5.5: 交流学級の最終同期（念のため）
        self._synchronize_exchange_classes(schedule, school)
        
        # 日内重複チェック（交流学級同期後）
        self._check_daily_duplicates(schedule, "交流学級同期後")
        
        # 日内重複チェック（最適化前）
        self._check_daily_duplicates(schedule, "最適化前")
        
        # Step 6: 局所探索で最適化
        optimization_result = self.optimizer.optimize(
            schedule, school, jiritsu_requirements, max_iterations
        )
        
        # Step 6.5: 制約特化型の最適化を追加
        self._apply_constraint_specific_optimizations(schedule, school)
        
        # 統計情報を出力
        self._log_statistics(schedule, optimization_result)
        
        # 最終評価
        final_breakdown = self.evaluator.evaluate_with_breakdown(schedule, school, jiritsu_requirements)
        self.logger.info(f"最終評価スコア: {final_breakdown.total_score}")
        self.logger.info(f"- 自立活動違反: {final_breakdown.jiritsu_violations}")
        self.logger.info(f"- 制約違反: {final_breakdown.constraint_violations}")
        self.logger.info(f"- 教員負荷分散: {final_breakdown.teacher_load_variance:.2f}")
        
        return schedule
    
    def _place_regular_subjects(self, schedule: Schedule, school: School) -> int:
        """通常教科を配置（交流学級同期を考慮）
        
        Args:
            schedule: スケジュール
            school: 学校情報
            
        Returns:
            配置した授業数
        """
        # 交流学級同期サービスを初期化
        from .exchange_class_synchronizer import ExchangeClassSynchronizer
        synchronizer = ExchangeClassSynchronizer()
        
        # 親学級と交流学級のマッピング
        parent_classes = [
            ClassReference(1, 1), ClassReference(1, 2),
            ClassReference(2, 2), ClassReference(2, 3),
            ClassReference(3, 2), ClassReference(3, 3)
        ]
        
        # 交流学級（処理から除外）
        exchange_classes = {
            ClassReference(1, 6), ClassReference(1, 7),
            ClassReference(2, 6), ClassReference(2, 7),
            ClassReference(3, 6), ClassReference(3, 7)
        }
        
        placed_count = 0
        
        # 親学級を先に配置（交流学級は同期のみで処理）
        for parent_class in parent_classes:
            if parent_class not in school.get_all_classes():
                continue
            
            # 各時間枠をチェック
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 既に配置済みまたはロックされている場合はスキップ
                    if schedule.get_assignment(time_slot, parent_class) or schedule.is_locked(time_slot, parent_class):
                        continue
                    
                    # 配置する科目を選択（交流学級の制約を考慮）
                    for subject_name in ["国", "数", "英", "理", "社", "保", "音", "美", "技", "家"]:
                        subject = Subject(subject_name)
                        
                        # 交流学級との同期可能かチェック
                        if not synchronizer.can_place_for_parent_class(schedule, school, parent_class, time_slot, subject):
                            continue
                        
                        # 教師の可用性チェック
                        teacher = school.get_assigned_teacher(subject, parent_class)
                        if not teacher or not schedule.is_teacher_available(time_slot, teacher):
                            continue
                        
                        # 日内重複チェック
                        if self._would_cause_daily_duplicate(schedule, parent_class, time_slot, subject):
                            continue
                        
                        # 配置前の制約チェック（体育館使用制約を含む）
                        assignment = Assignment(parent_class, subject, teacher)
                        if not self.constraint_validator.check_assignment(schedule, school, time_slot, assignment):
                            self.logger.debug(f"{parent_class}の{time_slot}への{subject.name}配置は制約違反のため不可")
                            continue
                        
                        # 配置
                        if schedule.assign(time_slot, assignment):
                            placed_count += 1
                            
                            # 交流学級を同期
                            if synchronizer.sync_exchange_with_parent(schedule, school, parent_class, time_slot, assignment):
                                self.logger.debug(f"親学級{parent_class}と交流学級を同期: {time_slot} {subject.name}")
                            break
        
        # 残りのクラスを通常処理（交流学級は除外して、親学級の同期のみで処理）
        # regular_serviceは内部で5,6,7組をスキップするので、追加の処理は不要
        regular_placed = self.regular_service.place_subjects(schedule, school)
        self.logger.info(f"通常教科配置完了: 親学級={placed_count}コマ, その他={regular_placed}コマ")
        
        return placed_count + regular_placed
    
    def _would_cause_daily_duplicate(self, schedule: Schedule, class_ref: ClassReference,
                                    time_slot: TimeSlot, subject: Subject) -> bool:
        """日内重複が発生するかチェック"""
        protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        if subject.name in protected_subjects:
            return False
        
        # 同じ日の他の時間に同じ科目があるかチェック
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            check_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(check_slot, class_ref)
            if assignment and assignment.subject == subject:
                return True
        
        return False
    
    def _enforce_and_lock_fixed_subjects(self, schedule: Schedule, school: School) -> None:
        """固定科目の保護とロック（強制配置は行わない）"""
        from ..policies.fixed_subject_protection_policy import FixedSubjectProtectionPolicy
        
        policy = FixedSubjectProtectionPolicy()
        
        # 強制配置はコメントアウト - input.csvの内容を尊重
        # enforced = policy.enforce_critical_slots(schedule, school)
        # if enforced > 0:
        #     self.logger.info(f"{enforced}個の固定科目を強制配置しました")
        
        # 既存の固定科目をロック（これは保持）
        # 設定からfixed_subjectsを取得
        from ...infrastructure.di_container import get_configuration_reader
        config_reader = get_configuration_reader()
        fixed_subjects = config_reader.get_fixed_subjects()
        locked_count = 0
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in fixed_subjects:
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    schedule.lock_cell(time_slot, assignment.class_ref)
                    locked_count += 1
        
        if locked_count > 0:
            self.logger.info(f"{locked_count}個の固定科目をロックしました（input.csvの内容を保護）")
        
        # 検証はスキップ（強制配置が無効のため）
        # violations = policy.validate_schedule(schedule, school)
        # if violations:
        #     self.logger.error(f"固定科目違反が{len(violations)}件検出されました")
        #     for v in violations[:5]:  # 最初の5件を表示
        #         self.logger.error(f"  {v['time_slot']} {v['class_ref']}: {v['expected']} → {v['actual']}")
    
    def _synchronize_exchange_classes_early(self, schedule: Schedule, school: School) -> None:
        """交流学級の早期同期（自立活動配置後、通常教科配置前）"""
        from .exchange_class_synchronizer import ExchangeClassSynchronizer
        from ..value_objects.time_slot import TimeSlot, ClassReference
        from ..value_objects.assignment import Assignment
        
        self.logger.info("交流学級の早期同期を開始（自立活動以外）")
        
        # 交流学級同期サービスを使用
        synchronizer = ExchangeClassSynchronizer()
        
        # 交流学級のマッピング
        exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        sync_count = 0
        for exchange_class, parent_class in exchange_mappings.items():
            if exchange_class not in school.get_all_classes() or parent_class not in school.get_all_classes():
                continue
                
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 交流学級が自立活動の場合はスキップ
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                        continue
                    
                    # 親学級に授業がある場合、交流学級も同じ授業を配置
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    if parent_assignment and parent_assignment.subject.name not in ["保", "保健体育"]:
                        if not exchange_assignment or exchange_assignment.subject != parent_assignment.subject:
                            # 同期サービスを使用して同期
                            if synchronizer.sync_exchange_with_parent(schedule, school, parent_class, time_slot, parent_assignment):
                                sync_count += 1
                            else:
                                self.logger.debug(f"{exchange_class}の{time_slot}への{parent_assignment.subject.name}同期に失敗")
        
        self.logger.info(f"交流学級の早期同期完了: {sync_count}件")
    
    def _synchronize_exchange_classes(self, schedule: Schedule, school: School) -> None:
        """交流学級を親学級と同期（最終確認）"""
        from .exchange_class_synchronizer import ExchangeClassSynchronizer
        
        self.logger.info("交流学級の最終同期を開始")
        synchronizer = ExchangeClassSynchronizer()
        sync_count = synchronizer.synchronize_all_exchange_classes(schedule, school)
        self.logger.info(f"交流学級の最終同期完了: {sync_count}件")
    
    def _lock_all_existing_assignments(self, schedule: Schedule, school: School) -> None:
        """初期スケジュールの既存の割り当てをロック（自立活動配置用の空きを残す）"""
        locked_count = 0
        test_subjects = {"test", "テスト", "定期テスト", "期末テスト", "中間テスト"}
        fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"}
        
        # 交流学級と親学級のマッピング
        exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        for time_slot, assignment in schedule.get_all_assignments():
            # 固定科目やテスト科目は必ずロック
            should_lock = False
            
            # テスト科目の場合
            if assignment.subject.name.lower() in test_subjects:
                should_lock = True
                self.logger.info(
                    f"テスト科目をロック: {time_slot} {assignment.class_ref} - {assignment.subject.name}"
                )
            
            # 固定科目の場合
            if assignment.subject.name in fixed_subjects:
                should_lock = True
            
            # 交流学級の自立活動の場合はロック
            if assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                should_lock = True
            
            # 通常の授業はロックしない（CSPが最適化できるように）
            # ただし、既に配置済みの授業を保護したい場合は以下の条件を追加
            # - 5組の授業はロック（合同授業のため）
            # - 会議時間（HF、企画など）はロック
            if assignment.class_ref.class_number == 5:  # 5組は特別扱い
                should_lock = True
            
            # テスト期間かチェック
            is_test_period = self._is_test_period(time_slot)
            if is_test_period:
                should_lock = True  # 必ずロック
                self.logger.info(
                    f"テスト期間を保護（内容を保持）: {time_slot} {assignment.class_ref} - {assignment.subject.name}"
                )
            
            # 交流学級の通常授業（数、英など）はロックしない（自立活動配置用）
            # ただし、テスト期間中は全ての教科をロック
            if not is_test_period and assignment.class_ref in exchange_mappings and assignment.subject.name not in ["自立", "日生", "生単", "作業"] and assignment.subject.name not in fixed_subjects:
                should_lock = False
            
            if should_lock and not schedule.is_locked(time_slot, assignment.class_ref):
                schedule.lock_cell(time_slot, assignment.class_ref)
                locked_count += 1
        
        if locked_count > 0:
            self.logger.info(f"初期スケジュールから{locked_count}個の割り当てをロックしました")
    
    def _log_statistics(self, schedule: Schedule, optimization_result) -> None:
        """統計情報をログ出力"""
        total_assignments = len(schedule.get_all_assignments())
        
        self.logger.info("=== CSP生成統計 ===")
        self.logger.info(f"総割り当て数: {total_assignments}")
        self.logger.info(f"最適化結果:")
        self.logger.info(f"- 初期スコア: {optimization_result.initial_score}")
        self.logger.info(f"- 最終スコア: {optimization_result.final_score}")
        self.logger.info(f"- 改善率: {optimization_result.improvement_percentage:.1f}%")
        self.logger.info(f"- 反復回数: {optimization_result.iterations_performed}")
        self.logger.info(f"- 交換試行: {optimization_result.swap_attempts}")
        self.logger.info(f"- 交換成功: {optimization_result.swap_successes}")
        
        if optimization_result.swap_attempts > 0:
            success_rate = optimization_result.swap_successes / optimization_result.swap_attempts * 100
            self.logger.info(f"- 交換成功率: {success_rate:.1f}%")
    
    
    def _check_daily_duplicates(self, schedule: Schedule, stage: str) -> None:
        """日内重複をチェックして報告"""
        duplicates = []
        protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        
        # すべてのクラスを収集
        all_classes = set()
        for _, assignment in schedule.get_all_assignments():
            all_classes.add(assignment.class_ref)
        
        # 各クラスごとに日内重複をチェック
        for class_ref in sorted(all_classes, key=lambda c: (c.grade, c.class_number)):
            for day in ["月", "火", "水", "木", "金"]:
                # その日の全教科を収集
                subjects_in_day = {}
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in protected_subjects:
                        subject_name = assignment.subject.name
                        if subject_name not in subjects_in_day:
                            subjects_in_day[subject_name] = []
                        subjects_in_day[subject_name].append(period)
                
                # 重複チェック
                for subject, periods in subjects_in_day.items():
                    if len(periods) > 1:
                        duplicates.append({
                            'class': class_ref,
                            'day': day,
                            'subject': subject,
                            'periods': periods
                        })
        
        # 結果を報告
        if duplicates:
            self.logger.warning(f"=== {stage}の日内重複: {len(duplicates)}件 ===")
            for dup in duplicates:
                periods_str = ", ".join([f"{p}限" for p in dup['periods']])
                self.logger.warning(f"  - {dup['class']}の{dup['day']}曜日: {dup['subject']}が{periods_str}に重複")
        else:
            self.logger.info(f"=== {stage}: 日内重複なし ===")
    
    def _would_cause_daily_duplicate_early_sync(self, schedule: Schedule, class_ref: ClassReference,
                                               time_slot: TimeSlot, subject: Subject) -> bool:
        """早期同期時の日内重複チェック"""
        # 保護教科は日内重複を許可
        protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        if subject.name in protected_subjects:
            return False
            
        # その日の他の時間に同じ教科があるかチェック
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            other_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(other_slot, class_ref)
            
            if assignment and assignment.subject == subject:
                return True
        
        return False
    
    def _apply_constraint_specific_optimizations(self, schedule: Schedule, school: School) -> None:
        """制約特化型の最適化を適用
        
        体育館使用制約と日内重複制約に特化した最適化を実行します。
        """
        self.logger.info("=== 制約特化型最適化を開始 ===")
        
        try:
            from .constraint_specific_optimizer import ConstraintSpecificOptimizer
            
            optimizer = ConstraintSpecificOptimizer()
            
            # 体育館使用制約の最適化
            gym_resolved = optimizer.optimize_gym_usage(schedule, school)
            
            # 日内重複制約の最適化
            duplicate_resolved = optimizer.optimize_daily_duplicates(schedule, school)
            
            if gym_resolved > 0 or duplicate_resolved > 0:
                self.logger.info(f"制約特化型最適化完了: 体育館使用={gym_resolved}件, 日内重複={duplicate_resolved}件解決")
            else:
                self.logger.info("制約特化型最適化: 追加の改善なし")
                
        except Exception as e:
            self.logger.error(f"制約特化型最適化中にエラー: {e}")
            # エラーが発生しても処理は継続
    
