"""教員マッピング情報を読み込むリポジトリ"""
import csv
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

from ...domain.value_objects.time_slot import Teacher, Subject, ClassReference
from ...shared.mixins.logging_mixin import LoggingMixin
from ...shared.utils.csv_operations import CSVOperations


class TeacherMappingRepository(LoggingMixin):
    """教員マッピングCSVファイルからデータを読み込むリポジトリ"""
    
    def __init__(self, base_path: Path = Path(".")):
        super().__init__()
        self.base_path = Path(base_path)
        self.permanent_absences = {}  # 恒久的な教師の休み情報
    
    def load_teacher_mapping(self, filename: str = "teacher_subject_mapping.csv") -> Dict[str, List[Tuple[Subject, List[ClassReference]]]]:
        """教員マッピングを読み込む
        
        Returns:
            Dict[教員名, List[Tuple[教科, List[担当クラス]]]]
        """
        file_path = self.base_path / filename
        
        # ファイルが見つからない場合、dataディレクトリも探す
        if not file_path.exists() and "data/" not in str(filename):
            alt_path = self.base_path / "data" / filename
            if alt_path.exists():
                file_path = alt_path
        
        if not file_path.exists():
            self.logger.warning(f"教員マッピングファイルが見つかりません: {file_path}")
            return {}
        
        teacher_mapping = defaultdict(list)
        
        try:
            rows = CSVOperations.read_csv(str(file_path))
            
            for row in rows:
                teacher_name = row['教員名'].strip()
                subject_name = row['教科'].strip()
                grade = int(row['学年'].strip())
                class_num = int(row['組'].strip())
                
                # 教科オブジェクトを作成
                try:
                    subject = Subject(subject_name)
                except ValueError:
                    self.logger.warning(f"無効な教科名をスキップ: {subject_name}")
                    continue
                
                # クラス参照を作成
                class_ref = ClassReference(grade, class_num)
                
                # 同じ教員・教科の組み合わせが既にある場合はクラスを追加
                found = False
                for i, (existing_subject, existing_classes) in enumerate(teacher_mapping[teacher_name]):
                    if existing_subject == subject:
                        if class_ref not in existing_classes:
                            existing_classes.append(class_ref)
                        found = True
                        break
                
                if not found:
                    teacher_mapping[teacher_name].append((subject, [class_ref]))
            
            # 実際の教員マッピングも追加で読み込む
            actual_mapping_path = self.base_path / "actual_teacher_mapping.csv"
            if actual_mapping_path.exists():
                self.logger.info("実際の教員マッピングを追加読み込み")
                actual_rows = CSVOperations.read_csv(str(actual_mapping_path))
                
                for row in actual_rows:
                    teacher_name = row['実際の教員名'].strip()
                    subject_name = row['担当教科'].strip()
                    grade = int(row['担当学年'].strip())
                    class_num = int(row['担当クラス'].strip())
                    remarks = row.get('備考', '').strip()
                    
                    # 備考欄は参考情報として無視する（実際の不在情報はFollow-up.csvから読み取る）
                    # if remarks:
                    #     absences = self._parse_permanent_absences(remarks)
                    #     if absences:
                    #         if teacher_name not in self.permanent_absences:
                    #             self.permanent_absences[teacher_name] = []
                    #         self.permanent_absences[teacher_name].extend(absences)
                    #         self.logger.info(f"恒久的休み情報を検出: {teacher_name} - {absences}")
                    
                    try:
                        subject = Subject(subject_name)
                        class_ref = ClassReference(grade, class_num)
                        
                        # 既存のマッピングを上書き
                        found = False
                        for i, (existing_subject, existing_classes) in enumerate(teacher_mapping[teacher_name]):
                            if existing_subject == subject:
                                if class_ref not in existing_classes:
                                    existing_classes.append(class_ref)
                                found = True
                                break
                        
                        if not found:
                            teacher_mapping[teacher_name].append((subject, [class_ref]))
                            
                    except ValueError:
                        self.logger.warning(f"無効な教科名をスキップ: {subject_name}")
                        continue
                
            self.logger.info(f"教員マッピングを読み込みました: {len(teacher_mapping)}名の教員")
            self.logger.info(f"恒久的休み情報: {len(self.permanent_absences)}名の教員")
            return dict(teacher_mapping)
            
        except Exception as e:
            self.logger.error(f"教員マッピング読み込みエラー: {e}")
            return {}
    
    def _parse_permanent_absences(self, remarks: str) -> List[Tuple[str, str]]:
        """
        備考欄から恒久的な教師の休み情報を解析
        
        Args:
            remarks: 備考欄の文字列（例: "月曜終日不在", "金曜午後不在"）
        
        Returns:
            List of (day, period_type) tuples
        """
        absences = []
        
        if not remarks:
            return absences
        
        # 複数の休みが「・」で区切られている場合に対応
        parts = remarks.split('・')
        
        for part in parts:
            # 曜日を抽出
            day_match = re.search(r'([月火水木金])曜?', part)
            if day_match:
                day = day_match.group(1)
                
                # 時間帯を抽出
                if '終日' in part:
                    absences.append((day, '終日'))
                elif '午後' in part:
                    absences.append((day, '午後'))
        
        return absences
    
    def get_permanent_absences(self) -> Dict[str, List[Tuple[str, str]]]:
        """恒久的な教師の休み情報を取得"""
        return self.permanent_absences
    
    def get_teacher_for_subject_class(self, mapping: Dict, subject: Subject, class_ref: ClassReference) -> Optional[Teacher]:
        """指定された教科・クラスの担当教員を取得"""
        for teacher_name, assignments in mapping.items():
            for assigned_subject, assigned_classes in assignments:
                if assigned_subject == subject and class_ref in assigned_classes:
                    # Teacherオブジェクトを作成（"先生"を含めたまま）
                    return Teacher(teacher_name)
        return None
    
    def get_all_teachers_for_subject_class(self, mapping: Dict, subject: Subject, class_ref: ClassReference) -> List[Teacher]:
        """指定された教科・クラスの全ての担当教員を取得
        
        複数の教師が同じクラス・教科を担当している場合、
        全ての教師を返します。
        """
        teachers = []
        for teacher_name, assignments in mapping.items():
            for assigned_subject, assigned_classes in assignments:
                if assigned_subject == subject and class_ref in assigned_classes:
                    teacher = Teacher(teacher_name)
                    if teacher not in teachers:
                        teachers.append(teacher)
        return teachers
    
    def get_all_teacher_names(self, mapping: Dict) -> Set[str]:
        """全教員名を取得"""
        names = set()
        for teacher_name in mapping.keys():
            names.add(teacher_name)
        return names