"""5組同期サービス（リファクタリング版）

制約を考慮した5組（1年5組、2年5組、3年5組）の同期処理
"""
import logging
import re
from typing import List, Optional, Tuple, Dict, TYPE_CHECKING
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...value_objects.assignment import Assignment
from ...interfaces.teacher_absence_repository import ITeacherAbsenceRepository
from ...utils.schedule_utils import ScheduleUtils

if TYPE_CHECKING:
    from ...constraints.base import ConstraintValidator

class RefactoredGrade5Synchronizer(LoggingMixin):
    """制約を考慮した5組同期サービス"""
    
    def __init__(self, constraint_validator: Optional['ConstraintValidator'] = None,
                 absence_repository: Optional[ITeacherAbsenceRepository] = None):
        super().__init__()
        
        # 依存性注入
        if absence_repository is None:
            from ....infrastructure.di_container import get_teacher_absence_repository
            absence_repository = get_teacher_absence_repository()
            
        self.absence_repository = absence_repository
        self.constraint_validator = constraint_validator
        
        # 5組クラス（ScheduleUtilsから取得）
        grade5_list = ScheduleUtils.get_grade5_classes()
        self.grade5_classes = []
        for class_str in grade5_list:
            # "1年5組" -> ClassReference(1, 5)
            match = re.match(r'(\d+)年(\d+)組', class_str)
            if match:
                self.grade5_classes.append(ClassReference(int(match.group(1)), int(match.group(2))))
        self._sync_stats = {
            'attempted': 0,
            'successful': 0,
            'constraint_violations': 0,
            'teacher_absences': 0
        }
    
    def synchronize_grade5_classes(self, schedule: Schedule, school: School) -> None:
        """5組の授業を同期させる（制約考慮版）"""
        self.logger.info("=== 5組の同期処理を開始（制約考慮版） ===")
        
        # 各時間枠で5組を同期
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                self._synchronize_time_slot_with_constraints(schedule, school, time_slot)
        
        self._log_statistics()
        self.logger.info("=== 5組の同期処理を完了 ===")
    
    def _synchronize_time_slot_with_constraints(self, schedule: Schedule, school: School, 
                                                time_slot: TimeSlot) -> None:
        """特定の時間枠で5組を同期（制約チェック付き）"""
        self._sync_stats['attempted'] += 1
        
        # 現在の割り当てを取得
        current_assignments = []
        locked_info = []
        
        for class_ref in self.grade5_classes:
            assignment = schedule.get_assignment(time_slot, class_ref)
            is_locked = schedule.is_locked(time_slot, class_ref)
            current_assignments.append((class_ref, assignment))
            locked_info.append((class_ref, is_locked))
        
        # すでに同期している場合はスキップ
        subjects = [a.subject.name if a else None for _, a in current_assignments]
        unique_subjects = set(s for s in subjects if s is not None)
        if len(unique_subjects) <= 1:
            return
        
        # 全てロックされている場合はスキップ
        if all(is_locked for _, is_locked in locked_info):
            self.logger.debug(f"{time_slot}: 全ての5組セルがロックされています")
            return
        
        # 同期する教科を決定
        chosen_subject, chosen_teacher = self._choose_subject_for_sync(
            current_assignments, locked_info, school, time_slot
        )
        
        if not chosen_subject or not chosen_teacher:
            self.logger.warning(f"{time_slot}: 5組同期用の教科/教員が見つかりません")
            return
        
        # 教員不在チェック
        if self._is_teacher_absent(chosen_teacher, time_slot):
            self._sync_stats['teacher_absences'] += 1
            return
        
        # 各5組クラスに配置を試みる
        sync_successful = True
        assignments_to_make = []
        
        for class_ref, is_locked in locked_info:
            if is_locked:
                continue
                
            assignment = Assignment(class_ref, chosen_subject, chosen_teacher)
            
            # 制約チェック
            if self.constraint_validator:
                if not self.constraint_validator.check_assignment(schedule, school, time_slot, assignment):
                    self.logger.warning(
                        f"制約違反: {time_slot} {class_ref} {chosen_subject.name} "
                        f"- 5組同期をスキップ"
                    )
                    self._sync_stats['constraint_violations'] += 1
                    sync_successful = False
                    break
            
            assignments_to_make.append((time_slot, assignment))
        
        # 全てのクラスで制約を満たす場合のみ同期実行
        if sync_successful and assignments_to_make:
            for time_slot, assignment in assignments_to_make:
                # 既存の割り当てを削除
                existing = schedule.get_assignment(time_slot, assignment.class_ref)
                if existing:
                    schedule.remove_assignment(time_slot, assignment.class_ref)
                
                # 新規割り当て
                schedule.assign(time_slot, assignment)
                
            self.logger.info(
                f"{time_slot}: 5組を{chosen_subject.name}({chosen_teacher.name})で同期"
            )
            self._sync_stats['successful'] += 1
    
    def _choose_subject_for_sync(self, current_assignments: List[Tuple[ClassReference, Optional[Assignment]]],
                                 locked_info: List[Tuple[ClassReference, bool]],
                                 school: School, time_slot: TimeSlot) -> Tuple[Optional[Subject], Optional[Teacher]]:
        """同期用の教科と教員を選択"""
        # ロックされたセルの教科を優先
        for (class_ref, assignment), (_, is_locked) in zip(current_assignments, locked_info):
            if is_locked and assignment:
                return assignment.subject, assignment.teacher
        
        # 最も多い教科を選択
        subject_counts = {}
        for (class_ref, assignment), (_, is_locked) in zip(current_assignments, locked_info):
            if not is_locked and assignment:
                subject_name = assignment.subject.name
                subject_counts[subject_name] = subject_counts.get(subject_name, 0) + 1
        
        if not subject_counts:
            return None, None
        
        chosen_subject_name = max(subject_counts, key=subject_counts.get)
        chosen_subject = Subject(chosen_subject_name)
        
        # 適切な教員を選択
        teacher = self._get_grade5_teacher(school, chosen_subject)
        
        return chosen_subject, teacher
    
    def _get_grade5_teacher(self, school: School, subject: Subject) -> Optional[Teacher]:
        """5組の特定教科の担当教員を取得"""
        # 各5組クラスから教員を探す
        for class_ref in self.grade5_classes:
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher:
                return teacher
        
        # 見つからない場合は、教科担当教員から選択
        teachers = school.get_teachers_for_subject(subject)
        if teachers:
            # 金子み先生を優先
            for teacher in teachers:
                if "金子み" in teacher.name:
                    return teacher
            return teachers[0]
        
        return None
    
    def _is_teacher_absent(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教員不在チェック"""
        if self.absence_repository.is_teacher_absent(teacher.name, time_slot):
            self.logger.warning(
                f"5組同期スキップ（教員不在）: {time_slot} {teacher.name}"
            )
            return True
        return False
    
    def fill_empty_slots_for_grade5(self, schedule: Schedule, school: School) -> int:
        """5組の空きコマを同時に埋める（制約考慮版）"""
        self.logger.info("=== 5組の空きコマ埋め処理を開始（制約考慮版） ===")
        
        filled_count = 0
        
        # 各時間枠をチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 全5組クラスが空きか確認
                empty_classes = []
                for class_ref in self.grade5_classes:
                    if not schedule.get_assignment(time_slot, class_ref):
                        if not schedule.is_locked(time_slot, class_ref):
                            empty_classes.append(class_ref)
                
                # 全クラスが空きでない場合はスキップ
                if len(empty_classes) != len(self.grade5_classes):
                    continue
                
                # 埋める教科を探す
                best_subject, best_teacher = self._find_best_subject_for_empty_slot(
                    schedule, school, time_slot
                )
                
                if not best_subject or not best_teacher:
                    continue
                
                # 教員不在チェック
                if self._is_teacher_absent(best_teacher, time_slot):
                    continue
                
                # 全クラスで制約チェック
                can_assign_all = True
                for class_ref in self.grade5_classes:
                    assignment = Assignment(class_ref, best_subject, best_teacher)
                    if self.constraint_validator:
                        if not self.constraint_validator.check_assignment(
                            schedule, school, time_slot, assignment
                        ):
                            can_assign_all = False
                            break
                
                # 制約を満たす場合のみ配置
                if can_assign_all:
                    for class_ref in self.grade5_classes:
                        assignment = Assignment(class_ref, best_subject, best_teacher)
                        schedule.assign(time_slot, assignment)
                    
                    self.logger.info(
                        f"{time_slot}: 5組に{best_subject.name}({best_teacher.name})を配置"
                    )
                    filled_count += 1
        
        self.logger.info(f"=== 5組の空きコマ埋め完了: {filled_count}時限を埋めました ===")
        return filled_count
    
    def _find_best_subject_for_empty_slot(self, schedule: Schedule, school: School,
                                         time_slot: TimeSlot) -> Tuple[Optional[Subject], Optional[Teacher]]:
        """空きコマに最適な教科を探す"""
        # 各クラスの不足時数を計算
        shortage_by_subject = {}
        
        for class_ref in self.grade5_classes:
            current_hours = self._count_subject_hours(schedule, class_ref)
            
            for subject in school.get_required_subjects(class_ref):
                # 固定科目はスキップ
                if ScheduleUtils.is_fixed_subject(subject.name):
                    continue
                    
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject.name, 0)
                shortage = standard - current
                
                if shortage > 0:
                    if subject.name not in shortage_by_subject:
                        shortage_by_subject[subject.name] = []
                    shortage_by_subject[subject.name].append(shortage)
        
        # 全クラスで不足している教科を優先
        best_subject_name = None
        best_shortage = 0
        
        for subject_name, shortages in shortage_by_subject.items():
            if len(shortages) == len(self.grade5_classes):  # 全クラスで不足
                avg_shortage = sum(shortages) / len(shortages)
                if avg_shortage > best_shortage:
                    best_shortage = avg_shortage
                    best_subject_name = subject_name
        
        if not best_subject_name:
            return None, None
        
        best_subject = Subject(best_subject_name)
        best_teacher = self._get_grade5_teacher(school, best_subject)
        
        return best_subject, best_teacher
    
    def _count_subject_hours(self, schedule: Schedule, class_ref: ClassReference) -> Dict[str, int]:
        """クラスの現在の教科別時数をカウント"""
        hours = {}
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    subject_name = assignment.subject.name
                    hours[subject_name] = hours.get(subject_name, 0) + 1
        return hours
    
    def ensure_grade5_sync(self, schedule: Schedule, school: School, time_slot: TimeSlot) -> bool:
        """特定の時間枠で5組の同期を確実に行う
        
        1つの5組クラスに科目が配置されたら、他の5組クラスにも同じ科目を配置する。
        全ての5組が空きの場合は、最適な科目を選んで配置する。
        
        Args:
            schedule: スケジュール
            school: 学校データ
            time_slot: 対象時間枠
            
        Returns:
            同期が成功したかどうか
        """
        # 現在の5組の配置状況を確認
        assignments = []
        empty_classes = []
        has_assignment = False
        existing_subject = None
        existing_teacher = None
        
        for class_ref in self.grade5_classes:
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                has_assignment = True
                if not existing_subject:
                    existing_subject = assignment.subject
                    existing_teacher = assignment.teacher
                assignments.append((class_ref, assignment))
            else:
                if not schedule.is_locked(time_slot, class_ref):
                    empty_classes.append(class_ref)
        
        # 既に全て同期している場合
        if len(assignments) == len(self.grade5_classes):
            return True
        
        # 一部に配置がある場合、同じ科目で空きを埋める
        if has_assignment and existing_subject and existing_teacher:
            success = True
            for class_ref in empty_classes:
                assignment = Assignment(class_ref, existing_subject, existing_teacher)
                
                # 制約チェック
                if self.constraint_validator:
                    if not self.constraint_validator.check_assignment(schedule, school, time_slot, assignment):
                        self.logger.warning(
                            f"制約違反: {time_slot} {class_ref} {existing_subject.name} - 5組同期失敗"
                        )
                        success = False
                        continue
                
                # 配置実行
                if schedule.assign(time_slot, assignment):
                    self.logger.info(
                        f"{time_slot}: {class_ref}に{existing_subject.name}({existing_teacher.name})を同期配置"
                    )
                else:
                    success = False
            
            return success
        
        # 全て空きの場合、最適な科目を選んで配置
        if len(empty_classes) == len(self.grade5_classes):
            subject, teacher = self._find_best_subject_for_empty_slot(schedule, school, time_slot)
            
            if subject and teacher:
                # 教員不在チェック
                if self._is_teacher_absent(teacher, time_slot):
                    return False
                
                # 全クラスで制約チェック
                can_assign_all = True
                for class_ref in self.grade5_classes:
                    assignment = Assignment(class_ref, subject, teacher)
                    if self.constraint_validator:
                        if not self.constraint_validator.check_assignment(
                            schedule, school, time_slot, assignment
                        ):
                            can_assign_all = False
                            break
                
                # 制約を満たす場合のみ配置
                if can_assign_all:
                    for class_ref in self.grade5_classes:
                        assignment = Assignment(class_ref, subject, teacher)
                        schedule.assign(time_slot, assignment)
                    
                    self.logger.info(
                        f"{time_slot}: 5組全てに{subject.name}({teacher.name})を新規配置"
                    )
                    return True
        
        return False
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        self.logger.info(
            f"5組同期統計: 試行={self._sync_stats['attempted']}, "
            f"成功={self._sync_stats['successful']}, "
            f"制約違反={self._sync_stats['constraint_violations']}, "
            f"教員不在={self._sync_stats['teacher_absences']}"
        )