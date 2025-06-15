"""設定ファイルを読み込むリポジトリ"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

from ...domain.value_objects.time_slot import Teacher, Subject, ClassReference, TimeSlot


class ConfigRepository:
    """configフォルダから各種設定を読み込むリポジトリ"""
    
    def __init__(self, config_path: Path = Path("data/config")):
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)
    
    def load_fixed_subjects(self) -> Set[str]:
        """固定教科のリストを読み込む"""
        file_path = self.config_path / "fixed_subjects.csv"
        fixed_subjects = set()
        
        if not file_path.exists():
            self.logger.warning(f"固定教科ファイルが見つかりません: {file_path}")
            return fixed_subjects
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fixed_subjects.add(row['固定教科'].strip())
                    
            self.logger.info(f"固定教科を読み込みました: {len(fixed_subjects)}件")
            return fixed_subjects
            
        except Exception as e:
            self.logger.error(f"固定教科読み込みエラー: {e}")
            return set()
    
    def load_valid_subjects(self) -> Set[str]:
        """有効な教科のリストを読み込む"""
        file_path = self.config_path / "valid_subjects.csv"
        valid_subjects = set()
        
        if not file_path.exists():
            self.logger.warning(f"有効教科ファイルが見つかりません: {file_path}")
            return valid_subjects
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    valid_subjects.add(row['教科略号'].strip())
                    
            self.logger.info(f"有効教科を読み込みました: {len(valid_subjects)}件")
            return valid_subjects
            
        except Exception as e:
            self.logger.error(f"有効教科読み込みエラー: {e}")
            return set()
    
    def load_special_needs_subjects(self) -> Set[str]:
        """特別支援教科のリストを読み込む"""
        file_path = self.config_path / "valid_subjects.csv"
        special_needs_subjects = set()
        
        if not file_path.exists():
            self.logger.warning(f"有効教科ファイルが見つかりません: {file_path}")
            return special_needs_subjects
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['種別'].strip() == '特別支援':
                        special_needs_subjects.add(row['教科略号'].strip())
                        
            self.logger.info(f"特別支援教科を読み込みました: {len(special_needs_subjects)}件")
            return special_needs_subjects
            
        except Exception as e:
            self.logger.error(f"特別支援教科読み込みエラー: {e}")
            return set()
    
    def load_exchange_class_mapping(self) -> Dict[ClassReference, Tuple[ClassReference, Set[str]]]:
        """交流学級のマッピングを読み込む"""
        file_path = self.config_path / "exchange_class_mapping.csv"
        mapping = {}
        
        if not file_path.exists():
            self.logger.warning(f"交流学級マッピングファイルが見つかりません: {file_path}")
            return mapping
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 交流学級
                    exchange_class = row['交流学級'].strip()
                    grade = int(exchange_class[0])
                    class_num = int(exchange_class[2])
                    exchange_ref = ClassReference(grade, class_num)
                    
                    # 親学級
                    parent_class = row['親学級'].strip()
                    parent_grade = int(parent_class[0])
                    parent_num = int(parent_class[2])
                    parent_ref = ClassReference(parent_grade, parent_num)
                    
                    # 自立時の親学級配置教科
                    subjects = set()
                    if '数または英' in row['親学級配置教科（自立時）']:
                        subjects = {'数', '英'}
                    
                    mapping[exchange_ref] = (parent_ref, subjects)
                    
            self.logger.info(f"交流学級マッピングを読み込みました: {len(mapping)}件")
            return mapping
            
        except Exception as e:
            self.logger.error(f"交流学級マッピング読み込みエラー: {e}")
            return {}
    
    def load_meeting_info(self) -> Dict[Tuple[str, int], Tuple[str, List[str]]]:
        """会議情報を読み込む（時間情報とメンバー情報を結合）"""
        meetings = {}
        
        # 1. まず会議時間を読み込む
        times_file = self.config_path / "default_meeting_times.csv"
        meeting_times = {}  # 会議名 -> (曜日, 校時)
        
        if not times_file.exists():
            self.logger.warning(f"会議時間ファイルが見つかりません: {times_file}")
            return meetings
        
        try:
            with open(times_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    meeting_name = row['会議名'].strip()
                    day = row['曜日'].strip()
                    period = int(row['校時'].strip())
                    meeting_times[meeting_name] = (day, period)
            
            self.logger.info(f"会議時間を読み込みました: {len(meeting_times)}件")
            
        except Exception as e:
            self.logger.error(f"会議時間読み込みエラー: {e}")
            return {}
        
        # 2. 次に会議メンバーを読み込む
        members_file = self.config_path / "meeting_members.csv"
        
        if not members_file.exists():
            self.logger.warning(f"会議メンバーファイルが見つかりません: {members_file}")
            # 時間情報だけで会議を作成（全教員参加として）
            for meeting_name, (day, period) in meeting_times.items():
                meetings[(day, period)] = (meeting_name, [])
            return meetings
        
        try:
            with open(members_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    meeting_name = row['会議名'].strip()
                    if meeting_name in meeting_times:
                        day, period = meeting_times[meeting_name]
                        # メンバーをカンマ区切りで分割（・区切りではなく）
                        members_str = row['参加教員'].strip()
                        if members_str:
                            members = [m.strip() for m in members_str.split(',')]
                        else:
                            members = []
                        
                        meetings[(day, period)] = (meeting_name, members)
            
            # メンバー情報がない会議も追加（全教員参加）
            for meeting_name, (day, period) in meeting_times.items():
                if (day, period) not in meetings:
                    meetings[(day, period)] = (meeting_name, [])
                    
            self.logger.info(f"会議情報を読み込みました: {len(meetings)}件")
            return meetings
            
        except Exception as e:
            self.logger.error(f"会議メンバー読み込みエラー: {e}")
            # エラー時は時間情報だけで返す
            for meeting_name, (day, period) in meeting_times.items():
                meetings[(day, period)] = (meeting_name, [])
            return meetings
    
    def load_grade5_classes(self) -> List[ClassReference]:
        """5組のクラスリストを読み込む"""
        file_path = self.config_path / "class_definitions.csv"
        grade5_classes = []
        
        if not file_path.exists():
            self.logger.warning(f"クラス定義ファイルが見つかりません: {file_path}")
            # デフォルト値を返す
            return [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['組'].strip() == '5' and row['クラス種別'].strip() == '特別支援学級':
                        grade = int(row['学年'].strip())
                        class_num = int(row['組'].strip())
                        grade5_classes.append(ClassReference(grade, class_num))
                        
            self.logger.info(f"5組クラスを読み込みました: {len(grade5_classes)}クラス")
            return grade5_classes
            
        except Exception as e:
            self.logger.error(f"5組クラス読み込みエラー: {e}")
            # デフォルト値を返す
            return [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
    
    def load_time_constraints(self) -> List[Dict]:
        """時間制約を読み込む"""
        file_path = self.config_path / "time_constraints.csv"
        constraints = []
        
        if not file_path.exists():
            self.logger.warning(f"時間制約ファイルが見つかりません: {file_path}")
            return constraints
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    constraint = {
                        '制約名': row['制約名'].strip(),
                        '曜日': row['曜日'].strip(),
                        '校時': int(row['校時'].strip()),
                        '対象': row['対象'].strip(),
                        '内容': row['内容'].strip(),
                        '優先度': row['優先度'].strip()
                    }
                    constraints.append(constraint)
                    
            self.logger.info(f"時間制約を読み込みました: {len(constraints)}件")
            return constraints
            
        except Exception as e:
            self.logger.error(f"時間制約読み込みエラー: {e}")
            return []
    
    def load_default_teacher_mapping(self) -> Dict[str, str]:
        """デフォルト教員マッピングを読み込む"""
        file_path = self.config_path / "default_teacher_mapping.csv"
        mapping = {}
        
        if not file_path.exists():
            self.logger.warning(f"デフォルト教員マッピングファイルが見つかりません: {file_path}")
            return mapping
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    subject = row['教科'].strip()
                    teacher = row['デフォルト教員名'].strip()
                    mapping[subject] = teacher
                    
            self.logger.info(f"デフォルト教員マッピングを読み込みました: {len(mapping)}件")
            return mapping
            
        except Exception as e:
            self.logger.error(f"デフォルト教員マッピング読み込みエラー: {e}")
            return {}
    
    def load_valid_class_numbers(self) -> Dict[str, Set[int]]:
        """有効なクラス番号を読み込む"""
        file_path = self.config_path / "system_constants.csv"
        class_numbers = {
            '通常学級': set(),
            '特別支援学級': set(),
            '交流学級': set()
        }
        
        if not file_path.exists():
            self.logger.warning(f"システム定数ファイルが見つかりません: {file_path}")
            # デフォルト値を返す
            return {
                '通常学級': {1, 2, 3},
                '特別支援学級': {5},
                '交流学級': {6, 7}
            }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['設定名'].strip() == '通常学級番号':
                        class_numbers['通常学級'] = {int(n.strip()) for n in row['値'].split('・')}
                    elif row['設定名'].strip() == '特別支援学級番号':
                        class_numbers['特別支援学級'] = {int(row['値'].strip())}
                    elif row['設定名'].strip() == '交流学級番号':
                        class_numbers['交流学級'] = {int(n.strip()) for n in row['値'].split('・')}
                        
            self.logger.info(f"有効なクラス番号を読み込みました")
            return class_numbers
            
        except Exception as e:
            self.logger.error(f"クラス番号読み込みエラー: {e}")
            # デフォルト値を返す
            return {
                '通常学級': {1, 2, 3},
                '特別支援学級': {5},
                '交流学級': {6, 7}
            }