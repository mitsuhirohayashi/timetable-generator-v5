"""ファイルパス設定のインターフェース"""

from abc import ABC, abstractmethod
from pathlib import Path


class IPathConfiguration(ABC):
    """ファイルパス情報を管理するインターフェース"""
    
    @property
    @abstractmethod
    def data_dir(self) -> Path:
        """データディレクトリのパス"""
        pass
    
    @property
    @abstractmethod
    def config_dir(self) -> Path:
        """設定ファイルディレクトリのパス"""
        pass
    
    @property
    @abstractmethod
    def input_dir(self) -> Path:
        """入力ファイルディレクトリのパス"""
        pass
    
    @property
    @abstractmethod
    def output_dir(self) -> Path:
        """出力ファイルディレクトリのパス"""
        pass
    
    @property
    @abstractmethod
    def base_timetable_csv(self) -> Path:
        """基本時間割CSVファイルのパス"""
        pass
    
    @property
    @abstractmethod
    def input_csv(self) -> Path:
        """入力CSVファイルのパス"""
        pass
    
    @property
    @abstractmethod
    def followup_csv(self) -> Path:
        """Follow-up CSVファイルのパス"""
        pass
    
    @property
    @abstractmethod
    def default_output_csv(self) -> Path:
        """デフォルト出力CSVファイルのパス"""
        pass
    
    @abstractmethod
    def get_path(self, path_type: str) -> Path:
        """指定されたタイプのパスを取得
        
        Args:
            path_type: パスタイプ（'config', 'input', 'output' など）
            
        Returns:
            Path: ファイルパス
        """
        pass