"""ファイルパス設定のアダプター実装"""

from pathlib import Path
from ...domain.interfaces.path_configuration import IPathConfiguration
from ..config.path_config import path_config


class PathConfigurationAdapter(IPathConfiguration):
    """既存のpath_configをIPathConfigurationに適合させるアダプター"""
    
    def __init__(self):
        self._path_config = path_config
    
    @property
    def data_dir(self) -> Path:
        """データディレクトリのパス"""
        return self._path_config.data_dir
    
    @property
    def config_dir(self) -> Path:
        """設定ファイルディレクトリのパス"""
        return self._path_config.config_dir
    
    @property
    def input_dir(self) -> Path:
        """入力ファイルディレクトリのパス"""
        return self._path_config.input_dir
    
    @property
    def output_dir(self) -> Path:
        """出力ファイルディレクトリのパス"""
        return self._path_config.output_dir
    
    @property
    def base_timetable_csv(self) -> Path:
        """基本時間割CSVファイルのパス"""
        return self._path_config.base_timetable_csv
    
    @property
    def input_csv(self) -> Path:
        """入力CSVファイルのパス"""
        return self._path_config.input_csv
    
    @property
    def followup_csv(self) -> Path:
        """Follow-up CSVファイルのパス"""
        return self._path_config.followup_csv
    
    @property
    def default_output_csv(self) -> Path:
        """デフォルト出力CSVファイルのパス"""
        return self._path_config.default_output_csv
    
    def get_path(self, path_type: str) -> Path:
        """指定されたタイプのパスを取得"""
        path_mapping = {
            'data': self.data_dir,
            'config': self.config_dir,
            'input': self.input_dir,
            'output': self.output_dir,
            'base_timetable': self.base_timetable_csv,
            'input_csv': self.input_csv,
            'followup': self.followup_csv,
            'default_output': self.default_output_csv,
        }
        
        return path_mapping.get(path_type, self.data_dir)