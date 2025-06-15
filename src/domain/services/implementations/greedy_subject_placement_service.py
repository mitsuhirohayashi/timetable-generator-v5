"""貪欲法による通常教科配置サービスの実装"""
import logging
from typing import Optional

from ..interfaces.regular_subject_placement_service import RegularSubjectPlacementService
from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...value_objects.assignment import Assignment
from ....infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from ....infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfig


class GreedySubjectPlacementService(RegularSubjectPlacementService):
    """貪欲法による通常教科配置サービス"""
    
    def __init__(self, config: AdvancedCSPConfig, constraint_validator):
        self.config = config
        self.constraint_validator = constraint_validator
        self.absence_loader = TeacherAbsenceLoader()
        self.logger = logging.getLogger(__name__)
    
    def place_subjects(self, schedule: Schedule, school: School) -> int:
        """通常教科を配置"""
        self.logger.info("残りの教科の配置を開始")
        total_placed = 0
        
        # 各クラスの未配置教科を収集
        for class_ref in school.get_all_classes():
            # 5組と交流学級は既に処理済み
            if class_ref.class_number in [5, 6, 7]:
                continue
            
            for subject in school.get_required_subjects(class_ref):
                if subject.is_protected_subject():
                    continue
                
                required_hours = int(round(school.get_standard_hours(class_ref, subject)))
                placed_hours = sum(
                    1 for _, assignment in schedule.get_all_assignments()
                    if assignment.class_ref == class_ref and assignment.subject == subject
                )
                
                teacher = school.get_assigned_teacher(subject, class_ref)
                if not teacher:
                    continue
                
                # 不足分を配置
                for _ in range(required_hours - placed_hours):
                    slot = self.find_best_slot(schedule, school, class_ref, subject, teacher)
                    if slot:
                        assignment = Assignment(class_ref, subject, teacher)
                        try:
                            schedule.assign(slot, assignment)
                            total_placed += 1
                        except ValueError as e:
                            # 固定科目保護により配置できない場合
                            self.logger.debug(f"固定科目保護により配置不可: {e}")
                            continue
        
        return total_placed
    
    def find_best_slot(self, schedule: Schedule, school: School,
                      class_ref: ClassReference, subject: Subject,
                      teacher: Teacher) -> Optional[TimeSlot]:
        """最適なスロットを探索"""
        best_slot = None
        best_score = float('inf')
        
        for day in self.config.weekdays:
            for period in range(self.config.periods_min, self.config.periods_max + 1):
                slot = TimeSlot(day, period)
                
                # 固定制約チェック
                if day == "月" and period == 6:
                    continue
                
                # 配置可能かチェック
                if (not schedule.get_assignment(slot, class_ref) and
                    not schedule.is_locked(slot, class_ref) and  # ロックされていないこと
                    self.can_place_subject(schedule, school, class_ref, slot, subject, teacher)):
                    score = self.evaluate_slot_for_subject(slot, subject)
                    if score < best_score:
                        best_score = score
                        best_slot = slot
        
        return best_slot
    
    def can_place_subject(self, schedule: Schedule, school: School,
                         class_ref: ClassReference, slot: TimeSlot,
                         subject: Subject, teacher: Teacher) -> bool:
        """教科を配置可能かチェック"""
        if not self._is_teacher_available(teacher, slot, schedule, school):
            return False
        
        # 日内重複チェック（保護教科を除く）
        protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        if subject.name not in protected_subjects:
            daily_count = sum(
                1 for period in range(1, 7)
                for s, a in schedule.get_all_assignments()
                if (s.day == slot.day and s.period == period and 
                    a.class_ref == class_ref and a.subject == subject)
            )
            if daily_count > 0:
                self.logger.debug(f"{class_ref}の{slot.day}曜日に{subject.name}が既に配置されているため配置不可")
                return False
        
        # 制約チェック
        temp_assignment = Assignment(class_ref, subject, teacher)
        return self.constraint_validator.check_assignment(schedule, school, slot, temp_assignment)
    
    def evaluate_slot_for_subject(self, slot: TimeSlot, subject: Subject) -> float:
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
    
    def _is_teacher_available(self, teacher: Teacher, slot: TimeSlot,
                            schedule: Schedule, school: School) -> bool:
        """教師が利用可能かチェック"""
        if not teacher:
            return True
        
        # スケジュール上の重複
        if not schedule.is_teacher_available(slot, teacher):
            return False
        
        # 不在情報
        if self.absence_loader.is_teacher_absent(teacher.name, slot.day, slot.period):
            return False
        
        # 学校の制約
        if school.is_teacher_unavailable(slot.day, slot.period, teacher):
            return False
        
        return True