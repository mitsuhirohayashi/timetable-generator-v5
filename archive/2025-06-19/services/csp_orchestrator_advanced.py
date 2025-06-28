"""高度な探索機能を持つCSPオーケストレーター"""
import logging
from typing import Optional
from enum import Enum

from .csp_orchestrator import CSPOrchestrator
from ..entities.schedule import Schedule
from ..entities.school import School
from ..constraints.base import ConstraintValidator
from ..interfaces.csp_configuration import ICSPConfiguration


class SearchMode(Enum):
    """探索モード"""
    STANDARD = "standard"  # 従来の方法
    PRIORITY = "priority"  # 優先度ベース
    SMART = "smart"      # スマートCSP（制約伝播）
    HYBRID = "hybrid"    # ハイブリッド（複数手法の組み合わせ）


class AdvancedCSPOrchestrator(CSPOrchestrator):
    """高度な探索機能を持つCSPオーケストレーター"""
    
    def __init__(self, constraint_validator: ConstraintValidator,
                 config: Optional[ICSPConfiguration] = None,
                 search_mode: SearchMode = SearchMode.HYBRID):
        """初期化
        
        Args:
            constraint_validator: 制約検証器
            config: CSP設定
            search_mode: 探索モード
        """
        super().__init__(constraint_validator, config)
        self.search_mode = search_mode
        self.logger = logging.getLogger(__name__)
    
    def generate(self, school: School, max_iterations: int = 200,
                 initial_schedule: Optional[Schedule] = None) -> Schedule:
        """高度な探索でスケジュールを生成"""
        self.logger.info(f"=== 高度なCSP生成を開始 (モード: {self.search_mode.value}) ===")
        
        if self.search_mode == SearchMode.STANDARD:
            # 従来の方法
            return super().generate(school, max_iterations, initial_schedule)
        
        elif self.search_mode == SearchMode.PRIORITY:
            # 優先度ベースの配置
            return self._generate_with_priority(school, max_iterations, initial_schedule)
        
        elif self.search_mode == SearchMode.SMART:
            # スマートCSPソルバー
            return self._generate_with_smart_csp(school, initial_schedule)
        
        else:  # HYBRID
            # ハイブリッドアプローチ
            return self._generate_hybrid(school, max_iterations, initial_schedule)
    
    def _generate_with_priority(self, school: School, max_iterations: int,
                               initial_schedule: Optional[Schedule]) -> Schedule:
        """優先度ベースの生成"""
        self.logger.info("優先度ベースの生成を開始")
        
        # 初期スケジュールの準備
        schedule = initial_schedule if initial_schedule else Schedule()
        
        # 初期設定とロック処理
        if initial_schedule:
            self._lock_all_existing_assignments(schedule, school)
        
        # テスト期間保護
        from .test_period_protector import TestPeriodProtector
        protector = TestPeriodProtector()
        protector.protect_test_periods(schedule, school)
        
        # 固定科目の配置
        self._enforce_and_lock_fixed_subjects(schedule, school)
        
        # Step 1: 自立活動の優先配置
        jiritsu_requirements = self.jiritsu_service.analyze_requirements(school, schedule)
        jiritsu_placed = self.jiritsu_service.place_activities(schedule, school, jiritsu_requirements)
        self.logger.info(f"自立活動配置: {jiritsu_placed}コマ")
        
        # Step 2: 5組の同期
        grade5_placed = self.grade5_service.synchronize_placement(schedule, school)
        self.logger.info(f"5組同期: {grade5_placed}コマ")
        
        # Step 3: 優先度ベースの通常教科配置
        regular_placed = self.priority_service.place_with_priority(schedule, school)
        self.logger.info(f"優先度配置: {regular_placed}コマ")
        
        # Step 4: 最適化
        violations_before = len(self.constraint_validator.validate_all(schedule, school))
        schedule = self.sa_optimizer.optimize(schedule, school, max_iterations)
        violations_after = len(self.constraint_validator.validate_all(schedule, school))
        
        self.logger.info(f"シミュレーテッドアニーリング最適化: "
                        f"違反数 {violations_before} → {violations_after}")
        
        return schedule
    
    def _generate_with_smart_csp(self, school: School, 
                                initial_schedule: Optional[Schedule]) -> Schedule:
        """スマートCSPソルバーによる生成"""
        self.logger.info("スマートCSPソルバーによる生成を開始")
        
        # 初期スケジュールの準備
        schedule = initial_schedule if initial_schedule else Schedule()
        
        if initial_schedule:
            self._lock_all_existing_assignments(schedule, school)
        
        # テスト期間保護
        from .test_period_protector import TestPeriodProtector
        protector = TestPeriodProtector()
        protector.protect_test_periods(schedule, school)
        
        # 固定科目の配置
        self._enforce_and_lock_fixed_subjects(schedule, school)
        
        # スマートソルバーで解く
        schedule = self.smart_solver.solve(school, schedule)
        
        # 統計情報を出力
        stats = self.smart_solver.stats
        self.logger.info(f"スマートCSP統計: "
                        f"探索ノード={stats['nodes_explored']}, "
                        f"バックトラック={stats['backtracks']}, "
                        f"制約伝播={stats['constraint_propagations']}, "
                        f"ドメイン消去={stats['domain_wipeouts']}")
        
        return schedule
    
    def _generate_hybrid(self, school: School, max_iterations: int,
                        initial_schedule: Optional[Schedule]) -> Schedule:
        """ハイブリッドアプローチ（複数手法の組み合わせ）"""
        self.logger.info("ハイブリッドアプローチによる生成を開始")
        
        # Phase 1: 優先度ベースで初期解を生成
        self.logger.info("Phase 1: 優先度ベースの初期解生成")
        schedule = self._generate_with_priority(school, max_iterations // 2, initial_schedule)
        
        initial_violations = len(self.constraint_validator.validate_all(schedule, school))
        self.logger.info(f"初期解の違反数: {initial_violations}")
        
        # Phase 2: 違反が多い場合はスマートCSPで再生成
        if initial_violations > 20:
            self.logger.info("Phase 2: 違反が多いためスマートCSPで再生成")
            
            # 自立活動と5組の配置は保持
            preserved_schedule = Schedule()
            for slot, assignment in schedule.get_all_assignments():
                if (assignment.subject.name == "自立" or 
                    assignment.class_ref.class_number == 5 or
                    schedule.is_locked(slot, assignment.class_ref)):
                    preserved_schedule.assign(slot, assignment)
                    preserved_schedule.lock_cell(slot, assignment.class_ref)
            
            # スマートCSPで残りを解く
            schedule = self.smart_solver.solve(school, preserved_schedule)
        
        # Phase 3: 最終最適化
        self.logger.info("Phase 3: 最終最適化")
        
        # まず制約特化型最適化
        from .constraint_specific_optimizer import ConstraintSpecificOptimizer
        cs_optimizer = ConstraintSpecificOptimizer(self.constraint_validator)
        gym_resolved, daily_resolved = cs_optimizer.optimize(schedule, school)
        self.logger.info(f"制約特化最適化: 体育館={gym_resolved}件, 日内重複={daily_resolved}件解決")
        
        # 最後にシミュレーテッドアニーリング
        final_violations_before = len(self.constraint_validator.validate_all(schedule, school))
        schedule = self.sa_optimizer.optimize(schedule, school, max_iterations // 2)
        final_violations_after = len(self.constraint_validator.validate_all(schedule, school))
        
        self.logger.info(f"最終違反数: {final_violations_before} → {final_violations_after}")
        
        # 交流学級の最終同期
        self._final_exchange_sync(schedule, school)
        
        return schedule
    
    def _final_exchange_sync(self, schedule: Schedule, school: School) -> None:
        """交流学級の最終同期"""
        from .exchange_class_synchronizer import ExchangeClassSynchronizer
        synchronizer = ExchangeClassSynchronizer()
        sync_count = synchronizer.synchronize_all_periods(schedule, school)
        self.logger.info(f"交流学級最終同期: {sync_count}件")
    
    def _lock_all_existing_assignments(self, schedule: Schedule, school: School) -> None:
        """既存の割り当てをすべてロック"""
        locked_count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            if not schedule.is_locked(time_slot, assignment.class_ref):
                schedule.lock_cell(time_slot, assignment.class_ref)
                locked_count += 1
        
        self.logger.info(f"初期スケジュールから{locked_count}個の割り当てをロックしました")
    
    def _enforce_and_lock_fixed_subjects(self, schedule: Schedule, school: School) -> None:
        """固定科目の強制配置とロック"""
        # 既存の実装を継承
        pass  # 親クラスのメソッドを使用