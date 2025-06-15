"""設定ファイルを読み込んでドメインオブジェクトを初期化"""
import csv
import logging
from pathlib import Path
from typing import Dict, Set

from ...domain.value_objects.subject_config import SubjectConfig, ClassConfig
from ...domain.value_objects.subject_validator import SubjectValidator
from ...domain.value_objects.class_validator import ClassValidator


class ConfigLoader:
    """設定ファイルを読み込むクラス"""
    
    def __init__(self, config_path: Path = Path("data/config")):
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)
    
    def load_subject_config(self) -> SubjectConfig:
        """教科設定を読み込む"""
        config = SubjectConfig()
        
        # subject_master.csvから読み込み
        subject_master_path = self.config_path / "subject_master.csv"
        if subject_master_path.exists():
            try:
                with open(subject_master_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject_code = row['教科略号'].strip()
                        config.valid_subjects.add(subject_code)
                        
                        # 教科名
                        config.subject_names[subject_code] = row['教科名'].strip()
                        
                        # 種別による分類
                        if row['種別'].strip() == '特別支援':
                            config.special_needs_subjects.add(subject_code)
                        
                        # 固定教科
                        if row['固定フラグ'].strip() == '可':
                            config.fixed_subjects.add(subject_code)
                        
                        # デフォルト教員
                        default_teacher = row['デフォルト教員名'].strip()
                        if default_teacher and default_teacher != 'なし':
                            config.default_teachers[subject_code] = default_teacher
                        
                        # 体育館使用
                        if row['体育館使用'].strip() == '可':
                            config.gym_subjects.add(subject_code)
                            
                self.logger.info(f"教科設定を読み込みました: {len(config.valid_subjects)}教科")
            except Exception as e:
                self.logger.error(f"教科設定読み込みエラー: {e}")
        else:
            # 旧形式のファイルから読み込み（後方互換性）
            self._load_legacy_subject_config(config)
        
        return config
    
    def _load_legacy_subject_config(self, config: SubjectConfig):
        """旧形式の設定ファイルから読み込み（後方互換性）"""
        # valid_subjects.csv
        valid_subjects_path = self.config_path / "valid_subjects.csv"
        if valid_subjects_path.exists():
            try:
                with open(valid_subjects_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject = row['教科略号'].strip()
                        config.valid_subjects.add(subject)
                        if row['種別'].strip() == '特別支援':
                            config.special_needs_subjects.add(subject)
            except Exception as e:
                self.logger.error(f"有効教科読み込みエラー: {e}")
        
        # fixed_subjects.csv
        fixed_subjects_path = self.config_path / "fixed_subjects.csv"
        if fixed_subjects_path.exists():
            try:
                with open(fixed_subjects_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        config.fixed_subjects.add(row['固定教科'].strip())
            except Exception as e:
                self.logger.error(f"固定教科読み込みエラー: {e}")
        
        # デフォルト値を設定
        if not config.valid_subjects:
            config.valid_subjects = {
                "国", "社", "数", "理", "英", "音", "美", "技", "家", "保", 
                "道", "総", "YT", "自立", "日生", "生単", "作業", "学活", "行事", "行", "欠", "学"
            }
            config.special_needs_subjects = {"自立", "日生", "生単", "作業"}
            config.fixed_subjects = {"YT", "総", "学活", "欠", "道", "行事", "行", "学"}
    
    def _load_grade5_team_teaching(self, config: ClassConfig):
        """5組のチームティーチング設定を読み込む"""
        grade5_tt_path = self.config_path / "grade5_team_teaching.csv"
        if grade5_tt_path.exists():
            try:
                config.grade5_team_teaching_teachers = set()
                with open(grade5_tt_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        teacher_name = row['教師名'].strip()
                        if teacher_name != 'その他':
                            config.grade5_team_teaching_teachers.add(teacher_name)
                self.logger.info(f"5組チームティーチング教師を読み込みました: {config.grade5_team_teaching_teachers}")
            except Exception as e:
                self.logger.error(f"5組チームティーチング設定読み込みエラー: {e}")
        else:
            # デフォルト値
            config.grade5_team_teaching_teachers = {"金子み", "寺田", "梶永"}
    
    def load_class_config(self) -> ClassConfig:
        """クラス設定を読み込む"""
        config = ClassConfig()
        
        # system_constants.csvから読み込み
        system_constants_path = self.config_path / "system_constants.csv"
        if system_constants_path.exists():
            try:
                with open(system_constants_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['設定名'].strip() == '通常学級番号':
                            config.regular_class_numbers = {int(n.strip()) for n in row['値'].split('・')}
                        elif row['設定名'].strip() == '特別支援学級番号':
                            config.special_needs_class_numbers = {int(row['値'].strip())}
                        elif row['設定名'].strip() == '交流学級番号':
                            config.exchange_class_numbers = {int(n.strip()) for n in row['値'].split('・')}
            except Exception as e:
                self.logger.error(f"クラス番号読み込みエラー: {e}")
        
        # exchange_class_mapping.csvから読み込み
        exchange_mapping_path = self.config_path / "exchange_class_mapping.csv"
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
                        
                        config.exchange_class_mappings[(eg, ec)] = ((pg, pc), subjects)
            except Exception as e:
                self.logger.error(f"交流学級マッピング読み込みエラー: {e}")
        
        # デフォルト値を設定
        if not config.regular_class_numbers:
            config.regular_class_numbers = {1, 2, 3}
            config.special_needs_class_numbers = {5}
            config.exchange_class_numbers = {6, 7}
            config.exchange_class_mappings = {
                (1, 6): ((1, 1), {'数', '英'}),
                (1, 7): ((1, 2), {'数', '英'}),
                (2, 6): ((2, 3), {'数', '英'}),
                (2, 7): ((2, 2), {'数', '英'}),
                (3, 6): ((3, 3), {'数', '英'}),
                (3, 7): ((3, 2), {'数', '英'}),
            }
        
        # 5組のチームティーチング教師を読み込み
        self._load_grade5_team_teaching(config)
        
        return config
    
    def initialize_validators(self):
        """バリデータを初期化"""
        subject_config = self.load_subject_config()
        class_config = self.load_class_config()
        
        SubjectValidator.initialize(subject_config)
        ClassValidator.initialize(class_config)
        
        # Team-teaching service initialization removed - functionality integrated into policies
        # Team teaching for Grade 5 is now handled directly in constraints
        
        self.logger.info("バリデータを初期化しました")
        self.logger.info(f"Grade5チームティーチング教師: {class_config.grade5_team_teaching_teachers}")