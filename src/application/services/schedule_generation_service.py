"""スケジュール生成サービス（リファクタリング版）

高度なCSPアルゴリズムを使用した時間割生成を管理するサービス。
Strategy パターンを使用してアルゴリズムの選択を管理します。
"""
import logging
from typing import Optional, Dict, List, TYPE_CHECKING, Any
from datetime import datetime

from .generation_strategies.base_generation_strategy import BaseGenerationStrategy
from .generation_strategies.ultrathink_strategy import UltrathinkStrategy
from .generation_strategies.improved_csp_strategy import ImprovedCSPStrategy
from .generation_strategies.grade5_priority_strategy import Grade5PriorityStrategy
from .generation_strategies.advanced_csp_strategy import AdvancedCSPStrategy
from .generation_strategies.legacy_strategy import LegacyStrategy
from .generation_strategies.unified_hybrid_strategy import UnifiedHybridStrategy
from .generation_strategies.unified_hybrid_strategy_fixed import UnifiedHybridStrategyFixed
from .generation_strategies.unified_hybrid_strategy_v2 import UnifiedHybridStrategyV2
from .generation_strategies.unified_hybrid_strategy_v3 import UnifiedHybridStrategyV3
from .simple_generator_v2 import SimpleGeneratorV2
from .generation_helpers.followup_loader import FollowupLoader
from .generation_helpers.empty_slot_filler import EmptySlotFiller
from .generation_helpers.schedule_helper import ScheduleHelper
from .learned_rule_application_service import LearnedRuleApplicationService

if TYPE_CHECKING:
    from ...domain.entities.schedule import Schedule
    from ...domain.entities.school import School
    from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
    from ...infrastructure.config.path_manager import PathManager


class ScheduleGenerationService:
    """スケジュール生成サービス（リファクタリング版）"""
    
    def __init__(
        self,
        constraint_system: 'UnifiedConstraintSystem',
        path_manager: 'PathManager',
        learned_rule_service: Optional[LearnedRuleApplicationService] = None
    ) -> None:
        """初期化
        
        Args:
            constraint_system: 統一制約システムのインスタンス
            path_manager: パス管理のインスタンス
            learned_rule_service: 学習ルール適用サービス（オプション）
        """
        self.constraint_system = constraint_system
        self.path_manager = path_manager
        self.logger = logging.getLogger(__name__)
        
        # 学習ルール適用サービスの初期化
        self.learned_rule_service = learned_rule_service or LearnedRuleApplicationService()
        
        # ヘルパーの初期化
        self.followup_loader = FollowupLoader(path_manager)
        self.empty_slot_filler = EmptySlotFiller(constraint_system, path_manager)
        self.schedule_helper = ScheduleHelper()
        
        # 戦略の初期化
        self._init_strategies()
        
        # 統計情報の初期化
        self.generation_stats: Dict[str, Any] = self._init_stats()
    
    def _init_strategies(self) -> None:
        """生成戦略を初期化"""
        self.strategies = {
            'simple_v2': SimpleGeneratorV2,
            'unified_hybrid': UnifiedHybridStrategyV2(self.constraint_system),
            'ultrathink': UltrathinkStrategy(
                self.constraint_system,
                self.followup_loader.load_followup_data
            ),
            'improved_csp': ImprovedCSPStrategy(self.constraint_system),
            'grade5_priority': Grade5PriorityStrategy(self.constraint_system),
            'advanced_csp': AdvancedCSPStrategy(self.constraint_system),
            'legacy': LegacyStrategy(self.constraint_system)
        }
    
    def _init_stats(self) -> Dict[str, Any]:
        """統計情報を初期化"""
        return {
            'start_time': None,
            'end_time': None,
            'iterations': 0,
            'assignments_made': 0,
            'assignments_failed': 0,
            'violations_fixed': 0,
            'final_violations': 0,
            'empty_slots_filled': 0,
            'algorithm_used': 'unknown'
        }
    
    def generate_schedule(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        strategy: str = 'legacy',
        max_iterations: int = 100,
        search_mode: str = "standard"
    ) -> 'Schedule':
        """スケジュールを生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            max_iterations: 最大反復回数
            use_advanced_csp: 高度なCSPアルゴリズムを使用するか
            use_improved_csp: 改良版CSPアルゴリズムを使用するか
            use_ultrathink: Ultrathink Perfect Generatorを使用するか
            use_grade5_priority: 5組優先配置アルゴリズムを使用するか
            use_unified_hybrid: 統一ハイブリッドアルゴリズムを使用するか
            search_mode: 探索モード
            
        Returns:
            生成されたスケジュール
        """
        self.logger.info("=== スケジュール生成を開始 ===")
        self.generation_stats['start_time'] = datetime.now()
        
        # QandAシステムから学習したルールを読み込む
        learned_rules_count = self.learned_rule_service.parse_and_load_rules()
        if learned_rules_count > 0:
            self.logger.info(f"QandAシステムから{learned_rules_count}個のルールを学習しました")
        
        # 戦略を選択
        if strategy == 'simple_v2':
            generator = self.strategies[strategy](school, initial_schedule)
            return generator.generate()

        strategy = self._select_strategy(strategy_name=strategy)
        
        self.generation_stats['algorithm_used'] = strategy.get_name()
        
        try:
            # 初期スケジュールの準備
            if initial_schedule:
                schedule = self._prepare_initial_schedule(initial_schedule, school)
            else:
                from ...domain.entities.schedule import Schedule
                schedule = Schedule()
            
            # スケジュール生成
            self.logger.info("--- 戦略実行前のスケジュール状態をデバッグ出力 ---")
            for ts, ass in schedule.get_all_assignments():
                self.logger.debug(f"[PRE-STRATEGY] {ts}: {ass.class_ref} - {ass.subject.name} ({ass.teacher.name if ass.teacher else 'N/A'})")
            self.logger.info("--- デバッグ出力終了 ---")

            schedule = strategy.generate(
                school=school,
                initial_schedule=schedule,
                max_iterations=max_iterations,
                search_mode=search_mode
            )
            
            # 統計情報を更新
            self._update_stats(schedule, school)
            
            # UnifiedHybrid戦略以外の場合のみ空きスロットを埋める
            if strategy != 'unified_hybrid':
                self.logger.info(f"{strategy}戦略のため、空きスロットを埋めます。")
                filled_count = self.empty_slot_filler.fill_empty_slots(schedule, school)
                self.generation_stats['empty_slots_filled'] = filled_count
            else:
                self.logger.info("UnifiedHybrid戦略のため、空きスロット埋めをスキップします。")
            
            # 最終検証
            self._final_validation(schedule, school)
            
        except Exception as e:
            self.logger.error(f"スケジュール生成中にエラーが発生しました: {e}")
            raise
        finally:
            self.generation_stats['end_time'] = datetime.now()
            self._log_statistics()
        
        return schedule
    
    def _select_strategy(self, strategy_name: str) -> BaseGenerationStrategy:
        """使用する戦略を選択"""
        if strategy_name in self.strategies:
            self.logger.info(f"✓ {strategy_name} 戦略を選択しました")
            return self.strategies[strategy_name]
        else:
            self.logger.error(f"無効な戦略名: {strategy_name}")
            raise ValueError(f"無効な戦略名: {strategy_name}")
    
    def _prepare_initial_schedule(
        self,
        initial_schedule: 'Schedule',
        school: 'School'
    ) -> 'Schedule':
        """初期スケジュールを準備"""
        # スケジュールをコピー
        schedule = self.schedule_helper.copy_schedule(initial_schedule)
        
        # 固定科目をロック
        self.schedule_helper.lock_fixed_subjects(schedule)
        
        return schedule
    
    def _update_stats(self, schedule: 'Schedule', school: 'School') -> None:
        """統計情報を更新"""
        self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
        
        # 制約違反をチェック
        validation_result = self.constraint_system.validate_schedule(schedule, school)
        self.generation_stats['final_violations'] = len(validation_result.violations)
    
    def _final_validation(self, schedule: 'Schedule', school: 'School') -> None:
        """最終検証"""
        validation_result = self.constraint_system.validate_schedule(schedule, school)
        violations = validation_result.violations
        
        if violations:
            self.logger.warning(f"最終検証で{len(violations)}件の制約違反が見つかりました")
            self.schedule_helper.log_violations(violations)
        else:
            self.logger.info("✓ 全ての制約を満たすスケジュールが生成されました！")
    
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
        self.logger.info(f"配置成功: {stats['assignments_made']}")
        self.logger.info(f"最終違反: {stats['final_violations']}")
        self.logger.info(f"空きスロット埋め: {stats['empty_slots_filled']}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return self.generation_stats.copy()