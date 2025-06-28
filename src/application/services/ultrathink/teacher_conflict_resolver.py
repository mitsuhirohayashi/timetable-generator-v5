"""教師重複解消戦略

教師の重複を解消するための専門的な戦略クラス。
"""
from typing import List, Dict, Set, Optional, Tuple
import logging
from collections import defaultdict

from ....domain.entities import School, Schedule
from ....domain.value_objects.time_slot import TimeSlot, ClassReference as ClassRef, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from .schedule_helpers import ScheduleHelpers

logger = logging.getLogger(__name__)


class TeacherConflictResolver:
    """教師の重複を解消する戦略クラス"""
    
    def __init__(self, helpers: ScheduleHelpers):
        self.helpers = helpers
    
    def find_teacher_conflicts(self, schedule: Schedule, school: School) -> Dict[Tuple[str, TimeSlot], List[ClassRef]]:
        """教師の重複を検出
        
        Returns:
            Dict[(teacher_name, time_slot), List[ClassRef]]: 重複している教師と時間、クラスのリスト
        """
        conflicts = defaultdict(list)
        
        # 各時間スロットごとに教師の割り当てをチェック
        for time_slot in self.helpers.get_all_time_slots():
            teacher_assignments = defaultdict(list)
            
            # その時間の全クラスの割り当てを取得
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher:
                    teacher_name = assignment.teacher.name
                    teacher_assignments[teacher_name].append(class_ref)
            
            # 重複をチェック（2つ以上のクラスを持つ教師）
            for teacher_name, classes in teacher_assignments.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [c for c in classes if c.class_number == 5]
                    if len(grade5_classes) == len(classes):
                        continue  # 全て5組なら問題なし
                    
                    conflicts[(teacher_name, time_slot)] = classes
        
        return dict(conflicts)
    
    def resolve_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師の重複を解消
        
        Returns:
            int: 解消した重複数
        """
        resolved_count = 0
        conflicts = self.find_teacher_conflicts(schedule, school)
        
        logger.info(f"教師重複を{len(conflicts)}件検出")
        
        for (teacher_name, time_slot), conflicting_classes in conflicts.items():
            logger.debug(f"{teacher_name}が{time_slot}に{len(conflicting_classes)}クラスで重複")
            
            # 最初のクラスは維持し、他のクラスの割り当てを変更
            keep_class = conflicting_classes[0]
            for class_ref in conflicting_classes[1:]:
                if self._reassign_class(schedule, school, class_ref, time_slot, teacher_name):
                    resolved_count += 1
        
        logger.info(f"教師重複を{resolved_count}件解消")
        return resolved_count
    
    def _reassign_class(self, schedule: Schedule, school: School, 
                       class_ref: ClassRef, conflict_slot: TimeSlot,
                       conflict_teacher: str) -> bool:
        """クラスの割り当てを変更して重複を解消
        
        Args:
            class_ref: 変更するクラス
            conflict_slot: 重複が発生している時間スロット
            conflict_teacher: 重複している教師名
            
        Returns:
            bool: 成功したかどうか
        """
        # ロックされている場合は変更不可
        if schedule.is_locked(conflict_slot, class_ref):
            return False
        
        current_assignment = schedule.get_assignment(conflict_slot, class_ref)
        if not current_assignment:
            return False
        
        subject = current_assignment.subject.name
        
        # 他の利用可能な教師を探す
        alternative_teacher = self._find_alternative_teacher(
            schedule, school, class_ref, subject, conflict_slot, conflict_teacher
        )
        
        if alternative_teacher:
            # 教師を変更
            new_assignment = Assignment(
                class_ref=class_ref,
                subject=current_assignment.subject,
                teacher=alternative_teacher
            )
            try:
                schedule.assign(conflict_slot, new_assignment)
                logger.debug(f"{class_ref}の{conflict_slot}の教師を{conflict_teacher}から{alternative_teacher.name}に変更")
                return True
            except Exception as e:
                logger.warning(f"教師変更エラー: {e}")
        
        # 教師変更ができない場合は、他の時間スロットと交換
        return self._swap_with_other_slot(schedule, school, class_ref, conflict_slot, subject)
    
    def _find_alternative_teacher(self, schedule: Schedule, school: School, class_ref: ClassRef,
                                 subject: str, time_slot: TimeSlot,
                                 exclude_teacher: str) -> Optional[Teacher]:
        """代替教師を探す
        
        Args:
            exclude_teacher: 除外する教師名
            
        Returns:
            Optional[Teacher]: 利用可能な代替教師
        """
        from .....domain.value_objects.time_slot import Subject as SubjectObj
        subject_obj = SubjectObj(subject)
        
        # その教科を教えられる全教師を取得
        for teacher in school.get_subject_teachers(subject_obj):
            if teacher.name == exclude_teacher:
                continue
            
            # その時間に空いているかチェック
            if self._is_teacher_available(schedule, school, teacher, time_slot):
                return teacher
        
        return None
    
    def _is_teacher_available(self, schedule: Schedule, school: School,
                             teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師がその時間に利用可能かチェック"""
        # その時間の全クラスをチェック
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher == teacher:
                # 既に別のクラスを担当している
                return False
        return True
    
    def _swap_with_other_slot(self, schedule: Schedule, school: School,
                             class_ref: ClassRef, conflict_slot: TimeSlot,
                             subject: str) -> bool:
        """他の時間スロットと交換して重複を解消
        
        Returns:
            bool: 成功したかどうか
        """
        # 同じ曜日の他の時間を探す
        for period in range(1, 7):
            if period == conflict_slot.period:
                continue
            
            swap_slot = TimeSlot(day=conflict_slot.day, period=period)
            
            # ロックされている場合はスキップ
            if schedule.is_locked(swap_slot, class_ref):
                continue
            
            swap_assignment = schedule.get_assignment(swap_slot, class_ref)
            if not swap_assignment:
                continue
            
            # 交換可能かチェック
            if self._can_swap(schedule, school, class_ref, conflict_slot, swap_slot):
                # 交換実行
                conflict_assignment = schedule.get_assignment(conflict_slot, class_ref)
                
                try:
                    # 一時的に削除
                    schedule.remove_assignment(conflict_slot, class_ref)
                    schedule.remove_assignment(swap_slot, class_ref)
                    
                    # 交換して再配置
                    schedule.assign(conflict_slot, Assignment(
                        class_ref=class_ref,
                        subject=swap_assignment.subject,
                        teacher=swap_assignment.teacher
                    ))
                    schedule.assign(swap_slot, Assignment(
                        class_ref=class_ref,
                        subject=conflict_assignment.subject,
                        teacher=conflict_assignment.teacher
                    ))
                    
                    logger.debug(f"{class_ref}の{conflict_slot}と{swap_slot}を交換")
                    return True
                    
                except Exception as e:
                    logger.warning(f"スロット交換エラー: {e}")
                    # ロールバック
                    try:
                        schedule.assign(conflict_slot, conflict_assignment)
                        schedule.assign(swap_slot, swap_assignment)
                    except:
                        pass
        
        return False
    
    def _can_swap(self, schedule: Schedule, school: School,
                  class_ref: ClassRef, slot1: TimeSlot, slot2: TimeSlot) -> bool:
        """2つのスロットを交換可能かチェック"""
        assignment1 = schedule.get_assignment(slot1, class_ref)
        assignment2 = schedule.get_assignment(slot2, class_ref)
        
        if not assignment1 or not assignment2:
            return False
        
        # 固定科目は交換不可
        fixed_subjects = ["欠", "YT", "学", "道", "総", "学総", "行"]
        if assignment1.subject.name in fixed_subjects or assignment2.subject.name in fixed_subjects:
            return False
        
        # 日内重複チェック
        if self.helpers.would_create_daily_duplicate(schedule, class_ref, slot1, assignment2.subject.name):
            return False
        if self.helpers.would_create_daily_duplicate(schedule, class_ref, slot2, assignment1.subject.name):
            return False
        
        # 教師の可用性チェック
        if assignment1.teacher:
            if not self._is_teacher_available_for_swap(schedule, school, assignment1.teacher, slot2, class_ref):
                return False
        if assignment2.teacher:
            if not self._is_teacher_available_for_swap(schedule, school, assignment2.teacher, slot1, class_ref):
                return False
        
        return True
    
    def _is_teacher_available_for_swap(self, schedule: Schedule, school: School,
                                       teacher: Teacher, new_slot: TimeSlot,
                                       swap_class: ClassRef) -> bool:
        """教師が新しいスロットで利用可能かチェック（交換元のクラスを除く）"""
        for class_ref in school.get_all_classes():
            if class_ref == swap_class:
                continue  # 交換元のクラスは除外
            
            assignment = schedule.get_assignment(new_slot, class_ref)
            if assignment and assignment.teacher == teacher:
                return False
        
        return True
    
    def _get_test_periods(self) -> Set[Tuple[str, str]]:
        """テスト期間のスロットを取得"""
        return {
            ("月", "1"), ("月", "2"), ("月", "3"),
            ("火", "1"), ("火", "2"), ("火", "3"),
            ("水", "1"), ("水", "2")
        }