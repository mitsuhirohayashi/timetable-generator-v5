"""改良版CSPアルゴリズムの調整役

制約充足をより確実にし、効率的な時間割生成を実現します。
"""
import logging
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
from enum import Enum

from ...domain.exceptions import (
    TimetableGenerationError,
    PhaseExecutionError,
    DataLoadingError,
    ConfigurationError
)

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from ...domain.constraints.base import ConstraintValidator
from ...domain.interfaces.csp_configuration import ICSPConfiguration
from ...domain.interfaces.followup_parser import IFollowUpParser
from ...domain.interfaces.path_configuration import IPathConfiguration
from ...domain.services.validators.constraint_validator import ConstraintValidatorImproved


class SearchMode(Enum):
    """探索モード"""
    STANDARD = "standard"  # 従来の方法
    PRIORITY = "priority"  # 優先度ベース
    SMART = "smart"      # スマートCSP（制約伝播）
    HYBRID = "hybrid"    # ハイブリッド（複数手法の組み合わせ）


class CSPOrchestratorImproved:
    """改良版CSPアルゴリズムの調整役
    
    主な改良点：
    1. 制約チェックの一元化と効率化
    2. 配置戦略の最適化
    3. エラーハンドリングの強化
    4. 統計情報の詳細化
    """
    
    def __init__(self, 
                 constraint_validator: ConstraintValidatorImproved = None,
                 csp_config: Optional[ICSPConfiguration] = None,
                 followup_parser: Optional[IFollowUpParser] = None,
                 path_config: Optional[IPathConfiguration] = None):
        """CSPオーケストレーターを初期化
        
        Args:
            constraint_validator: 改良版制約検証器
            csp_config: CSP設定
            followup_parser: フォローアップパーサー
            path_config: パス設定
        """
        # 改良版制約検証器を使用
        self.constraint_validator = constraint_validator or ConstraintValidatorImproved()
        self.logger = logging.getLogger(__name__)
        
        # 依存性注入
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
        
        # 統計情報の初期化
        self.statistics = defaultdict(int)
        
        # 各サービスを内部で作成
        self._create_services()
        
        # テスト期間情報を読み込んで設定
        self._load_test_periods()
        self._update_jiritsu_service_test_periods()
    
    def _create_services(self) -> None:
        """必要なサービスを内部で作成"""
        # 評価器を最初に作成
        from .generators.weighted_schedule_evaluator import WeightedScheduleEvaluator
        self.evaluator = WeightedScheduleEvaluator(self.config, self.constraint_validator)
        
        # 各サービス実装をインポートして作成
        from .generators.backtrack_jiritsu_placement_service import BacktrackJiritsuPlacementService
        from .generators.synchronized_grade5_service import SynchronizedGrade5Service
        from .generators.priority_based_placement_service_improved import PriorityBasedPlacementServiceImproved
        from .generators.random_swap_optimizer import RandomSwapOptimizer
        from .optimizers.constraint_specific_optimizer import ConstraintSpecificOptimizer
        
        self.jiritsu_service = BacktrackJiritsuPlacementService(self.config, self.constraint_validator)
        self.grade5_service = SynchronizedGrade5Service(self.config, self.constraint_validator)
        self.regular_service = PriorityBasedPlacementServiceImproved(self.constraint_validator)
        self.optimizer = RandomSwapOptimizer(self.config, self.constraint_validator, self.evaluator)
        self.constraint_optimizer = ConstraintSpecificOptimizer()
    
    def _load_test_periods(self) -> None:
        """テスト期間情報を読み込む"""
        try:
            test_periods_list = self.followup_parser.parse_test_periods()
            
            for test_period in test_periods_list:
                if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
                    day = test_period.day
                    for period in test_period.periods:
                        self.test_periods.add((day, period))
            
            if self.test_periods:
                self.logger.info(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
        except Exception as e:
            self.logger.warning(f"テスト期間情報の読み込みに失敗: {e}")
    
    def _update_jiritsu_service_test_periods(self) -> None:
        """jiritsuサービスにテスト期間情報を設定"""
        test_periods_dict = {(day, period): "テスト期間" for day, period in self.test_periods}
        self.jiritsu_service.set_test_periods(test_periods_dict)
    
    def generate(self, school: School, max_iterations: int = 200,
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """CSPアプローチでスケジュールを生成
        
        Args:
            school: 学校情報
            max_iterations: 最大反復回数
            initial_schedule: 初期スケジュール
            
        Returns:
            生成されたスケジュール
        """
        self.logger.info("=== 改良版CSPオーケストレーターによるスケジュール生成を開始 ===")
        
        # 統計情報をリセット
        self.statistics.clear()
        
        # 初期スケジュールの準備
        schedule = initial_schedule if initial_schedule else Schedule()
        
        # Phase 1: 初期設定と保護
        self._phase1_initialization(schedule, school)
        
        # Phase 2: 自立活動の配置
        self._phase2_jiritsu_placement(schedule, school)
        
        # Phase 3: 5組の同期配置
        self._phase3_grade5_synchronization(schedule, school)
        
        # Phase 4: 交流学級の早期同期
        self._phase4_exchange_class_sync(schedule, school)
        
        # Phase 5: 通常教科の配置（改良版）
        self._phase5_regular_subjects(schedule, school)
        
        # Phase 6: 最適化
        self._phase6_optimization(schedule, school, max_iterations)
        
        # 最終評価と統計出力
        self._final_evaluation(schedule, school)
        
        return schedule
    
    def _phase1_initialization(self, schedule: Schedule, school: School) -> None:
        """Phase 1: 初期設定と保護"""
        self.logger.info("=== Phase 1: 初期設定と保護 ===")
        
        try:
            # テスト期間保護
            from ...domain.services.core.test_period_protector import TestPeriodProtector
            protector = TestPeriodProtector()
            
            # テスト期間情報をスケジュールに設定
            self._load_test_periods()
            if self.test_periods:
                # test_periods (set of tuples) を辞書形式に変換
                test_periods_dict = {}
                for day, period in self.test_periods:
                    if day not in test_periods_dict:
                        test_periods_dict[day] = []
                    test_periods_dict[day].append(period)
                schedule.test_periods = test_periods_dict
                self.logger.info(f"スケジュールにテスト期間情報を設定: {len(self.test_periods)}スロット")
            
            # 初期スケジュールがある場合は既存の割り当てをロック
            if schedule.get_all_assignments():
                locked_count = self._lock_initial_assignments(schedule, school)
                self.statistics['initial_locked'] = locked_count
                self.logger.info(f"初期スケジュールから{locked_count}個の割り当てをロック")
            
            # テスト期間を保護
            protector.protect_test_periods(schedule, school)
            
            # 固定科目の保護（強制配置はしない）
            self._protect_fixed_subjects(schedule, school)
            
        except Exception as e:
            self.logger.error(f"Phase 1 初期化エラー: {str(e)}", exc_info=True)
            raise PhaseExecutionError(
                f"Phase 1 failed: {str(e)}",
                phase_name="initialization",
                details={'error': str(e)}
            ) from e
    
    def _phase2_jiritsu_placement(self, schedule: Schedule, school: School) -> None:
        """Phase 2: 自立活動の配置"""
        self.logger.info("=== Phase 2: 自立活動の配置 ===")
        
        try:
            jiritsu_requirements = self.jiritsu_service.analyze_requirements(school, schedule)
            jiritsu_placed = self.jiritsu_service.place_activities(schedule, school, jiritsu_requirements)
            
            self.statistics['jiritsu_placed'] = jiritsu_placed
            self.logger.info(f"自立活動配置完了: {jiritsu_placed}コマ")
            
        except Exception as e:
            self.logger.error(f"Phase 2 自立活動配置エラー: {str(e)}", exc_info=True)
            self.statistics['jiritsu_placement_errors'] = str(e)
            # 続行
            self.logger.warning("自立活動配置に失敗しましたが、処理を続行します")
    
    def _phase3_grade5_synchronization(self, schedule: Schedule, school: School) -> None:
        """Phase 3: 5組の同期配置"""
        self.logger.info("=== Phase 3: 5組の同期配置 ===")
        
        try:
            grade5_placed = self.grade5_service.synchronize_placement(schedule, school)
            
            self.statistics['grade5_placed'] = grade5_placed
            self.logger.info(f"5組同期配置完了: {grade5_placed}コマ")
            
        except Exception as e:
            self.logger.error(f"Phase 3 5組同期配置エラー: {str(e)}", exc_info=True)
            self.statistics['grade5_sync_errors'] = str(e)
            # 続行
            self.logger.warning("5組同期配置に失敗しましたが、処理を続行します")
    
    def _phase4_exchange_class_sync(self, schedule: Schedule, school: School) -> None:
        """Phase 4: 交流学級の早期同期"""
        self.logger.info("=== Phase 4: 交流学級の早期同期 ===")
        
        try:
            sync_count = self._synchronize_exchange_classes_early(schedule, school)
            
            self.statistics['exchange_sync_early'] = sync_count
            self.logger.info(f"交流学級早期同期完了: {sync_count}件")
            
        except Exception as e:
            self.logger.error(f"Phase 4 交流学級同期エラー: {str(e)}", exc_info=True)
            self.statistics['exchange_sync_errors'] = str(e)
            # 続行
            self.logger.warning("交流学級同期に失敗しましたが、処理を続行します")
    
    def _phase5_regular_subjects(self, schedule: Schedule, school: School) -> None:
        """Phase 5: 通常教科の配置（改良版）"""
        self.logger.info("=== Phase 5: 通常教科の配置（優先度ベース） ===")
        
        # 制約チェックの統計を開始
        # キャッシュクリア（アダプターには実装されていない場合があるため条件付き）
        if hasattr(self.constraint_validator, 'clear_cache'):
            self.constraint_validator.clear_cache()
        
        # メソッド名が異なる可能性があるため確認
        if hasattr(self.regular_service, 'place_subjects'):
            regular_placed = self.regular_service.place_subjects(schedule, school)
        elif hasattr(self.regular_service, 'place_all_subjects'):
            regular_placed = self.regular_service.place_all_subjects(schedule, school)
        else:
            regular_placed = 0
        
        self.statistics['regular_placed'] = regular_placed
        self.logger.info(f"通常教科配置完了: {regular_placed}コマ")
        
        # 日内重複チェック
        duplicates = self._check_daily_duplicates(schedule, "通常教科配置後")
        self.statistics['daily_duplicates_after_regular'] = len(duplicates)
    
    def _phase6_optimization(self, schedule: Schedule, school: School, max_iterations: int) -> None:
        """Phase 6: 最適化"""
        self.logger.info("=== Phase 6: 最適化 ===")
        
        # 交流学級の最終同期
        from ...domain.services.synchronizers.exchange_class_synchronizer import ExchangeClassSynchronizer
        synchronizer = ExchangeClassSynchronizer()
        final_sync = synchronizer.synchronize_all_exchange_classes(schedule, school)
        self.statistics['exchange_sync_final'] = final_sync
        self.logger.info(f"交流学級最終同期: {final_sync}件")
        
        # 局所探索による最適化
        jiritsu_requirements = self.jiritsu_service.analyze_requirements(school, schedule)
        optimization_result = self.optimizer.optimize(
            schedule, school, jiritsu_requirements, max_iterations
        )
        
        self.statistics['optimization_iterations'] = optimization_result.iterations_performed
        self.statistics['optimization_swaps'] = optimization_result.swap_successes
        self.statistics['optimization_improvement'] = optimization_result.improvement_percentage
        
        # 制約特化型最適化
        gym_resolved = self.constraint_optimizer.optimize_gym_usage(schedule, school)
        duplicate_resolved = self.constraint_optimizer.optimize_daily_duplicates(schedule, school)
        
        self.statistics['gym_conflicts_resolved'] = gym_resolved
        self.statistics['daily_duplicates_resolved'] = duplicate_resolved
        
        self.logger.info(f"最適化完了: 改善率{optimization_result.improvement_percentage:.1f}%")
    
    def _final_evaluation(self, schedule: Schedule, school: School) -> None:
        """最終評価と統計出力"""
        self.logger.info("=== 最終評価 ===")
        
        # 制約違反の詳細チェック
        result = self.constraint_validator.validate_schedule(schedule, school)
        violations = result.violations
        
        violation_types = defaultdict(int)
        for violation in violations:
            # ConstraintViolationオブジェクトから情報を取得
            if hasattr(violation, 'severity'):
                violation_type = violation.severity
            elif hasattr(violation, 'constraint_name'):
                violation_type = violation.constraint_name
            else:
                violation_type = 'Unknown'
            violation_types[violation_type] += 1
        
        # 統計情報の出力
        self.logger.info("=== 生成統計 ===")
        self.logger.info(f"総割り当て数: {len(schedule.get_all_assignments())}")
        self.logger.info(f"初期ロック数: {self.statistics.get('initial_locked', 0)}")
        self.logger.info(f"自立活動配置: {self.statistics.get('jiritsu_placed', 0)}コマ")
        self.logger.info(f"5組同期配置: {self.statistics.get('grade5_placed', 0)}コマ")
        self.logger.info(f"通常教科配置: {self.statistics.get('regular_placed', 0)}コマ")
        self.logger.info(f"交流学級同期: 早期{self.statistics.get('exchange_sync_early', 0)}件, 最終{self.statistics.get('exchange_sync_final', 0)}件")
        
        self.logger.info("=== 最適化統計 ===")
        self.logger.info(f"反復回数: {self.statistics.get('optimization_iterations', 0)}")
        self.logger.info(f"交換成功: {self.statistics.get('optimization_swaps', 0)}")
        self.logger.info(f"改善率: {self.statistics.get('optimization_improvement', 0):.1f}%")
        self.logger.info(f"体育館競合解決: {self.statistics.get('gym_conflicts_resolved', 0)}件")
        self.logger.info(f"日内重複解決: {self.statistics.get('daily_duplicates_resolved', 0)}件")
        
        self.logger.info("=== 制約違反統計 ===")
        total_violations = len(violations)
        self.logger.info(f"総違反数: {total_violations}")
        for vtype, count in violation_types.items():
            self.logger.info(f"- {vtype}: {count}件")
    
    def _lock_initial_assignments(self, schedule: Schedule, school: School) -> int:
        """初期スケジュールの既存の割り当てをロック"""
        locked_count = 0
        test_subjects = {"test", "テスト", "定期テスト", "期末テスト", "中間テスト"}
        fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"}
        
        # 交流学級のマッピング
        exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        for time_slot, assignment in schedule.get_all_assignments():
            should_lock = False
            
            # テスト科目または固定科目
            if (assignment.subject.name.lower() in test_subjects or 
                assignment.subject.name in fixed_subjects):
                should_lock = True
            
            # 交流学級の自立活動
            if assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                should_lock = True
            
            # テスト期間
            if (time_slot.day, time_slot.period) in self.test_periods:
                should_lock = True
            
            # 交流学級でない通常の授業はロックしない（配置の柔軟性を保つため）
            # コメントアウト: 過度なロックを防ぐ
            # if assignment.class_ref not in exchange_mappings:
            #     should_lock = True
            
            if should_lock and not schedule.is_locked(time_slot, assignment.class_ref):
                schedule.lock_cell(time_slot, assignment.class_ref)
                locked_count += 1
        
        return locked_count
    
    def _protect_fixed_subjects(self, schedule: Schedule, school: School) -> None:
        """固定科目の保護（強制配置はしない）"""
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
            self.logger.info(f"{locked_count}個の固定科目をロック")
    
    def _synchronize_exchange_classes_early(self, schedule: Schedule, school: School) -> int:
        """交流学級の早期同期"""
        from ...domain.value_objects.assignment import Assignment
        
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
                            # ロックされている場合はスキップ
                            if schedule.is_locked(time_slot, exchange_class):
                                continue
                            
                            # 制約チェック
                            new_assignment = Assignment(exchange_class, parent_assignment.subject, parent_assignment.teacher)
                            can_place, _ = self.constraint_validator.can_place_assignment(
                                schedule, school, time_slot, new_assignment, check_level='normal'
                            )
                            
                            if can_place:
                                # 既存の割り当てを削除
                                if exchange_assignment:
                                    schedule.remove_assignment(time_slot, exchange_class)
                                
                                # 新しい割り当てを配置
                                schedule.assign(time_slot, new_assignment)
                                sync_count += 1
        
        return sync_count
    
    def _check_daily_duplicates(self, schedule: Schedule, stage: str) -> List[Dict]:
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
                subjects_in_day = defaultdict(list)
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in protected_subjects:
                        subjects_in_day[assignment.subject.name].append(period)
                
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
            for dup in duplicates[:5]:  # 最初の5件のみ表示
                periods_str = ", ".join([f"{p}限" for p in dup['periods']])
                self.logger.warning(f"  - {dup['class']}の{dup['day']}曜日: {dup['subject']}が{periods_str}に重複")
        else:
            self.logger.info(f"=== {stage}: 日内重複なし ===")
        
        return duplicates


# Aliases for backward compatibility
CSPOrchestrator = CSPOrchestratorImproved
AdvancedCSPOrchestrator = CSPOrchestratorImproved