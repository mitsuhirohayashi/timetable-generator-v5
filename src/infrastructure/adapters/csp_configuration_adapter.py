"""制約充足問題(CSP)設定のアダプター実装"""

from typing import Dict, Any, Optional
from pathlib import Path
import logging

from ...domain.interfaces.csp_configuration import ICSPConfiguration
from ..config.advanced_csp_config_loader import AdvancedCSPConfig, AdvancedCSPConfigLoader


class CSPConfigurationAdapter(ICSPConfiguration):
    """既存のAdvancedCSPConfigをICSPConfigurationに適合させるアダプター"""
    
    def __init__(self, config_file: Path = None):
        self.logger = logging.getLogger(__name__)
        
        # 設定ファイルからロード
        if config_file:
            loader = AdvancedCSPConfigLoader(config_file)
            self._config = loader.load()
        else:
            # デフォルト設定を作成
            loader = AdvancedCSPConfigLoader()
            self._config = loader._create_default_config()
    
    def get_max_iterations(self) -> int:
        """最大反復回数を取得"""
        return self._config.max_iterations
    
    def get_backtrack_limit(self) -> int:
        """バックトラックの制限回数を取得"""
        return self._config.backtrack_limit
    
    def get_local_search_iterations(self) -> int:
        """局所探索の反復回数を取得"""
        return self._config.local_search_iterations
    
    def get_tabu_tenure(self) -> int:
        """タブーサーチの保持期間を取得"""
        return self._config.tabu_tenure
    
    def get_timeout_seconds(self) -> Optional[int]:
        """タイムアウト秒数を取得"""
        return self._config.timeout_seconds
    
    def is_constraint_propagation_enabled(self) -> bool:
        """制約伝播が有効かどうかを取得"""
        return self._config.enable_constraint_propagation
    
    def is_arc_consistency_enabled(self) -> bool:
        """アーク整合性が有効かどうかを取得"""
        return self._config.enable_arc_consistency
    
    def get_search_strategy(self) -> str:
        """探索戦略を取得"""
        return self._config.search_strategy
    
    def get_value_ordering_strategy(self) -> str:
        """値順序戦略を取得"""
        return self._config.value_ordering_strategy
    
    def get_all_parameters(self) -> Dict[str, Any]:
        """すべてのパラメータを辞書形式で取得"""
        return {
            "max_iterations": self._config.max_iterations,
            "backtrack_limit": self._config.backtrack_limit,
            "local_search_iterations": self._config.local_search_iterations,
            "tabu_tenure": self._config.tabu_tenure,
            "timeout_seconds": self._config.timeout_seconds,
            "enable_constraint_propagation": self._config.enable_constraint_propagation,
            "enable_arc_consistency": self._config.enable_arc_consistency,
            "search_strategy": self._config.search_strategy,
            "value_ordering_strategy": self._config.value_ordering_strategy,
            "priority_weights": self._config.priority_weights,
            "optimization_phases": self._config.optimization_phases,
            # Add missing parameters that are being accessed
            "jiritsu_subjects": self._config.jiritsu_subjects,
            "parent_subjects_for_jiritsu": self._config.parent_subjects_for_jiritsu,
            "exchange_parent_mappings": self._config.exchange_parent_mappings,
            "grade5_classes": self._config.grade5_classes,
            "fixed_subjects": self._config.fixed_subjects,
            "main_subjects": self._config.main_subjects,
            "skill_subjects": self._config.skill_subjects,
            "excluded_sync_subjects": self._config.excluded_sync_subjects,
            "weekdays": self._config.weekdays,
            "periods_min": self._config.periods_min,
            "periods_max": self._config.periods_max,
            "monday_period_6": self._config.monday_period_6,
            "yt_days": self._config.yt_days,
            "pe_preferred_day": self._config.pe_preferred_day,
            "main_subjects_preferred_periods": self._config.main_subjects_preferred_periods,
            "skill_subjects_preferred_periods": self._config.skill_subjects_preferred_periods,
            "swap_attempts": self._config.swap_attempts,
            "temperature": self._config.temperature,
        }
    
    @property
    def weekdays(self) -> list:
        """平日のリストを取得"""
        return self._config.weekdays
    
    @property
    def periods_min(self) -> int:
        """最小時限を取得"""
        return self._config.periods_min
    
    @property
    def periods_max(self) -> int:
        """最大時限を取得"""
        return self._config.periods_max