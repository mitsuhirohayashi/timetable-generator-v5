"""教科の妥当性を検証するモジュール（統合版）"""
from typing import Set, Optional, Dict
from pathlib import Path
import csv
import logging
from .subject_config import SubjectConfig


class SubjectValidator:
    """教科の妥当性を検証するクラス（統合版）
    
    このクラスは以下の機能を統合:
    - SubjectValidator（CSVファイルから直接読み込む版）
    - SubjectValidator_new（SubjectConfigを使用する版）
    """
    
    _instance: Optional['SubjectValidator'] = None
    _config: Optional[SubjectConfig] = None
    _valid_subjects: Optional[Set[str]] = None
    _special_needs_subjects: Optional[Set[str]] = None
    _fixed_subjects: Optional[Set[str]] = None
    _subject_names: Optional[Dict[str, str]] = None
    _default_teachers: Optional[Dict[str, str]] = None
    
    def __new__(cls, config: Optional[SubjectConfig] = None):
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
    def initialize(cls, config: SubjectConfig) -> 'SubjectValidator':
        """設定を指定して初期化"""
        cls._instance = None
        return cls(config)
    
    def _load_from_config(self):
        """設定オブジェクトから読み込み（旧subject_validator_new）"""
        self._valid_subjects = self._config.valid_subjects
        self._special_needs_subjects = self._config.special_needs_subjects
        self._fixed_subjects = self._config.fixed_subjects
        self._subject_names = self._config.subject_names
        self._default_teachers = self._config.default_teachers
    
    def _load_from_csv(self):
        """CSVファイルから直接読み込み（旧subject_validator）"""
        logger = logging.getLogger(__name__)
        config_path = Path("data/config")
        
        # 有効な教科を読み込む
        self._valid_subjects = set()
        self._special_needs_subjects = set()
        self._subject_names = {}
        
        valid_subjects_path = config_path / "valid_subjects.csv"
        if valid_subjects_path.exists():
            try:
                with open(valid_subjects_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject = row['教科略号'].strip()
                        self._valid_subjects.add(subject)
                        
                        # 教科名があれば記録
                        if '教科名' in row and row['教科名'].strip():
                            self._subject_names[subject] = row['教科名'].strip()
                        
                        if row['種別'].strip() == '特別支援':
                            self._special_needs_subjects.add(subject)
            except Exception as e:
                logger.error(f"有効教科読み込みエラー: {e}")
        
        # デフォルト値を設定
        if not self._valid_subjects:
            self._valid_subjects = {
                "国", "社", "数", "理", "英", "音", "美", "技", "家", "技家", "保", 
                "道", "総", "YT", "自立", "日生", "生単", "作業", "学活", "行事", "行", "欠", "学", "学総"
            }
            self._special_needs_subjects = {"自立", "日生", "生単", "作業"}
        
        # 固定教科を読み込む
        self._fixed_subjects = set()
        fixed_subjects_path = config_path / "fixed_subjects.csv"
        if fixed_subjects_path.exists():
            try:
                with open(fixed_subjects_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self._fixed_subjects.add(row['固定教科'].strip())
            except Exception as e:
                logger.error(f"固定教科読み込みエラー: {e}")
        
        # デフォルト値を設定
        if not self._fixed_subjects:
            self._fixed_subjects = {"YT", "総", "学活", "欠", "道", "行事", "行", "学", "学総", "テスト", "技家"}
        
        # デフォルト教師を読み込む（オプション）
        self._default_teachers = {}
        teacher_mapping_path = config_path / "default_teacher_mapping.csv"
        if teacher_mapping_path.exists():
            try:
                with open(teacher_mapping_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject = row.get('教科', '').strip()
                        teacher = row.get('デフォルト教員名', '').strip()
                        if subject and teacher:
                            self._default_teachers[subject] = teacher
            except Exception as e:
                logger.warning(f"デフォルト教師マッピング読み込みエラー: {e}")
    
    @property
    def valid_subjects(self) -> Set[str]:
        """有効な教科のセットを返す"""
        if self._config:
            return self._config.valid_subjects.copy()
        else:
            return self._valid_subjects.copy()
    
    @property
    def special_needs_subjects(self) -> Set[str]:
        """特別支援教科のセットを返す"""
        if self._config:
            return self._config.special_needs_subjects.copy()
        else:
            return self._special_needs_subjects.copy()
    
    @property
    def fixed_subjects(self) -> Set[str]:
        """固定教科のセットを返す"""
        if self._config:
            return self._config.fixed_subjects.copy()
        else:
            return self._fixed_subjects.copy()
    
    def is_valid_subject(self, subject: str) -> bool:
        """有効な教科かどうか判定"""
        if subject is None:
            return False
        if self._config:
            return subject in self._config.valid_subjects
        else:
            return subject in self._valid_subjects
    
    def is_special_needs_subject(self, subject: str) -> bool:
        """特別支援教科かどうか判定"""
        if self._config:
            return subject in self._config.special_needs_subjects
        else:
            return subject in self._special_needs_subjects
    
    def is_fixed_subject(self, subject: str) -> bool:
        """固定教科かどうか判定"""
        if self._config:
            return subject in self._config.fixed_subjects
        else:
            return subject in self._fixed_subjects
    
    def get_subject_name(self, subject_code: str) -> str:
        """教科コードから教科名を取得（旧subject_validator_newの機能）"""
        if self._config:
            return self._config.subject_names.get(subject_code, subject_code)
        else:
            return self._subject_names.get(subject_code, subject_code) if self._subject_names else subject_code
    
    def get_default_teacher(self, subject_code: str) -> Optional[str]:
        """教科のデフォルト教員名を取得（旧subject_validator_newの機能）"""
        if self._config:
            return self._config.default_teachers.get(subject_code)
        else:
            return self._default_teachers.get(subject_code) if self._default_teachers else None