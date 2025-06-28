"""会議時間・教師不在の最適化サービス"""
import logging
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from ....domain.interfaces.teacher_absence_repository import ITeacherAbsenceRepository


class MeetingTimeOptimizer:
    """会議時間と教師不在を最適化するサービス"""
    
    def __init__(self, absence_repository: Optional[ITeacherAbsenceRepository] = None,
                 regular_meetings: Optional[Dict] = None,
                 teacher_roles: Optional[Dict] = None,
                 all_day_absences: Optional[Dict] = None):
        """初期化
        
        Args:
            absence_repository: 教師不在情報リポジトリ
            regular_meetings: 定例会議の設定（QA.txtから読み込み）
            teacher_roles: 教師の役職（QA.txtから読み込み）
            all_day_absences: 終日不在の教師（QA.txtから読み込み）
        """
        self.logger = logging.getLogger(__name__)
        
        # 依存性注入
        if absence_repository is None:
            from ....infrastructure.di_container import get_teacher_absence_repository
            absence_repository = get_teacher_absence_repository()
            
        self.absence_repository = absence_repository
        
        # 定例会議の設定（外部から注入、デフォルトは空）
        self._regular_meetings = regular_meetings or {}
        
        # 教師の役職（外部から注入、デフォルトは空）
        self._teacher_roles = teacher_roles or {}
        
        # 終日不在の教師（外部から注入、デフォルトは空）
        self._all_day_absences = all_day_absences or {}
    
    def optimize_meeting_times(self, schedule: Schedule, school: School) -> Tuple[Schedule, int]:
        """会議時間を最適化"""
        self.logger.info("=== 会議時間最適化を開始 ===")
        
        changes_count = 0
        
        # Step 1: 会議参加者の授業を確認・調整
        changes_count += self._adjust_meeting_participants(schedule, school)
        
        # Step 2: 終日不在教師の授業を削除
        changes_count += self._handle_all_day_absences(schedule, school)
        
        # Step 3: 部分的な不在の処理
        changes_count += self._handle_partial_absences(schedule, school)
        
        # Step 4: 会議時間の保護（ロック）
        self._protect_meeting_times(schedule, school)
        
        self.logger.info(f"会議時間最適化完了: {changes_count}件の変更")
        
        return schedule, changes_count
    
    def _adjust_meeting_participants(self, schedule: Schedule, school: School) -> int:
        """会議参加者の授業を調整"""
        changes = 0
        
        for meeting_name, meeting_info in self._regular_meetings.items():
            if isinstance(meeting_info, dict) and "day" in meeting_info:
                day = meeting_info["day"]
                period = meeting_info["period"]
                participants = meeting_info["participants"]
                
                time_slot = TimeSlot(day, period)
                
                for teacher_name in participants:
                    teacher = Teacher(teacher_name)
                    
                    # この時間に授業がある場合は移動または削除
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                            # 授業を別の時間に移動を試みる
                            if self._move_lesson_to_alternative_slot(
                                schedule, school, time_slot, class_ref, assignment
                            ):
                                changes += 1
                                self.logger.info(
                                    f"{meeting_name}のため{teacher_name}先生の授業を移動: "
                                    f"{class_ref} {time_slot}"
                                )
                            else:
                                # 移動できない場合は削除
                                schedule.remove_assignment(time_slot, class_ref)
                                changes += 1
                                self.logger.warning(
                                    f"{meeting_name}のため{teacher_name}先生の授業を削除: "
                                    f"{class_ref} {time_slot}"
                                )
        
        return changes
    
    def _handle_all_day_absences(self, schedule: Schedule, school: School) -> int:
        """終日不在教師の授業を削除"""
        changes = 0
        
        for day, absent_teachers in self._all_day_absences.items():
            for teacher_name in absent_teachers:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if (assignment and assignment.teacher and 
                            assignment.teacher.name == teacher_name):
                            
                            # ロックされていない場合のみ削除
                            if not schedule.is_locked(time_slot, class_ref):
                                schedule.remove_assignment(time_slot, class_ref)
                                changes += 1
                                self.logger.info(
                                    f"終日不在により削除: {teacher_name}先生 "
                                    f"{time_slot} {class_ref}"
                                )
        
        return changes
    
    def _handle_partial_absences(self, schedule: Schedule, school: School) -> int:
        """部分的な不在の処理"""
        changes = 0
        
        # Follow-up.csvから読み込んだ不在情報を処理
        partial_absences = {
            ("井野口", "火", 5): "不在",
            ("井野口", "火", 6): "不在",
            ("金子み", "水", 4): "外勤",
            ("金子み", "水", 5): "外勤",
            ("金子み", "水", 6): "外勤",
            ("井上", "金", 4): "外勤",
            ("井上", "金", 5): "外勤",
            ("井上", "金", 6): "外勤",
            ("永山", "金", 4): "外勤",
            ("永山", "金", 5): "外勤",
            ("永山", "金", 6): "外勤",
            ("梶永", "金", 5): "出張",
            ("梶永", "金", 6): "出張",
        }
        
        for (teacher_name, day, period), reason in partial_absences.items():
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if (assignment and assignment.teacher and 
                    assignment.teacher.name == teacher_name):
                    
                    if not schedule.is_locked(time_slot, class_ref):
                        # 代替教師を探す
                        alt_teacher = self._find_substitute_teacher(
                            schedule, school, assignment.subject, time_slot, [teacher_name]
                        )
                        
                        if alt_teacher:
                            # 代替教師で置き換え
                            schedule.remove_assignment(time_slot, class_ref)
                            new_assignment = Assignment(
                                class_ref, assignment.subject, alt_teacher
                            )
                            schedule.assign(time_slot, new_assignment)
                            changes += 1
                            self.logger.info(
                                f"代替教師配置: {teacher_name}→{alt_teacher.name} "
                                f"{time_slot} {class_ref} ({reason})"
                            )
                        else:
                            # 代替が見つからない場合は削除
                            schedule.remove_assignment(time_slot, class_ref)
                            changes += 1
                            self.logger.warning(
                                f"代替不可により削除: {teacher_name}先生 "
                                f"{time_slot} {class_ref} ({reason})"
                            )
        
        return changes
    
    def _move_lesson_to_alternative_slot(self, schedule: Schedule, school: School,
                                       original_slot: TimeSlot, class_ref: ClassReference,
                                       assignment: Assignment) -> bool:
        """授業を別の時間枠に移動"""
        # 同じ曜日の別の時限を優先的に探す
        for period in range(1, 7):
            if period == original_slot.period:
                continue
            
            alt_slot = TimeSlot(original_slot.day, period)
            
            # 移動可能かチェック
            if self._can_move_to_slot(schedule, school, class_ref, assignment, alt_slot):
                # 元の授業を削除
                schedule.remove_assignment(original_slot, class_ref)
                
                # 新しい時間に配置
                schedule.assign(alt_slot, assignment)
                return True
        
        # 別の曜日も試す
        for day in ["月", "火", "水", "木", "金"]:
            if day == original_slot.day:
                continue
            
            for period in range(1, 7):
                alt_slot = TimeSlot(day, period)
                
                if self._can_move_to_slot(schedule, school, class_ref, assignment, alt_slot):
                    schedule.remove_assignment(original_slot, class_ref)
                    schedule.assign(alt_slot, assignment)
                    return True
        
        return False
    
    def _can_move_to_slot(self, schedule: Schedule, school: School,
                         class_ref: ClassReference, assignment: Assignment,
                         target_slot: TimeSlot) -> bool:
        """指定時間枠に移動可能かチェック"""
        # 既に授業がある場合は不可
        if schedule.get_assignment(target_slot, class_ref):
            return False
        
        # ロックされている場合は不可
        if schedule.is_locked(target_slot, class_ref):
            return False
        
        # 教師が利用可能かチェック
        if assignment.teacher:
            # 他のクラスで授業がないか
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(target_slot, other_class)
                if (other_assignment and other_assignment.teacher and 
                    other_assignment.teacher.name == assignment.teacher.name):
                    return False
            
            # 不在チェック
            if self.absence_repository.is_teacher_absent(
                assignment.teacher.name, target_slot.day, target_slot.period
            ):
                return False
        
        # 特別な時間枠（月6限、YT等）は避ける
        if (target_slot.day == "月" and target_slot.period == 6) or \
           (target_slot.day in ["火", "水", "金"] and target_slot.period == 6):
            return False
        
        return True
    
    def _find_substitute_teacher(self, schedule: Schedule, school: School, subject: Subject,
                               time_slot: TimeSlot, 
                               unavailable_teachers: List[str]) -> Optional[Teacher]:
        """代替教師を探す"""
        # 同じ教科を担当できる教師を探す
        subject_teachers = school.get_subject_teachers(subject)
        
        for teacher in subject_teachers:
            if teacher.name in unavailable_teachers:
                continue
            
            # この時間に空いているかチェック
            is_available = True
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if (assignment and assignment.teacher and 
                    assignment.teacher.name == teacher.name):
                    is_available = False
                    break
            
            if is_available and not self.absence_repository.is_teacher_absent(
                teacher.name, time_slot.day, time_slot.period
            ):
                return teacher
        
        return None
    
    def _protect_meeting_times(self, schedule: Schedule, school: School) -> None:
        """会議時間をロック（保護）"""
        # 会議参加者の該当時間をロック
        for meeting_name, meeting_info in self._regular_meetings.items():
            if isinstance(meeting_info, dict) and "day" in meeting_info:
                day = meeting_info["day"]
                period = meeting_info["period"]
                participants = meeting_info["participants"]
                
                time_slot = TimeSlot(day, period)
                
                self.logger.info(
                    f"{meeting_name}（{day}曜{period}限）をロック: "
                    f"参加者{len(participants)}名"
                )