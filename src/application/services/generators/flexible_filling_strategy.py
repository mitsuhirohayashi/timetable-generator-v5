"""柔軟な空きスロット埋め戦略

人間の時間割作成者のような柔軟性を実現する戦略。
教師不在時の代替案、時数の借用、緊急対応などを含む。
"""

from typing import List, Tuple, Dict, Optional, Set
from collections import defaultdict
import logging

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Subject, Teacher
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment
from ....domain.interfaces.fill_strategy import FillStrategy


class FlexibleFillingStrategy(FillStrategy):
    """人間的な柔軟性を持つ埋め戦略"""
    
    def __init__(self):
        self.name = "柔軟埋め戦略"
        self.logger = logging.getLogger(__name__)
    
    def get_placeable_subjects(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> List[Subject]:
        """配置可能な科目を柔軟に取得"""
        
        # 1. まず通常の配置可能科目を取得
        regular_subjects = self._get_regular_subjects(schedule, school, class_ref)
        
        # 2. 時数が余っている科目も候補に追加（借用可能）
        surplus_subjects = self._get_surplus_subjects(schedule, school, class_ref)
        
        # 3. 緊急時は固定科目以外すべてを候補に
        all_subjects = self._get_all_non_fixed_subjects(school, class_ref)
        
        # 優先順位: 通常 > 余剰 > すべて
        subjects = []
        seen = set()
        
        for subj in regular_subjects + surplus_subjects + all_subjects:
            if subj.name not in seen:
                subjects.append(subj)
                seen.add(subj.name)
        
        return subjects
    
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """柔軟な候補リストを作成"""
        
        candidates = []
        subjects = self.get_placeable_subjects(schedule, school, time_slot, class_ref)
        
        for subject in subjects:
            # 1. 通常の担当教師を試す
            regular_teacher = school.get_assigned_teacher(subject, class_ref)
            if regular_teacher and self._is_teacher_available_flexibly(
                schedule, regular_teacher, time_slot
            ):
                candidates.append((subject, regular_teacher))
            
            # 2. 代替教師を探す（同じ教科を教えられる他の教師）
            substitute_teachers = self._find_substitute_teachers(
                school, subject, class_ref, regular_teacher
            )
            for teacher in substitute_teachers:
                if self._is_teacher_available_flexibly(schedule, teacher, time_slot):
                    candidates.append((subject, teacher))
                    self.logger.info(
                        f"代替教師を発見: {teacher.name} が {class_ref} の "
                        f"{subject.name} を担当可能（通常: {regular_teacher.name if regular_teacher else 'なし'}）"
                    )
            
            # 3. 緊急時：他学年の教師も検討
            if not candidates:
                emergency_teachers = self._find_emergency_teachers(
                    school, subject, time_slot, schedule
                )
                for teacher in emergency_teachers:
                    candidates.append((subject, teacher))
                    self.logger.warning(
                        f"緊急対応: {teacher.name} を {class_ref} の "
                        f"{subject.name} に一時配置"
                    )
        
        # 4. 特殊な解決策：時数0での配置（体育など）
        if not candidates and self._can_use_zero_hour_solution(time_slot, class_ref):
            zero_hour_candidates = self._create_zero_hour_candidates(
                school, class_ref
            )
            candidates.extend(zero_hour_candidates)
        
        return candidates
    
    def _get_regular_subjects(
        self, schedule: Schedule, school: School, class_ref: ClassReference
    ) -> List[Subject]:
        """通常の配置可能科目を取得"""
        subjects = []
        base_hours = school.get_all_standard_hours(class_ref)
        current_hours = self._count_current_hours(schedule, class_ref)
        
        for subject, required in base_hours.items():
            if self._is_fixed_subject(subject.name):
                continue
            current = current_hours.get(subject, 0)
            if current < required:
                subjects.append(subject)
        
        return subjects
    
    def _get_surplus_subjects(
        self, schedule: Schedule, school: School, class_ref: ClassReference
    ) -> List[Subject]:
        """時数に余裕がある科目を取得"""
        subjects = []
        base_hours = school.get_all_standard_hours(class_ref)
        current_hours = self._count_current_hours(schedule, class_ref)
        
        # 標準時数を満たしていても、+1時間まで許容
        for subject, required in base_hours.items():
            if self._is_fixed_subject(subject.name):
                continue
            current = current_hours.get(subject, 0)
            if current == required:  # 標準時数ちょうど
                subjects.append(subject)
        
        return subjects
    
    def _get_all_non_fixed_subjects(
        self, school: School, class_ref: ClassReference
    ) -> List[Subject]:
        """固定科目以外のすべての科目を取得"""
        subjects = []
        base_hours = school.get_all_standard_hours(class_ref)
        
        for subject in base_hours.keys():
            if not self._is_fixed_subject(subject.name):
                subjects.append(subject)
        
        return subjects
    
    def _is_teacher_available_flexibly(
        self, schedule: Schedule, teacher: Teacher, time_slot: TimeSlot
    ) -> bool:
        """教師が柔軟に利用可能かチェック"""
        # 通常のチェックに加えて、緊急時の例外を許可
        
        # その時間に既に授業がある場合
        for class_ref in schedule.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher == teacher:
                # 5組の合同授業は例外
                if self._is_grade5_class(class_ref):
                    continue
                return False
        
        return True
    
    def _find_substitute_teachers(
        self, school: School, subject: Subject, class_ref: ClassReference,
        regular_teacher: Optional[Teacher]
    ) -> List[Teacher]:
        """代替教師を探す"""
        substitutes = []
        
        # 同じ教科を教えられる他の教師を探す
        all_subject_teachers = school.get_subject_teachers(subject)
        
        for teacher in all_subject_teachers:
            if teacher != regular_teacher:
                # 同学年の他クラスを教えている教師を優先
                if self._teaches_same_grade(school, teacher, class_ref.grade):
                    substitutes.insert(0, teacher)
                else:
                    substitutes.append(teacher)
        
        return substitutes
    
    def _find_emergency_teachers(
        self, school: School, subject: Subject, 
        time_slot: TimeSlot, schedule: Schedule
    ) -> List[Teacher]:
        """緊急時の教師を探す"""
        emergency = []
        
        # その時間に空いているすべての教師から探す
        all_teachers = school.get_all_teachers()
        
        for teacher in all_teachers:
            # その時間に授業がない
            if self._is_teacher_available_flexibly(schedule, teacher, time_slot):
                # 関連教科を教えられる可能性がある
                if self._can_teach_related_subject(teacher, subject):
                    emergency.append(teacher)
        
        return emergency
    
    def _can_use_zero_hour_solution(
        self, time_slot: TimeSlot, class_ref: ClassReference
    ) -> bool:
        """時数0での配置が可能かチェック"""
        # 体育など、緊急時に時数0で配置可能な条件
        # 例：金曜の午後など
        if time_slot.day == "金" and time_slot.period >= 5:
            return True
        return False
    
    def _create_zero_hour_candidates(
        self, school: School, class_ref: ClassReference
    ) -> List[Tuple[Subject, Teacher]]:
        """時数0の候補を作成"""
        candidates = []
        
        # 体育を時数0で配置
        pe_subject = None
        for subject in school.get_all_subjects():
            if subject.name == "保":
                pe_subject = subject
                break
        
        if pe_subject:
            # 仮の教師を割り当て
            dummy_teacher = Teacher("臨時", "臨時対応")
            candidates.append((pe_subject, dummy_teacher))
            self.logger.warning(
                f"時数0での緊急配置: {class_ref} に {pe_subject.name}（臨時対応）"
            )
        
        return candidates
    
    def _count_current_hours(
        self, schedule: Schedule, class_ref: ClassReference
    ) -> Dict[Subject, int]:
        """現在の時数をカウント"""
        hours = defaultdict(int)
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    hours[assignment.subject] += 1
        
        return hours
    
    def _is_fixed_subject(self, subject_name: str) -> bool:
        """固定科目かチェック"""
        fixed = {"欠", "YT", "学", "学活", "総", "総合", "道", "道徳", 
                 "学総", "行", "行事", "テスト", "技家"}
        return subject_name in fixed
    
    def _is_grade5_class(self, class_ref: ClassReference) -> bool:
        """5組かチェック"""
        return class_ref.class_num == 5
    
    def _teaches_same_grade(
        self, school: School, teacher: Teacher, grade: int
    ) -> bool:
        """同学年を教えているかチェック"""
        # 簡易実装：教師名から判断
        # TODO: より正確な実装が必要
        return True
    
    def _can_teach_related_subject(
        self, teacher: Teacher, subject: Subject
    ) -> bool:
        """関連教科を教えられるかチェック"""
        # 簡易実装：一部の組み合わせを許可
        related = {
            "数": ["算", "理"],
            "算": ["数", "理"],
            "国": ["社", "道"],
            "理": ["数", "算"],
            "英": ["国"],
        }
        
        # 教師が教えられる教科を推定（実際には教師データから取得すべき）
        teacher_subjects = self._estimate_teacher_subjects(teacher)
        
        for teach_subj in teacher_subjects:
            if teach_subj == subject.name:
                return True
            if teach_subj in related and subject.name in related[teach_subj]:
                return True
        
        return False
    
    def _estimate_teacher_subjects(self, teacher: Teacher) -> Set[str]:
        """教師が教えられる教科を推定"""
        # 簡易実装：教師名から推定
        # TODO: 実際の教師データから取得
        return {"国", "数", "英", "理", "社"}
    
    def get_max_daily_occurrences(self, subject_name: str) -> int:
        """教科の1日最大配置数を取得"""
        # 柔軟性を重視し、通常より緩い制限
        return 2  # 緊急時は1日2回まで許容
    
    def should_check_consecutive_periods(self) -> bool:
        """連続時限チェックを行うか"""
        return False  # 柔軟性のため連続も許可
    
    def should_check_daily_duplicate_strictly(self) -> bool:
        """日内重複を厳密にチェックするか"""
        return False  # 柔軟性のため緩いチェック
    
    def should_filter_forbidden_subjects(self) -> bool:
        """禁止科目をフィルタするか"""
        return True  # 固定科目は守る