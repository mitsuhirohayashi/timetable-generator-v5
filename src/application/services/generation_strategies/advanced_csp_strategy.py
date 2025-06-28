"""高度なCSP生成戦略

標準のCSPアルゴリズムに加えて、複数の探索モードをサポートし、
より効率的なスケジュール生成を実現します。
"""
import logging
from typing import Optional, TYPE_CHECKING

from .base_generation_strategy import BaseGenerationStrategy
from .constraint_validator_adapter import ConstraintValidatorAdapter

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School


class AdvancedCSPStrategy(BaseGenerationStrategy):
    """高度なCSPアルゴリズムを使用した生成戦略"""
    
    def __init__(self, constraint_system):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        
    def get_name(self) -> str:
        return "advanced_csp"
    
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 100,
        **kwargs
    ) -> 'Schedule':
        """高度なCSPアルゴリズムでスケジュールを生成"""
        search_mode = kwargs.get('search_mode', 'standard')
        
        # テスト期間保持チェッカーを初期化
        from ....domain.services.core.test_period_preservation_check import TestPeriodPreservationChecker
        preservation_checker = TestPeriodPreservationChecker()
        
        # 入力データの補正（初期スケジュールがある場合）
        if initial_schedule:
            from ..input_data_corrector import InputDataCorrector
            corrector = InputDataCorrector()
            corrections = corrector.correct_input_schedule(initial_schedule, school)
            if corrections > 0:
                self.logger.info(f"入力データを{corrections}箇所補正しました")
        
        # アダプターを作成
        adapter = ConstraintValidatorAdapter(self.constraint_system)
        
        # search_modeに基づいて適切なOrchestratorを選択
        if search_mode != "standard":
            # 高度な探索モードを使用
            from ..csp_orchestrator import AdvancedCSPOrchestrator, SearchMode
            
            # search_modeをSearchMode列挙型に変換
            mode_map = {
                "priority": SearchMode.PRIORITY,
                "smart": SearchMode.SMART,
                "hybrid": SearchMode.HYBRID
            }
            search_enum = mode_map.get(search_mode, SearchMode.HYBRID)
            
            self.logger.info(f"高度な探索モード ({search_enum.value}) を使用します")
            csp_orchestrator = AdvancedCSPOrchestrator(adapter, None, search_enum)
        else:
            # 標準のCSPOrchestratorを使用
            from ..csp_orchestrator import CSPOrchestrator
            csp_orchestrator = CSPOrchestrator(adapter)
        
        # 生成実行
        schedule = csp_orchestrator.generate(school, max_iterations, initial_schedule)
        
        # テスト期間データ保持チェック（CSP生成後）
        if initial_schedule:
            self.logger.warning("=== CSP生成後のテスト期間データチェック ===")
            preservation_checker.check_test_period_preservation(initial_schedule, schedule, school)
        
        # 空きスロット埋め（別途実装必要）
        self._fill_empty_slots(schedule, school)
        
        # テスト期間データ保持チェック（空きスロット埋め後）
        if initial_schedule:
            self.logger.warning("=== 空きスロット埋め後のテスト期間データチェック ===")
            preservation_checker.check_test_period_preservation(initial_schedule, schedule, school)
        
        return schedule
    
    def _fill_empty_slots(self, schedule: 'Schedule', school: 'School'):
        """空きスロットを埋める（簡略実装）"""
        # 実際の実装は別モジュールから呼び出す
        pass