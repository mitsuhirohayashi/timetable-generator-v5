"""5組同期サービスの実装"""
import logging
from typing import List, Dict, Optional

from ..interfaces.grade5_synchronization_service import Grade5SynchronizationService
from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject
from ...value_objects.assignment import Assignment
from ....infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfig


class SynchronizedGrade5Service(Grade5SynchronizationService):
    """5組同期サービス"""
    
    def __init__(self, config: AdvancedCSPConfig, constraint_validator):
        self.config = config
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
    
    def get_common_subjects(self, school: School, grade5_classes: List[ClassReference]) -> Dict[Subject, int]:
        """共通教科と必要時間数を取得"""
        common_subjects = {}
        
        # 各クラスの必要教科を収集
        class_subjects = {}
        for class_ref in grade5_classes:
            subjects = {}
            for subject in school.get_required_subjects(class_ref):
                if not subject.is_protected_subject():
                    hours = int(round(school.get_standard_hours(class_ref, subject)))
                    if hours > 0:
                        subjects[subject] = hours
            class_subjects[class_ref] = subjects
        
        # 共通教科を抽出
        if class_subjects:
            first_class_subjects = list(class_subjects.values())[0]
            for subject, hours in first_class_subjects.items():
                if all(subject in cs and cs[subject] == hours 
                      for cs in class_subjects.values()):
                    common_subjects[subject] = hours
        
        return common_subjects
    
    def synchronize_placement(self, schedule: Schedule, school: School) -> int:
        """5組の同期配置を実行"""
        self.logger.info("5組の同期配置を開始")
        
        grade5_classes = self.config.grade5_classes
        total_placed = 0
        
        # 共通教科を収集
        common_subjects = self.get_common_subjects(school, grade5_classes)
        
        for subject, required_hours in common_subjects.items():
            # 体育は同期から除外
            if subject.name in self.config.excluded_sync_subjects:
                continue
            
            placed_hours = self.count_placed_hours(schedule, grade5_classes, subject)
            
            for _ in range(required_hours - placed_hours):
                slot = self.find_best_slot_for_grade5(schedule, school, grade5_classes, subject)
                if slot:
                    # 全5組に同時配置
                    success = True
                    assignments = []
                    
                    for class_ref in grade5_classes:
                        teacher = school.get_assigned_teacher(subject, class_ref)
                        if teacher:
                            assignment = Assignment(class_ref, subject, teacher)
                            if self.constraint_validator.check_assignment(schedule, school, slot, assignment):
                                assignments.append((slot, assignment))
                            else:
                                success = False
                                break
                        else:
                            success = False
                            break
                    
                    if success:
                        for slot, assignment in assignments:
                            schedule.assign(slot, assignment)
                        total_placed += len(assignments)
                        self.logger.debug(f"{slot}: 5組に{subject.name}を同期配置")
        
        return total_placed
    
    def find_best_slot_for_grade5(self, schedule: Schedule, school: School,
                                  classes: List[ClassReference], subject: Subject) -> Optional[TimeSlot]:
        """5組の最適なスロットを探索"""
        best_slot = None
        best_score = float('inf')
        
        for day in self.config.weekdays:
            for period in range(self.config.periods_min, self.config.periods_max + 1):
                slot = TimeSlot(day, period)
                
                # 固定制約チェック
                if day == "月" and period == 6:
                    continue
                
                # 全クラスで利用可能か
                all_available = True
                for class_ref in classes:
                    if schedule.get_assignment(slot, class_ref):
                        all_available = False
                        break
                    
                    # ロックされているセルはスキップ
                    if schedule.is_locked(slot, class_ref):
                        all_available = False
                        break
                    
                    # 日内重複チェック
                    if self._has_subject_on_day(schedule, class_ref, slot.day, subject):
                        all_available = False
                        break
                    
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    if not self._is_teacher_available(teacher, slot, schedule, school):
                        all_available = False
                        break
                
                if all_available:
                    score = self._evaluate_slot_for_subject(slot, subject)
                    if score < best_score:
                        best_score = score
                        best_slot = slot
        
        return best_slot
    
    def count_placed_hours(self, schedule: Schedule, classes: List[ClassReference],
                          subject: Subject) -> int:
        """配置済み時間数をカウント"""
        count = 0
        checked_slots = set()
        
        for slot, assignment in schedule.get_all_assignments():
            if (assignment.class_ref in classes and 
                assignment.subject == subject and 
                slot not in checked_slots):
                # 全5組が同じ時間に配置されているか確認
                all_have_subject = all(
                    schedule.get_assignment(slot, c) and 
                    schedule.get_assignment(slot, c).subject == subject
                    for c in classes
                )
                if all_have_subject:
                    count += 1
                    checked_slots.add(slot)
        
        return count
    
    def _is_teacher_available(self, teacher, slot: TimeSlot, schedule: Schedule, school: School) -> bool:
        """教師が利用可能かチェック"""
        if not teacher:
            return False
        
        # スケジュール上の重複
        if not schedule.is_teacher_available(slot, teacher):
            return False
        
        # 学校の制約
        if school.is_teacher_unavailable(slot.day, slot.period, teacher):
            return False
        
        return True
    
    def _has_subject_on_day(self, schedule: Schedule, class_ref: ClassReference, day: str, subject: Subject) -> bool:
        """指定日に指定科目が既に配置されているかチェック"""
        # 保護教科は日内重複を許可
        protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        if subject.name in protected_subjects:
            return False
        
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                return True
        return False
    
    def _evaluate_slot_for_subject(self, slot: TimeSlot, subject: Subject) -> float:
        """教科に対するスロットの評価"""
        score = 0.0
        
        # 体育は火曜日を優先
        if subject.name == "保" and slot.day == self.config.pe_preferred_day:
            score -= 20
        
        # 主要教科は午前中を優先
        if subject.name in self.config.main_subjects and slot.period in self.config.main_subjects_preferred_periods:
            score -= 10
        
        # 技能教科は午後でも可
        if subject.name in self.config.skill_subjects and slot.period in self.config.skill_subjects_preferred_periods:
            score -= 5
        
        return score