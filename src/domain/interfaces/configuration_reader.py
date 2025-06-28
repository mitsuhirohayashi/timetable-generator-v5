"""設定情報の読み込みインターフェース"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class IConfigurationReader(ABC):
    """設定情報を読み込むためのインターフェース"""
    
    @abstractmethod
    def get_grade5_classes(self) -> List[str]:
        """5組クラスのリストを取得
        
        Returns:
            List[str]: 5組クラス名のリスト
        """
        pass
    
    @abstractmethod
    def get_meeting_times(self) -> Dict[str, Dict[str, Any]]:
        """会議時間の設定を取得
        
        Returns:
            Dict[str, Dict[str, Any]]: 会議名をキー、設定情報を値とする辞書
            例: {
                "HF": {"day": "火", "period": 4, "participants": [...]},
                "企画": {"day": "火", "period": 3, "participants": [...]}
            }
        """
        pass
    
    @abstractmethod
    def get_fixed_subjects(self) -> List[str]:
        """固定科目のリストを取得
        
        Returns:
            List[str]: 固定科目名のリスト
        """
        pass
    
    @abstractmethod
    def get_jiritsu_subjects(self) -> List[str]:
        """自立活動関連科目のリストを取得
        
        Returns:
            List[str]: 自立活動関連科目名のリスト
        """
        pass
    
    @abstractmethod
    def get_exchange_class_pairs(self) -> List[tuple[str, str]]:
        """交流学級と親学級のペアリストを取得
        
        Returns:
            List[tuple[str, str]]: (交流学級, 親学級)のタプルのリスト
        """
        pass
    
    @abstractmethod
    def get_config_value(self, key: str, default: Optional[Any] = None) -> Any:
        """指定されたキーの設定値を取得
        
        Args:
            key: 設定キー
            default: デフォルト値
            
        Returns:
            Any: 設定値
        """
        pass
    
    @abstractmethod
    def get_meeting_info(self) -> Dict[tuple[str, int], tuple[str, List[str]]]:
        """会議情報を取得
        
        Returns:
            Dict[tuple[str, int], tuple[str, List[str]]]: 
            (曜日, 校時)をキー、(会議名, 参加教員リスト)を値とする辞書
        """
        pass