"""学校データ - 純粋なデータ保持クラス"""
from typing import Dict, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from ..value_objects.time_slot import ClassReference, Subject, Teacher


@dataclass
class SchoolData:
    """学校の純粋なデータを保持するクラス
    
    ビジネスロジックを含まず、データの保存・取得のみを行う
    """
    # クラス一覧
    classes: Set[ClassReference] = field(default_factory=set)
    
    # 教員一覧
    teachers: Set[Teacher] = field(default_factory=set)
    
    # 教員の担当教科: Teacher -> Set[Subject]
    teacher_subjects: Dict[Teacher, Set[Subject]] = field(
        default_factory=lambda: defaultdict(set)
    )
    
    # 教科の担当教員: Subject -> Set[Teacher]
    subject_teachers: Dict[Subject, Set[Teacher]] = field(
        default_factory=lambda: defaultdict(set)
    )
    
    # 教員のクラス割り当て: (Subject, ClassReference) -> Teacher
    teacher_assignments: Dict[Tuple[Subject, ClassReference], Teacher] = field(
        default_factory=dict
    )
    
    # 標準時数: (ClassReference, Subject) -> float
    standard_hours: Dict[Tuple[ClassReference, Subject], float] = field(
        default_factory=dict
    )
    
    # 教員の利用不可時間: (day, period) -> Set[Teacher]
    teacher_unavailable: Dict[Tuple[str, int], Set[Teacher]] = field(
        default_factory=lambda: defaultdict(set)
    )
    
    # 基本的なデータ操作メソッド
    def add_class(self, class_ref: ClassReference) -> None:
        """クラスを追加"""
        self.classes.add(class_ref)
    
    def add_teacher(self, teacher: Teacher) -> None:
        """教員を追加"""
        self.teachers.add(teacher)
    
    def add_teacher_subject(self, teacher: Teacher, subject: Subject) -> None:
        """教員の担当教科を追加"""
        self.teachers.add(teacher)
        self.teacher_subjects[teacher].add(subject)
        self.subject_teachers[subject].add(teacher)
    
    def set_teacher_assignment(self, subject: Subject, class_ref: ClassReference, 
                              teacher: Teacher) -> None:
        """教員のクラス割り当てを設定"""
        self.teacher_assignments[(subject, class_ref)] = teacher
    
    def get_teacher_assignment(self, subject: Subject, 
                              class_ref: ClassReference) -> Optional[Teacher]:
        """教員のクラス割り当てを取得"""
        return self.teacher_assignments.get((subject, class_ref))
    
    def set_standard_hours(self, class_ref: ClassReference, subject: Subject, 
                          hours: float) -> None:
        """標準時数を設定"""
        self.standard_hours[(class_ref, subject)] = hours
    
    def get_standard_hours(self, class_ref: ClassReference, 
                          subject: Subject) -> float:
        """標準時数を取得"""
        return self.standard_hours.get((class_ref, subject), 0.0)
    
    def set_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> None:
        """教員の利用不可時間を設定"""
        self.teacher_unavailable[(day, period)].add(teacher)
    
    def is_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> bool:
        """教員が利用不可かどうか"""
        return teacher in self.teacher_unavailable[(day, period)]
    
    def get_unavailable_teachers(self, day: str, period: int) -> Set[Teacher]:
        """指定時間の利用不可教員を取得"""
        return self.teacher_unavailable[(day, period)].copy()
    
    def clone(self) -> 'SchoolData':
        """データの複製を作成"""
        new_data = SchoolData()
        
        # 深いコピー
        new_data.classes = self.classes.copy()
        new_data.teachers = self.teachers.copy()
        
        for teacher, subjects in self.teacher_subjects.items():
            new_data.teacher_subjects[teacher] = subjects.copy()
        
        for subject, teachers in self.subject_teachers.items():
            new_data.subject_teachers[subject] = teachers.copy()
        
        new_data.teacher_assignments = self.teacher_assignments.copy()
        new_data.standard_hours = self.standard_hours.copy()
        
        for key, teachers in self.teacher_unavailable.items():
            new_data.teacher_unavailable[key] = teachers.copy()
        
        return new_data