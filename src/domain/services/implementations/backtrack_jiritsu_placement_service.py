"""バックトラッキングによる自立活動配置サービスの実装"""
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from ..interfaces.jiritsu_placement_service import JiritsuPlacementService
from ..interfaces.jiritsu_placement_service import JiritsuRequirement as BaseJiritsuRequirement
from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...value_objects.assignment import Assignment
from ....infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from ....infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfig


@dataclass
class JiritsuRequirement(BaseJiritsuRequirement):
    """自立活動の要件（実装用拡張版）"""
    hours_needed: int
    jiritsu_teacher: Teacher
    placed_slots: List[TimeSlot]
    
    def __init__(self, exchange_class, parent_class, hours_needed, jiritsu_teacher, placed_slots):
        # 基底クラスの初期化
        super().__init__(
            exchange_class=exchange_class,
            parent_class=parent_class,
            periods_per_week=hours_needed,
            allowed_parent_subjects=["数", "英"]  # デフォルト値
        )
        self.hours_needed = hours_needed
        self.jiritsu_teacher = jiritsu_teacher
        self.placed_slots = placed_slots


class BacktrackJiritsuPlacementService(JiritsuPlacementService):
    """バックトラッキングによる自立活動配置サービス"""
    
    def __init__(self, config: AdvancedCSPConfig, constraint_validator):
        self.config = config
        self.constraint_validator = constraint_validator
        self.absence_loader = TeacherAbsenceLoader()
        self.logger = logging.getLogger(__name__)
    
    def analyze_requirements(self, school: School, schedule: Schedule) -> List[JiritsuRequirement]:
        """自立活動要件を分析"""
        requirements = []
        
        for exchange_class, parent_class in self.config.exchange_parent_mappings.items():
            jiritsu_hours = 0
            jiritsu_teacher = None
            
            # 自立活動系教科の時数を集計
            for subject in school.get_required_subjects(exchange_class):
                if subject.name in self.config.jiritsu_subjects:
                    hours = school.get_standard_hours(exchange_class, subject)
                    jiritsu_hours += int(round(hours))
                    if not jiritsu_teacher:
                        jiritsu_teacher = school.get_assigned_teacher(subject, exchange_class)
            
            if jiritsu_hours > 0 and jiritsu_teacher:
                # 既配置のスロットを確認
                placed_slots = [
                    slot for slot, assignment in schedule.get_all_assignments()
                    if assignment.class_ref == exchange_class and assignment.subject.name == "自立"
                ]
                
                requirements.append(JiritsuRequirement(
                    exchange_class=exchange_class,
                    parent_class=parent_class,
                    hours_needed=jiritsu_hours,
                    jiritsu_teacher=jiritsu_teacher,
                    placed_slots=placed_slots
                ))
                
                self.logger.debug(
                    f"{exchange_class}: {jiritsu_hours}時間の自立活動が必要"
                    f"（{len(placed_slots)}時間配置済み）"
                )
        
        return requirements
    
    def place_activities(self, schedule: Schedule, school: School, 
                        requirements: List[JiritsuRequirement]) -> int:
        """自立活動を配置"""
        self.logger.info("自立活動の配置を開始")
        total_placed = 0
        
        for req in requirements:
            remaining_hours = req.hours_needed - len(req.placed_slots)
            if remaining_hours <= 0:
                continue
            
            # 配置可能なスロットを探索
            feasible_slots = self.find_feasible_slots(schedule, school, req)
            
            if len(feasible_slots) < remaining_hours:
                self.logger.warning(
                    f"{req.exchange_class}: 配置可能なスロットが不足 "
                    f"({len(feasible_slots)}/{remaining_hours})"
                )
            
            # バックトラッキングで配置
            placed = self._backtrack_placement(
                schedule, school, req, feasible_slots, remaining_hours
            )
            
            total_placed += placed
            
            if placed < remaining_hours:
                self.logger.warning(
                    f"{req.exchange_class}: {placed}/{remaining_hours}時間のみ配置"
                )
        
        return total_placed
    
    def find_feasible_slots(self, schedule: Schedule, school: School,
                           requirement: JiritsuRequirement) -> List[Tuple[TimeSlot, Subject, Teacher]]:
        """配置可能なスロットを探索"""
        feasible_slots = []
        days_with_jiritsu = {slot.day for slot in requirement.placed_slots}
        
        for day in self.config.weekdays:
            # 1日1コマまでの制限
            if day in days_with_jiritsu:
                continue
            
            for period in range(self.config.periods_min, self.config.periods_max + 1):
                slot = TimeSlot(day, period)
                
                # 固定制約をチェック
                if day == "月" and period == self.config.periods_max:  # 月曜6限は欠
                    continue
                if day in self.config.yt_days and period == self.config.yt_days[day]:  # YT固定
                    continue
                
                # 既存の割り当てをチェック
                exchange_assignment = schedule.get_assignment(slot, requirement.exchange_class)
                parent_assignment = schedule.get_assignment(slot, requirement.parent_class)
                
                # 固定科目が配置されている場合はスキップ
                if exchange_assignment or parent_assignment:
                    continue
                
                # 固定科目保護チェック（ロックされている場合もスキップ）
                if (schedule.is_locked(slot, requirement.exchange_class) or 
                    schedule.is_locked(slot, requirement.parent_class)):
                    continue
                
                # 教員の利用可能性
                if not self._is_teacher_available(requirement.jiritsu_teacher, slot, schedule, school):
                    continue
                
                # 親学級で数学または英語を配置できるか
                for subject_name in self.config.parent_subjects_for_jiritsu:
                    subject = Subject(subject_name)
                    teacher = school.get_assigned_teacher(subject, requirement.parent_class)
                    
                    if teacher and self._can_place_subject(
                        schedule, school, requirement.parent_class, slot, subject, teacher
                    ):
                        feasible_slots.append((slot, subject, teacher))
                        break
        
        # スロットを評価順にソート
        feasible_slots.sort(key=lambda x: self._evaluate_jiritsu_slot(x[0], x[1]))
        
        return feasible_slots
    
    def _backtrack_placement(self, schedule: Schedule, school: School,
                            req: JiritsuRequirement, feasible_slots: List,
                            needed_hours: int) -> int:
        """バックトラッキングで自立活動を配置"""
        placed_count = 0
        used_days = {slot.day for slot in req.placed_slots}
        
        def backtrack(index: int, current_placed: int) -> bool:
            nonlocal placed_count
            
            if current_placed >= needed_hours:
                placed_count = current_placed
                return True
            
            if index >= len(feasible_slots):
                return False
            
            slot, parent_subject, parent_teacher = feasible_slots[index]
            
            # このスロットをスキップ
            if backtrack(index + 1, current_placed):
                return True
            
            # 1日1コマ制限チェック
            if slot.day in used_days:
                return backtrack(index + 1, current_placed)
            
            # 配置を試みる
            jiritsu_assignment = Assignment(req.exchange_class, Subject("自立"), req.jiritsu_teacher)
            parent_assignment = Assignment(req.parent_class, parent_subject, parent_teacher)
            
            # 配置前に固定科目保護チェック
            try:
                # 一時配置
                schedule.assign(slot, jiritsu_assignment)
                schedule.assign(slot, parent_assignment)
                used_days.add(slot.day)
            except ValueError as e:
                # 固定科目保護により配置できない場合
                self.logger.debug(f"固定科目保護により配置不可: {e}")
                return backtrack(index + 1, current_placed)
            
            # 制約チェック
            if (self.constraint_validator.check_assignment(schedule, school, slot, jiritsu_assignment) and
                self.constraint_validator.check_assignment(schedule, school, slot, parent_assignment)):
                
                if backtrack(index + 1, current_placed + 1):
                    self.logger.debug(
                        f"{slot}: {req.exchange_class}に自立、"
                        f"{req.parent_class}に{parent_subject.name}を配置"
                    )
                    return True
            
            # 配置を取り消し
            schedule.remove_assignment(slot, req.exchange_class)
            schedule.remove_assignment(slot, req.parent_class)
            used_days.remove(slot.day)
            
            return backtrack(index + 1, current_placed)
        
        backtrack(0, 0)
        return placed_count
    
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
    
    def _can_place_subject(self, schedule: Schedule, school: School,
                          class_ref: ClassReference, slot: TimeSlot,
                          subject: Subject, teacher: Teacher) -> bool:
        """教科を配置可能かチェック"""
        if not self._is_teacher_available(teacher, slot, schedule, school):
            return False
        
        # 日内重複チェック
        daily_count = sum(
            1 for period in range(1, 7)
            for s, a in schedule.get_all_assignments()
            if (s.day == slot.day and s.period == period and 
                a.class_ref == class_ref and a.subject == subject)
        )
        if daily_count > 0:
            return False
        
        # 制約チェック
        temp_assignment = Assignment(class_ref, subject, teacher)
        return self.constraint_validator.check_assignment(schedule, school, slot, temp_assignment)
    
    def _evaluate_jiritsu_slot(self, slot: TimeSlot, parent_subject: Subject) -> float:
        """自立活動スロットの評価（低いほど良い）"""
        score = 0.0
        
        # 中間の曜日を優先
        if slot.day in ["火", "水", "木"]:
            score -= 10
        
        # 午前中を優先
        if slot.period <= 3:
            score -= 5
        
        # 数学を英語より優先
        if parent_subject.name == "数":
            score -= 3
        
        return score
    
    def can_place_jiritsu(self, schedule: Schedule, school: School,
                         time_slot: TimeSlot, requirement: JiritsuRequirement) -> bool:
        """特定の時間枠に自立活動を配置可能かチェック"""
        # 既存の割り当てをチェック
        exchange_assignment = schedule.get_assignment(time_slot, requirement.exchange_class)
        parent_assignment = schedule.get_assignment(time_slot, requirement.parent_class)
        
        # 既に割り当てがある場合は配置不可
        if exchange_assignment or parent_assignment:
            return False
        
        # ロックされている場合は配置不可
        if (schedule.is_locked(time_slot, requirement.exchange_class) or 
            schedule.is_locked(time_slot, requirement.parent_class)):
            return False
        
        # 固定制約をチェック
        if time_slot.day == "月" and time_slot.period == 6:  # 月曜6限は欠
            return False
        
        # 教員の利用可能性をチェック（JiritsuRequirementにjiritsu_teacher属性がある場合）
        if hasattr(requirement, 'jiritsu_teacher'):
            if not self._is_teacher_available(requirement.jiritsu_teacher, time_slot, schedule, school):
                return False
        
        # 親学級で適切な教科を配置できるかチェック
        for subject_name in requirement.allowed_parent_subjects:
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, requirement.parent_class)
            
            if teacher and self._can_place_subject(
                schedule, school, requirement.parent_class, time_slot, subject, teacher
            ):
                return True
        
        return False