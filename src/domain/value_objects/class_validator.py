"""クラスの妥当性を検証するモジュール（統合版）"""
from typing import Set, Dict, Optional, Tuple
from pathlib import Path
import csv
import logging
from .subject_config import ClassConfig


class ClassValidator:
    """クラスの妥当性を検証するクラス（統合版）
    
    このクラスは以下の機能を統合:
    - ClassValidator（CSVファイルから直接読み込む版）
    - ClassValidator_new（ClassConfigを使用する版）
    """
    
    _instance: Optional['ClassValidator'] = None
    _config: Optional[ClassConfig] = None
    _valid_class_numbers: Optional[Dict[str, Set[int]]] = None
    _exchange_class_mapping: Optional[Dict[Tuple[int, int], Tuple[Tuple[int, int], Set[str]]]] = None
    
    def __new__(cls, config: Optional[ClassConfig] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            if config is not None:
                cls._config = config
                cls._instance._load_from_config()
            else:
                cls._instance._load_from_csv()
        elif config is not None:
            # 新しい設定で更新
            cls._config = config
            cls._instance._load_from_config()
        return cls._instance
    
    @classmethod
    def initialize(cls, config: ClassConfig) -> 'ClassValidator':
        """設定を指定して初期化"""
        cls._instance = None
        return cls(config)
    
    def _load_from_config(self):
        """設定オブジェクトから読み込み（旧class_validator_new）"""
        self._valid_class_numbers = {
            '通常学級': self._config.regular_class_numbers,
            '特別支援学級': self._config.special_needs_class_numbers,
            '交流学級': self._config.exchange_class_numbers
        }
        self._exchange_class_mapping = self._config.exchange_class_mappings
    
    def _load_from_csv(self):
        """CSVファイルから直接読み込み（旧class_validator）"""
        logger = logging.getLogger(__name__)
        config_path = Path("data/config")
        
        # 有効なクラス番号を読み込む
        self._valid_class_numbers = {
            '通常学級': set(),
            '特別支援学級': set(),
            '交流学級': set()
        }
        
        system_constants_path = config_path / "system_constants.csv"
        if system_constants_path.exists():
            try:
                with open(system_constants_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['設定名'].strip() == '通常学級番号':
                            self._valid_class_numbers['通常学級'] = {int(n.strip()) for n in row['値'].split('・')}
                        elif row['設定名'].strip() == '特別支援学級番号':
                            self._valid_class_numbers['特別支援学級'] = {int(row['値'].strip())}
                        elif row['設定名'].strip() == '交流学級番号':
                            self._valid_class_numbers['交流学級'] = {int(n.strip()) for n in row['値'].split('・')}
            except Exception as e:
                logger.error(f"クラス番号読み込みエラー: {e}")
        
        # デフォルト値を設定
        if not self._valid_class_numbers['通常学級']:
            self._valid_class_numbers = {
                '通常学級': {1, 2, 3},
                '特別支援学級': {5},
                '交流学級': {6, 7}
            }
        
        # 交流学級マッピングを読み込む
        self._exchange_class_mapping = {}
        exchange_mapping_path = config_path / "exchange_class_mapping.csv"
        if exchange_mapping_path.exists():
            try:
                with open(exchange_mapping_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # 交流学級
                        exchange_class = row['交流学級'].strip()
                        eg = int(exchange_class[0])
                        ec = int(exchange_class[2])
                        
                        # 親学級
                        parent_class = row['親学級'].strip()
                        pg = int(parent_class[0])
                        pc = int(parent_class[2])
                        
                        # 自立時の親学級配置教科
                        subjects = set()
                        if '数または英' in row['親学級配置教科（自立時）']:
                            subjects = {'数', '英'}
                        
                        self._exchange_class_mapping[(eg, ec)] = ((pg, pc), subjects)
            except Exception as e:
                logger.error(f"交流学級マッピング読み込みエラー: {e}")
        
        # デフォルト値を設定
        if not self._exchange_class_mapping:
            self._exchange_class_mapping = {
                (1, 6): ((1, 1), {'数', '英'}),
                (1, 7): ((1, 2), {'数', '英'}),
                (2, 6): ((2, 3), {'数', '英'}),
                (2, 7): ((2, 2), {'数', '英'}),
                (3, 6): ((3, 3), {'数', '英'}),
                (3, 7): ((3, 2), {'数', '英'}),
            }
    
    @property
    def all_valid_class_numbers(self) -> Set[int]:
        """すべての有効なクラス番号を返す"""
        if self._config:
            return (self._config.regular_class_numbers | 
                    self._config.special_needs_class_numbers | 
                    self._config.exchange_class_numbers)
        else:
            return (self._valid_class_numbers['通常学級'] | 
                    self._valid_class_numbers['特別支援学級'] | 
                    self._valid_class_numbers['交流学級'])
    
    def is_regular_class(self, class_number: int) -> bool:
        """通常学級かどうか判定"""
        if self._config:
            return class_number in self._config.regular_class_numbers
        else:
            return class_number in self._valid_class_numbers['通常学級']
    
    def is_special_needs_class(self, class_number: int) -> bool:
        """特別支援学級かどうか判定"""
        if self._config:
            return class_number in self._config.special_needs_class_numbers
        else:
            return class_number in self._valid_class_numbers['特別支援学級']
    
    def is_exchange_class(self, class_number: int) -> bool:
        """交流学級かどうか判定"""
        if self._config:
            return class_number in self._config.exchange_class_numbers
        else:
            return class_number in self._valid_class_numbers['交流学級']
    
    def get_exchange_parent_info(self, grade: int, class_number: int) -> Optional[Tuple[Tuple[int, int], Set[str]]]:
        """交流学級の親学級情報を取得"""
        if self._config:
            return self._config.exchange_class_mappings.get((grade, class_number))
        else:
            return self._exchange_class_mapping.get((grade, class_number))
    
    def get_grade5_team_teaching_teachers(self) -> Set[str]:
        """5組のチームティーチング教師を取得"""
        if self._config and hasattr(self._config, 'grade5_team_teaching_teachers'):
            return self._config.grade5_team_teaching_teachers
        else:
            # デフォルト値
            return {"金子み", "寺田", "梶永"}