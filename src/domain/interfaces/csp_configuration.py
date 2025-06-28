"""制約充足問題(CSP)アルゴリズムの設定インターフェース"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ICSPConfiguration(ABC):
    """CSPアルゴリズムの設定を管理するインターフェース"""
    
    @abstractmethod
    def get_max_iterations(self) -> int:
        """最大反復回数を取得
        
        Returns:
            int: 最大反復回数
        """
        pass
    
    @abstractmethod
    def get_backtrack_limit(self) -> int:
        """バックトラックの制限回数を取得
        
        Returns:
            int: バックトラック制限回数
        """
        pass
    
    @abstractmethod
    def get_local_search_iterations(self) -> int:
        """局所探索の反復回数を取得
        
        Returns:
            int: 局所探索反復回数
        """
        pass
    
    @abstractmethod
    def get_tabu_tenure(self) -> int:
        """タブーサーチの保持期間を取得
        
        Returns:
            int: タブー保持期間
        """
        pass
    
    @abstractmethod
    def get_timeout_seconds(self) -> Optional[int]:
        """タイムアウト秒数を取得
        
        Returns:
            Optional[int]: タイムアウト秒数（Noneの場合は無制限）
        """
        pass
    
    @abstractmethod
    def is_constraint_propagation_enabled(self) -> bool:
        """制約伝播が有効かどうかを取得
        
        Returns:
            bool: 有効の場合True
        """
        pass
    
    @abstractmethod
    def is_arc_consistency_enabled(self) -> bool:
        """アーク整合性が有効かどうかを取得
        
        Returns:
            bool: 有効の場合True
        """
        pass
    
    @abstractmethod
    def get_search_strategy(self) -> str:
        """探索戦略を取得
        
        Returns:
            str: 探索戦略名（'mrv', 'degree', 'random' など）
        """
        pass
    
    @abstractmethod
    def get_value_ordering_strategy(self) -> str:
        """値順序戦略を取得
        
        Returns:
            str: 値順序戦略名（'lcv', 'random' など）
        """
        pass
    
    @abstractmethod
    def get_all_parameters(self) -> Dict[str, Any]:
        """すべてのパラメータを辞書形式で取得
        
        Returns:
            Dict[str, Any]: パラメータ名をキー、値を値とする辞書
        """
        pass
    
    @property
    @abstractmethod
    def weekdays(self) -> list:
        """平日のリストを取得
        
        Returns:
            list: 平日のリスト（例: ["月", "火", "水", "木", "金"]）
        """
        pass
    
    @property
    @abstractmethod
    def periods_min(self) -> int:
        """最小時限を取得
        
        Returns:
            int: 最小時限（通常は1）
        """
        pass
    
    @property
    @abstractmethod
    def periods_max(self) -> int:
        """最大時限を取得
        
        Returns:
            int: 最大時限（通常は6）
        """
        pass