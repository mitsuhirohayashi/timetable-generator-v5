"""CSPサービスのファクトリー"""
from typing import Dict, Any

from .interfaces.jiritsu_placement_service import JiritsuPlacementService
from .interfaces.grade5_synchronization_service import Grade5SynchronizationService
from .interfaces.regular_subject_placement_service import RegularSubjectPlacementService
from .interfaces.local_search_optimizer import LocalSearchOptimizer
from .interfaces.schedule_evaluator import ScheduleEvaluator

from .implementations.backtrack_jiritsu_placement_service import BacktrackJiritsuPlacementService
from .implementations.synchronized_grade5_service import SynchronizedGrade5Service
from .implementations.greedy_subject_placement_service import GreedySubjectPlacementService
from .implementations.random_swap_optimizer import RandomSwapOptimizer
from .implementations.weighted_schedule_evaluator import WeightedScheduleEvaluator

from .csp_orchestrator import CSPOrchestrator
from ..constraints.base import ConstraintValidator
from ...infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfig


class CSPServiceFactory:
    """CSPサービスのファクトリー
    
    設定に基づいて適切なサービス実装を生成する
    """
    
    @staticmethod
    def create_services(config: AdvancedCSPConfig, 
                       constraint_validator: ConstraintValidator) -> Dict[str, Any]:
        """設定に基づいてサービスを生成
        
        Args:
            config: CSP設定
            constraint_validator: 制約バリデーター
            
        Returns:
            サービスの辞書
        """
        # 評価器を最初に作成（他のサービスが依存するため）
        evaluator = WeightedScheduleEvaluator(config, constraint_validator)
        
        # 各サービスを作成
        services = {
            'jiritsu_service': BacktrackJiritsuPlacementService(config, constraint_validator),
            'grade5_service': SynchronizedGrade5Service(config, constraint_validator),
            'regular_service': GreedySubjectPlacementService(config, constraint_validator),
            'optimizer': RandomSwapOptimizer(config, constraint_validator, evaluator),
            'evaluator': evaluator
        }
        
        return services
    
    @staticmethod
    def create_orchestrator(config: AdvancedCSPConfig,
                           constraint_validator: ConstraintValidator) -> CSPOrchestrator:
        """CSPオーケストレーターを作成
        
        Args:
            config: CSP設定
            constraint_validator: 制約バリデーター
            
        Returns:
            CSPオーケストレーター
        """
        services = CSPServiceFactory.create_services(config, constraint_validator)
        
        return CSPOrchestrator(
            jiritsu_service=services['jiritsu_service'],
            grade5_service=services['grade5_service'],
            regular_service=services['regular_service'],
            optimizer=services['optimizer'],
            evaluator=services['evaluator'],
            config=config
        )