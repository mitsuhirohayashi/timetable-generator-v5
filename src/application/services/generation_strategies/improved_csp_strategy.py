"""改良版CSP生成戦略

キャッシング、バックトラッキング、優先度ベース配置を活用した
高度な制約充足アルゴリズムを使用します。
"""
import logging
from typing import Optional, TYPE_CHECKING

from .base_generation_strategy import BaseGenerationStrategy

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School


class ImprovedCSPStrategy(BaseGenerationStrategy):
    """改良版CSPアルゴリズムを使用した生成戦略"""
    
    def __init__(self, constraint_system):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        
    def get_name(self) -> str:
        return "improved_csp"
    
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 100,
        **kwargs
    ) -> 'Schedule':
        """改良版CSPアルゴリズムでスケジュールを生成"""
        self.logger.info("=== 改良版CSPアルゴリズムを使用 ===")
        
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
        
        # 改良版コンポーネントを使用
        from ....domain.services.unified_constraint_validator import UnifiedConstraintValidator
        from ..csp_orchestrator import CSPOrchestratorImproved
        
        # 統合制約検証器を作成
        improved_validator = UnifiedConstraintValidator(
            unified_system=self.constraint_system
        )
        
        # 改良版CSPオーケストレーターを作成
        csp_orchestrator = CSPOrchestratorImproved(improved_validator)
        
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