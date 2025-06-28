"""リファクタリング版学校エンティティ - ファサードパターンを適用"""
from typing import Dict, List, Set, Optional

from .school_data import SchoolData
from ..services.school_business_service import SchoolBusinessService
from ..value_objects.time_slot import ClassReference, Subject, Teacher
from ..value_objects.assignment import StandardHours
from ...shared.mixins.validation_mixin import ValidationMixin, ValidationError


class School(ValidationMixin):
    """学校全体の情報を管理するエンティティ（ファサード）
    
    既存のインターフェースを維持しながら、内部的にはSchoolDataと
    SchoolBusinessServiceを使用してデータとロジックを分離
    """
    
    def __init__(self):
        # データ保持
        self._data = SchoolData()
        
        # ビジネスロジック
        self._business_service = SchoolBusinessService()
    
    # クラス管理
    def add_class(self, class_ref: ClassReference) -> None:
        """クラスを追加"""
        self._data.add_class(class_ref)
    
    def get_all_classes(self) -> List[ClassReference]:
        """全てのクラスを取得"""
        return sorted(list(self._data.classes), 
                     key=lambda c: (c.grade, c.class_number))
    
    def get_classes_by_type(self, regular: bool = None, special_needs: bool = None, 
                           exchange: bool = None) -> List[ClassReference]:
        """タイプ別にクラスを取得"""
        return self._business_service.get_classes_by_type(
            self._data, regular, special_needs, exchange
        )
    
    # 教員管理
    def add_teacher(self, teacher: Teacher) -> None:
        """教員を追加"""
        self._data.add_teacher(teacher)
    
    def get_all_teachers(self) -> List[Teacher]:
        """全ての教員を取得"""
        return sorted(list(self._data.teachers), key=lambda t: t.name)
    
    def assign_teacher_subject(self, teacher: Teacher, subject: Subject) -> None:
        """教員の担当教科を設定"""
        self._data.add_teacher_subject(teacher, subject)
    
    def get_teacher_subjects(self, teacher: Teacher) -> Set[Subject]:
        """教員の担当教科を取得"""
        return self._data.teacher_subjects.get(teacher, set()).copy()
    
    def get_subject_teachers(self, subject: Subject) -> Set[Teacher]:
        """教科の担当教員を取得"""
        return self._data.subject_teachers.get(subject, set()).copy()
    
    def can_teacher_teach_subject(self, teacher: Teacher, subject: Subject) -> bool:
        """教員が指定された教科を担当できるかどうか判定"""
        return self._business_service.can_teacher_teach_subject(
            self._data, teacher, subject
        )
    
    # 教員-クラス割り当て管理
    def assign_teacher_to_class(self, teacher: Teacher, subject: Subject, 
                               class_ref: ClassReference) -> None:
        """教員を特定のクラス・教科に割り当て"""
        if not self.can_teacher_teach_subject(teacher, subject):
            raise ValidationError(f"{teacher} cannot teach {subject}")
        
        self._data.set_teacher_assignment(subject, class_ref, teacher)
    
    def get_assigned_teacher(self, subject: Subject, class_ref: ClassReference) -> Teacher:
        """指定されたクラス・教科の担当教員を取得"""
        return self._data.get_teacher_assignment(subject, class_ref)
    
    def get_teacher_class_assignments(self, teacher: Teacher) -> List[tuple[Subject, ClassReference]]:
        """教員の担当クラス・教科一覧を取得"""
        return self._business_service.get_teacher_class_assignments(
            self._data, teacher
        )
    
    # 標準時数管理
    def set_standard_hours(self, class_ref: ClassReference, subject: Subject, hours: float) -> None:
        """標準時数を設定"""
        self._data.set_standard_hours(class_ref, subject, hours)
    
    def get_standard_hours(self, class_ref: ClassReference, subject: Subject) -> float:
        """標準時数を取得"""
        return self._business_service.get_standard_hours_with_compatibility(
            self._data, class_ref, subject
        )
    
    def get_all_standard_hours(self, class_ref: ClassReference) -> Dict[Subject, float]:
        """指定されたクラスの全ての標準時数を取得"""
        result = {}
        for (c, subject), hours in self._data.standard_hours.items():
            if c == class_ref and hours > 0:
                result[subject] = hours
        return result
    
    def get_required_subjects(self, class_ref: ClassReference) -> List[Subject]:
        """指定されたクラスで必要な教科一覧を取得"""
        return self._business_service.get_required_subjects(
            self._data, class_ref
        )
    
    # 教員の利用不可時間管理
    def set_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> None:
        """教員の利用不可時間を設定"""
        self._data.set_teacher_unavailable(day, period, teacher)
    
    def is_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> bool:
        """教員が指定された時間に利用不可かどうか判定"""
        return self._data.is_teacher_unavailable(day, period, teacher)
    
    def get_unavailable_teachers(self, day: str, period: int) -> Set[Teacher]:
        """指定された時間に利用不可の教員一覧を取得"""
        return self._data.get_unavailable_teachers(day, period)
    
    def get_available_teachers(self, day: str, period: int) -> Set[Teacher]:
        """指定された時間に利用可能な教員一覧を取得"""
        return self._business_service.get_available_teachers(
            self._data, day, period
        )
    
    # バリデーション
    def validate_setup(self) -> List[str]:
        """学校設定の妥当性を検証"""
        return self._business_service.validate_setup(self._data)
    
    # 追加のビジネスメソッド（オプション）
    def get_teacher_workload_summary(self) -> Dict[Teacher, Dict[str, int]]:
        """教員の担当負荷サマリーを取得"""
        return self._business_service.get_teacher_workload_summary(self._data)
    
    def get_teachers_for_subject(self, subject: Subject) -> List[Teacher]:
        """教科を担当できる教員一覧を取得"""
        return sorted(list(self.get_subject_teachers(subject)), 
                     key=lambda t: t.name)
    
    def get_all_subjects(self) -> List[Subject]:
        """全ての教科を取得"""
        subjects = set()
        # 標準時数から教科を収集
        for (_, subject), _ in self._data.standard_hours.items():
            subjects.add(subject)
        # 教員の担当教科からも収集
        for _, subject_set in self._data.teacher_subjects.items():
            subjects.update(subject_set)
        return sorted(list(subjects), key=lambda s: s.name)
    
    def find_substitute_teacher(self, subject: Subject, class_ref: ClassReference,
                              excluded_teachers: List[Teacher] = None) -> Optional[Teacher]:
        """代替教員を探す"""
        candidates = self._business_service.find_teachers_for_subject_and_class(
            self._data, subject, class_ref
        )
        
        if excluded_teachers:
            candidates = [t for t in candidates if t not in excluded_teachers]
        
        return candidates[0] if candidates else None
    
    def clone(self) -> 'School':
        """学校データの複製を作成"""
        new_school = School()
        new_school._data = self._data.clone()
        return new_school
    
    def __str__(self) -> str:
        return f"School(classes={len(self._data.classes)}, teachers={len(self._data.teachers)})"