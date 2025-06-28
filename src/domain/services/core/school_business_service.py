"""学校ビジネスサービス - 学校に関するビジネスロジック"""
from typing import List, Set, Dict, Tuple
import logging
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.school_data import SchoolData
from ...value_objects.time_slot import ClassReference, Subject, Teacher


class SchoolBusinessService(LoggingMixin):
    """学校に関するビジネスロジックを提供するサービス"""
    
    def __init__(self):
        super().__init__()
    
    def get_classes_by_type(self, school_data: SchoolData, 
                           regular: bool = None,
                           special_needs: bool = None,
                           exchange: bool = None) -> List[ClassReference]:
        """タイプ別にクラスを取得"""
        classes = sorted(list(school_data.classes), 
                        key=lambda c: (c.grade, c.class_number))
        
        if regular is not None:
            classes = [c for c in classes if c.is_regular_class() == regular]
        if special_needs is not None:
            classes = [c for c in classes if c.is_special_needs_class() == special_needs]
        if exchange is not None:
            classes = [c for c in classes if c.is_exchange_class() == exchange]
        
        return classes
    
    def can_teacher_teach_subject(self, school_data: SchoolData,
                                 teacher: Teacher, subject: Subject) -> bool:
        """教員が指定された教科を担当できるかどうか判定"""
        return subject in school_data.teacher_subjects.get(teacher, set())
    
    def get_teacher_class_assignments(self, school_data: SchoolData,
                                    teacher: Teacher) -> List[Tuple[Subject, ClassReference]]:
        """教員の担当クラス・教科一覧を取得"""
        assignments = []
        for (subject, class_ref), assigned_teacher in school_data.teacher_assignments.items():
            if assigned_teacher == teacher:
                assignments.append((subject, class_ref))
        return assignments
    
    def get_required_subjects(self, school_data: SchoolData,
                            class_ref: ClassReference) -> List[Subject]:
        """指定されたクラスで必要な教科一覧を取得"""
        subjects = []
        for (c, subject), hours in school_data.standard_hours.items():
            if c == class_ref and hours > 0:
                subjects.append(subject)
        return subjects
    
    def get_standard_hours_with_compatibility(self, school_data: SchoolData,
                                            class_ref: ClassReference,
                                            subject: Subject) -> float:
        """標準時数を取得（互換性処理付き）"""
        # 学総は総合と同じ標準時数として扱う
        if subject.name == "学総":
            sougou_subject = Subject("総")
            return school_data.get_standard_hours(class_ref, sougou_subject)
        return school_data.get_standard_hours(class_ref, subject)
    
    def get_available_teachers(self, school_data: SchoolData,
                             day: str, period: int) -> Set[Teacher]:
        """指定された時間に利用可能な教員一覧を取得"""
        unavailable = school_data.get_unavailable_teachers(day, period)
        return school_data.teachers - unavailable
    
    def validate_setup(self, school_data: SchoolData) -> List[str]:
        """学校設定の妥当性を検証"""
        errors = []
        
        # 全てのクラス・教科に担当教員が割り当てられているかチェック
        for class_ref in school_data.classes:
            required_subjects = self.get_required_subjects(school_data, class_ref)
            for subject in required_subjects:
                teacher = school_data.get_teacher_assignment(subject, class_ref)
                if not teacher:
                    errors.append(
                        f"担当教員未割当: {class_ref} {subject}"
                    )
        
        # 教員の担当可能教科と実際の割り当てに矛盾がないかチェック
        for (subject, class_ref), teacher in school_data.teacher_assignments.items():
            if not self.can_teacher_teach_subject(school_data, teacher, subject):
                errors.append(
                    f"教科担当不可: {teacher.name}先生は{subject}を担当できませんが、"
                    f"{class_ref}に割り当てられています"
                )
        
        # 標準時数の妥当性チェック
        for (class_ref, subject), hours in school_data.standard_hours.items():
            if hours < 0:
                errors.append(
                    f"無効な標準時数: {class_ref} {subject} = {hours}時間"
                )
            elif hours > 30:  # 週30時間を超える教科は異常
                errors.append(
                    f"異常な標準時数: {class_ref} {subject} = {hours}時間"
                )
        
        return errors
    
    def get_teacher_workload_summary(self, school_data: SchoolData) -> Dict[Teacher, Dict[str, int]]:
        """教員の担当負荷サマリーを取得"""
        summary = {}
        
        for teacher in school_data.teachers:
            assignments = self.get_teacher_class_assignments(school_data, teacher)
            
            # 担当クラス数と教科数を集計
            classes = set()
            subjects = set()
            for subject, class_ref in assignments:
                classes.add(class_ref)
                subjects.add(subject)
            
            summary[teacher] = {
                'total_assignments': len(assignments),
                'class_count': len(classes),
                'subject_count': len(subjects),
                'subjects': list(subjects)
            }
        
        return summary
    
    def find_teachers_for_subject_and_class(self, school_data: SchoolData,
                                          subject: Subject,
                                          class_ref: ClassReference) -> List[Teacher]:
        """指定した教科とクラスを担当可能な教員を探す"""
        # まず割り当て済みの教員を確認
        assigned = school_data.get_teacher_assignment(subject, class_ref)
        if assigned:
            return [assigned]
        
        # 次に、その教科を担当可能な教員を探す
        candidates = []
        for teacher in school_data.subject_teachers.get(subject, set()):
            if self.can_teacher_teach_subject(school_data, teacher, subject):
                candidates.append(teacher)
        
        return candidates