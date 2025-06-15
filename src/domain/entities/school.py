"""学校エンティティ"""
from typing import Dict, List, Set
from collections import defaultdict

from ..value_objects.time_slot import ClassReference, Subject, Teacher
from ..value_objects.assignment import StandardHours


class School:
    """学校全体の情報を管理するエンティティ"""
    
    def __init__(self):
        self._classes: Set[ClassReference] = set()
        self._teachers: Set[Teacher] = set()
        self._teacher_subjects: Dict[Teacher, Set[Subject]] = defaultdict(set)
        self._subject_teachers: Dict[Subject, Set[Teacher]] = defaultdict(set)
        self._teacher_assignments: Dict[tuple[Subject, ClassReference], Teacher] = {}
        self._standard_hours: Dict[tuple[ClassReference, Subject], float] = {}
        self._teacher_unavailable: Dict[tuple[str, int], Set[Teacher]] = defaultdict(set)
    
    # クラス管理
    def add_class(self, class_ref: ClassReference) -> None:
        """クラスを追加"""
        self._classes.add(class_ref)
    
    def get_all_classes(self) -> List[ClassReference]:
        """全てのクラスを取得"""
        return sorted(list(self._classes), key=lambda c: (c.grade, c.class_number))
    
    def get_classes_by_type(self, regular: bool = None, special_needs: bool = None, 
                           exchange: bool = None) -> List[ClassReference]:
        """タイプ別にクラスを取得"""
        classes = self.get_all_classes()
        
        if regular is not None:
            classes = [c for c in classes if c.is_regular_class() == regular]
        if special_needs is not None:
            classes = [c for c in classes if c.is_special_needs_class() == special_needs]
        if exchange is not None:
            classes = [c for c in classes if c.is_exchange_class() == exchange]
        
        return classes
    
    # 教員管理
    def add_teacher(self, teacher: Teacher) -> None:
        """教員を追加"""
        self._teachers.add(teacher)
    
    def get_all_teachers(self) -> List[Teacher]:
        """全ての教員を取得"""
        return sorted(list(self._teachers), key=lambda t: t.name)
    
    def assign_teacher_subject(self, teacher: Teacher, subject: Subject) -> None:
        """教員の担当教科を設定"""
        self.add_teacher(teacher)
        self._teacher_subjects[teacher].add(subject)
        self._subject_teachers[subject].add(teacher)
    
    def get_teacher_subjects(self, teacher: Teacher) -> Set[Subject]:
        """教員の担当教科を取得"""
        return self._teacher_subjects[teacher].copy()
    
    def get_subject_teachers(self, subject: Subject) -> Set[Teacher]:
        """教科の担当教員を取得"""
        return self._subject_teachers[subject].copy()
    
    def can_teacher_teach_subject(self, teacher: Teacher, subject: Subject) -> bool:
        """教員が指定された教科を担当できるかどうか判定"""
        return subject in self._teacher_subjects[teacher]
    
    # 教員-クラス割り当て管理
    def assign_teacher_to_class(self, teacher: Teacher, subject: Subject, class_ref: ClassReference) -> None:
        """教員を特定のクラス・教科に割り当て"""
        if not self.can_teacher_teach_subject(teacher, subject):
            raise ValueError(f"{teacher} cannot teach {subject}")
        
        self._teacher_assignments[(subject, class_ref)] = teacher
    
    def get_assigned_teacher(self, subject: Subject, class_ref: ClassReference) -> Teacher:
        """指定されたクラス・教科の担当教員を取得"""
        return self._teacher_assignments.get((subject, class_ref))
    
    def get_teacher_class_assignments(self, teacher: Teacher) -> List[tuple[Subject, ClassReference]]:
        """教員の担当クラス・教科一覧を取得"""
        return [(subject, class_ref) for (subject, class_ref), t in self._teacher_assignments.items() 
                if t == teacher]
    
    # 標準時数管理
    def set_standard_hours(self, class_ref: ClassReference, subject: Subject, hours: float) -> None:
        """標準時数を設定"""
        self._standard_hours[(class_ref, subject)] = hours
    
    def get_standard_hours(self, class_ref: ClassReference, subject: Subject) -> float:
        """標準時数を取得"""
        # 学総は総合と同じ標準時数として扱う
        if subject.name == "学総":
            sougou_subject = Subject("総")
            return self._standard_hours.get((class_ref, sougou_subject), 0.0)
        return self._standard_hours.get((class_ref, subject), 0.0)
    
    def get_all_standard_hours(self, class_ref: ClassReference) -> Dict[Subject, float]:
        """指定されたクラスの全ての標準時数を取得"""
        result = {}
        for (c, subject), hours in self._standard_hours.items():
            if c == class_ref and hours > 0:
                result[subject] = hours
        return result
    
    def get_required_subjects(self, class_ref: ClassReference) -> List[Subject]:
        """指定されたクラスで必要な教科一覧を取得"""
        return [subject for subject, hours in self.get_all_standard_hours(class_ref).items() 
                if hours > 0]
    
    # 教員の利用不可時間管理
    def set_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> None:
        """教員の利用不可時間を設定"""
        self._teacher_unavailable[(day, period)].add(teacher)
    
    def is_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> bool:
        """教員が指定された時間に利用不可かどうか判定"""
        return teacher in self._teacher_unavailable[(day, period)]
    
    def get_unavailable_teachers(self, day: str, period: int) -> Set[Teacher]:
        """指定された時間に利用不可の教員一覧を取得"""
        return self._teacher_unavailable[(day, period)].copy()
    
    def get_available_teachers(self, day: str, period: int) -> Set[Teacher]:
        """指定された時間に利用可能な教員一覧を取得"""
        unavailable = self.get_unavailable_teachers(day, period)
        return self._teachers - unavailable
    
    # バリデーション
    def validate_setup(self) -> List[str]:
        """学校設定の妥当性を検証"""
        errors = []
        
        # 全てのクラス・教科に担当教員が割り当てられているかチェック
        for class_ref in self._classes:
            required_subjects = self.get_required_subjects(class_ref)
            for subject in required_subjects:
                if not self.get_assigned_teacher(subject, class_ref):
                    errors.append(f"No teacher assigned for {class_ref} {subject}")
        
        # 教員の担当可能教科と実際の割り当てに矛盾がないかチェック
        for (subject, class_ref), teacher in self._teacher_assignments.items():
            if not self.can_teacher_teach_subject(teacher, subject):
                errors.append(f"Teacher {teacher} cannot teach {subject} but assigned to {class_ref}")
        
        return errors
    
    def __str__(self) -> str:
        return f"School(classes={len(self._classes)}, teachers={len(self._teachers)})"