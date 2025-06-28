"""改良版スケジュール生成サービス

改良版のCSPオーケストレーターと制約検証器を使用して、
より確実な時間割生成を実現します。
"""
import logging
from typing import Optional, Dict, Any

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.services.csp_orchestrator_improved import CSPOrchestratorImproved
from ...domain.services.constraint_validator_improved import ConstraintValidatorImproved
from ...domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
from ...domain.services.integrated_optimizer_improved import IntegratedOptimizerImproved
from ...infrastructure.parsers.enhanced_followup_parser import EnhancedFollowupParser
from ...infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfigLoader
from ...infrastructure.config.constraint_loader import ConstraintLoader


class ScheduleGenerationServiceImproved:
    """改良版スケジュール生成サービス
    
    改良版のコンポーネントを使用して、制約違反を最小化した
    時間割生成を実現します。
    """
    
    def __init__(self,
                 constraint_loader: Optional[ConstraintLoader] = None,
                 followup_parser: Optional[EnhancedFollowupParser] = None,
                 csp_config_loader: Optional[AdvancedCSPConfigLoader] = None):
        """初期化
        
        Args:
            constraint_loader: 制約ローダー
            followup_parser: フォローアップパーサー
            csp_config_loader: CSP設定ローダー
        """
        self.logger = logging.getLogger(__name__)
        
        # 依存性注入
        if constraint_loader is None:
            from ...infrastructure.di_container import get_constraint_loader
            constraint_loader = get_constraint_loader()
        if followup_parser is None:
            from ...infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
        if csp_config_loader is None:
            from ...infrastructure.di_container import get_csp_configuration
            csp_config_loader = get_csp_configuration()
        
        self.constraint_loader = constraint_loader
        self.followup_parser = followup_parser
        self.csp_config = csp_config_loader
        
        # 改良版コンポーネントの初期化
        self.constraint_validator = ConstraintValidatorImproved()
        self.csp_orchestrator = CSPOrchestratorImproved(
            constraint_validator=self.constraint_validator,
            csp_config=self.csp_config,
            followup_parser=self.followup_parser
        )
        self.empty_slot_filler = SmartEmptySlotFiller()
        self.integrated_optimizer = IntegratedOptimizerImproved()
    
    def generate_schedule(self,
                         school: School,
                         initial_schedule: Optional[Schedule] = None,
                         parameters: Optional[Dict[str, Any]] = None) -> Schedule:
        """改良版時間割生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            parameters: 生成パラメータ
            
        Returns:
            生成された時間割
        """
        self.logger.info("=== 改良版スケジュール生成を開始 ===")
        
        # パラメータの取得
        params = parameters or {}
        max_iterations = params.get('max_iterations', 200)
        enable_optimization = params.get('enable_optimization', True)
        
        try:
            # Phase 1: CSPによる基本生成（改良版）
            self.logger.info("Phase 1: 改良版CSPによる基本生成")
            schedule = self.csp_orchestrator.generate(
                school=school,
                max_iterations=max_iterations,
                initial_schedule=initial_schedule
            )
            
            # Phase 2: 空きスロット埋め（統合済み）
            self.logger.info("Phase 2: 空きスロット埋め")
            filled_count = self.empty_slot_filler.fill_empty_slots(schedule, school)
            self.logger.info(f"空きスロット埋め完了: {filled_count}スロット")
            
            # Phase 3: 統合最適化（オプション）
            if enable_optimization:
                self.logger.info("Phase 3: 統合最適化")
                optimization_stats = self.integrated_optimizer.optimize(schedule, school)
                self._log_optimization_stats(optimization_stats)
            
            # Phase 4: 最終検証
            self.logger.info("Phase 4: 最終検証")
            violations = self.constraint_validator.validate_all_constraints(schedule, school)
            self._log_violations(violations)
            
            self.logger.info("=== 改良版スケジュール生成完了 ===")
            return schedule
            
        except Exception as e:
            self.logger.error(f"スケジュール生成中にエラーが発生: {e}", exc_info=True)
            raise
    
    def _log_optimization_stats(self, stats: Dict[str, Any]) -> None:
        """最適化統計をログ出力"""
        if not stats:
            return
        
        self.logger.info("=== 最適化統計 ===")
        for key, value in stats.items():
            self.logger.info(f"{key}: {value}")
    
    def _log_violations(self, violations: list) -> None:
        """制約違反をログ出力"""
        if not violations:
            self.logger.info("制約違反なし！")
            return
        
        self.logger.warning(f"=== 制約違反: {len(violations)}件 ===")
        
        # 違反をタイプ別に集計
        violation_counts = {}
        for v in violations:
            vtype = v.get('type', 'unknown')
            violation_counts[vtype] = violation_counts.get(vtype, 0) + 1
        
        for vtype, count in violation_counts.items():
            self.logger.warning(f"- {vtype}: {count}件")
        
        # 最初の5件を詳細表示
        for v in violations[:5]:
            self.logger.warning(f"  詳細: {v.get('message', v)}")