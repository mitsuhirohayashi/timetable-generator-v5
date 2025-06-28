"""設定情報のアダプター実装"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import csv
import logging

from ...domain.interfaces.configuration_reader import IConfigurationReader
from ..repositories.config_repository import ConfigRepository


class ConfigurationAdapter(IConfigurationReader):
    """既存のConfigRepositoryをIConfigurationReaderに適合させるアダプター"""
    
    def __init__(self, config_path: Path = None):
        self._repository = ConfigRepository(config_path) if config_path else ConfigRepository()
        self.logger = logging.getLogger(__name__)
        self._config_cache = {}
        self._load_basic_config()
    
    def get_grade5_classes(self) -> List[str]:
        """5組クラスのリストを取得"""
        # ハードコーディングされているが、将来的には設定ファイルから読み込む
        return ["1年5組", "2年5組", "3年5組"]
    
    def get_meeting_times(self) -> Dict[str, Dict[str, Any]]:
        """会議時間の設定を取得"""
        # デフォルトの会議時間
        meetings = {
            "HF": {"day": "火", "period": 4, "participants": []},
            "企画": {"day": "火", "period": 3, "participants": []},
            "特会": {"day": "水", "period": 2, "participants": []},
            "生指": {"day": "木", "period": 3, "participants": []},
            "初研": {"day": "木", "period": 6, "participants": []}
        }
        
        # 設定ファイルから読み込み（存在する場合）
        meeting_config_path = self._repository.config_path / "meeting_times.csv"
        if meeting_config_path.exists():
            try:
                with open(meeting_config_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        meeting_name = row.get('会議名', '').strip()
                        if meeting_name:
                            meetings[meeting_name] = {
                                "day": row.get('曜日', ''),
                                "period": int(row.get('時限', 0)),
                                "participants": row.get('参加者', '').split(',')
                            }
            except Exception as e:
                self.logger.warning(f"会議時間設定の読み込みエラー: {e}")
        
        return meetings
    
    def get_fixed_subjects(self) -> List[str]:
        """固定科目のリストを取得"""
        # ConfigRepositoryから取得
        fixed_subjects = self._repository.load_fixed_subjects()
        if fixed_subjects:
            return list(fixed_subjects)
        
        # フォールバックとしてハードコーディングされた値を返す
        return ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家", ""]
    
    def get_jiritsu_subjects(self) -> List[str]:
        """自立活動関連科目のリストを取得"""
        # ConfigRepositoryから特別支援科目を取得
        special_needs = self._repository.load_special_needs_subjects()
        if special_needs:
            return list(special_needs)
        
        # フォールバック
        return ["自立", "日生", "生単", "作業"]
    
    def get_exchange_class_pairs(self) -> List[tuple[str, str]]:
        """交流学級と親学級のペアリストを取得"""
        # ConfigRepositoryから取得
        mapping = self._repository.load_exchange_class_mapping()
        if mapping:
            pairs = []
            for exchange_class, (parent_class, _) in mapping.items():
                pairs.append((str(exchange_class), str(parent_class)))
            return pairs
        
        # フォールバック
        return [
            ("1年6組", "1年1組"),
            ("1年7組", "1年2組"),
            ("2年6組", "2年3組"),
            ("2年7組", "2年2組"),
            ("3年6組", "3年3組"),
            ("3年7組", "3年2組"),
        ]
    
    def get_config_value(self, key: str, default: Optional[Any] = None) -> Any:
        """指定されたキーの設定値を取得"""
        return self._config_cache.get(key, default)
    
    def get_meeting_info(self) -> Dict[tuple[str, int], tuple[str, List[str]]]:
        """会議情報を取得"""
        # get_meeting_times() の結果を期待される形式に変換
        meeting_times = self.get_meeting_times()
        meeting_info = {}
        
        for meeting_name, config in meeting_times.items():
            day = config.get("day", "")
            period = config.get("period", 0)
            participants = config.get("participants", [])
            
            if day and period:
                meeting_info[(day, period)] = (meeting_name, participants)
        
        return meeting_info
    
    def _load_basic_config(self) -> None:
        """基本設定をロード"""
        # 将来的に設定ファイルから読み込む
        self._config_cache = {
            "weekdays": ["月", "火", "水", "木", "金"],
            "periods": list(range(1, 7)),
            "max_periods": 6,
        }