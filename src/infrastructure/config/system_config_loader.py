"""システム設定ローダー

JSONファイルから設定を読み込み、アプリケーション全体で使用する設定を管理します。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, FrozenSet
from dataclasses import dataclass, field

from ...shared.mixins.logging_mixin import LoggingMixin
from ...shared.utils.validation_utils import ValidationUtils
from ...domain.interfaces.configuration_reader import IConfigurationReader


@dataclass
class SystemConfig:
    """システム設定を保持するデータクラス"""
    weekdays: List[str]
    periods: Dict[str, int]
    grade5_classes: List[str]
    fixed_subjects: FrozenSet[str]
    jiritsu_subjects: FrozenSet[str]
    jiritsu_parent_subjects: FrozenSet[str]
    meeting_types: FrozenSet[str]
    default_meetings: Dict[str, tuple[str, int]]
    core_subjects: FrozenSet[str]
    special_subjects: FrozenSet[str]
    other_subjects: FrozenSet[str]
    exchange_class_pairs: Dict[str, str]
    standard_hours: Dict[str, int]
    constraint_priorities: Dict[str, int]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """辞書からSystemConfigインスタンスを生成"""
        return cls(
            weekdays=data['weekdays'],
            periods=data['periods'],
            grade5_classes=data['grade5_classes'],
            fixed_subjects=frozenset(data['fixed_subjects']),
            jiritsu_subjects=frozenset(data['jiritsu']['subjects']),
            jiritsu_parent_subjects=frozenset(data['jiritsu']['parent_subjects']),
            meeting_types=frozenset(data['meetings']['types']),
            default_meetings={
                k: (v['day'], v['period']) 
                for k, v in data['meetings']['defaults'].items()
            },
            core_subjects=frozenset(data['subject_categories']['core']),
            special_subjects=frozenset(data['subject_categories']['special']),
            other_subjects=frozenset(data['subject_categories']['other']),
            exchange_class_pairs=data['exchange_class_pairs'],
            standard_hours=data['standard_hours'],
            constraint_priorities=data['constraint_priorities']
        )


class SystemConfigLoader(LoggingMixin):
    """システム設定をJSONファイルから読み込むローダー"""
    
    def __init__(self, config_path: Optional[Path] = None):
        super().__init__()
        self._config_path = config_path
        self._config: Optional[SystemConfig] = None
        self._raw_data: Optional[Dict[str, Any]] = None
    
    def load(self, config_file: str = "system_config.json") -> SystemConfig:
        """設定ファイルを読み込む
        
        Args:
            config_file: 設定ファイル名
            
        Returns:
            SystemConfig: システム設定
            
        Raises:
            FileNotFoundError: 設定ファイルが見つからない場合
            json.JSONDecodeError: JSONパースエラー
        """
        if self._config_path:
            file_path = self._config_path / config_file
        else:
            # デフォルトパスを使用
            from ..config.path_config import path_config
            file_path = path_config.config_dir / config_file
        
        if not file_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self._raw_data = json.load(f)
            
            self._config = SystemConfig.from_dict(self._raw_data)
            self.logger.info(f"設定ファイルを読み込みました: {file_path}")
            
            return self._config
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONパースエラー: {e}")
            raise
        except Exception as e:
            self.logger.error(f"設定ファイル読み込みエラー: {e}")
            raise
    
    def get_config(self) -> Optional[SystemConfig]:
        """読み込み済みの設定を取得"""
        return self._config
    
    def reload(self) -> SystemConfig:
        """設定を再読み込み"""
        self._config = None
        self._raw_data = None
        return self.load()
    
    # IConfigurationReader インターフェース実装
    def read_configuration(self, config_type: str) -> Dict[str, Any]:
        """指定されたタイプの設定を読み込む"""
        if not self._raw_data:
            self.load()
        
        if config_type in self._raw_data:
            return self._raw_data[config_type]
        else:
            return {}
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """設定値を取得"""
        if not self._raw_data:
            self.load()
        
        # ネストしたキーに対応（例: "meetings.defaults.HF"）
        keys = key.split('.')
        value = self._raw_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def has_key(self, key: str) -> bool:
        """キーが存在するかチェック"""
        if not self._raw_data:
            self.load()
        
        keys = key.split('.')
        value = self._raw_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False
        
        return True


# シングルトンインスタンス
_system_config_loader = SystemConfigLoader()


def get_system_config() -> SystemConfig:
    """システム設定を取得（シングルトン）"""
    if not _system_config_loader.get_config():
        _system_config_loader.load()
    return _system_config_loader.get_config()


def reload_system_config() -> SystemConfig:
    """システム設定を再読み込み"""
    return _system_config_loader.reload()