"""統合スケジュール修復サービス

個別の修正スクリプトを統合し、一貫性のあるスケジュール修復機能を提供します。
"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School, Subject, Teacher
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from .exchange_class_service import ExchangeClassService
from .constraint_validator import ConstraintValidator


class ScheduleRepairer(LoggingMixin):
    """統合スケジュール修復サービス
    
    主な機能:
    1. 交流学級同期違反の修正
    2. 日内重複の解消
    3. 教師不在違反の修正
    4. 体育館使用競合の解消
    5. 5組同期違反の修正
    """
    
    def __init__(self, school: School, absence_loader=None):
        """初期化
        
        Args:
            school: 学校情報
            absence_loader: 教師不在情報ローダー
        """
        super().__init__()
        self.school = school
        self.exchange_service = ExchangeClassService()
        self.constraint_validator = ConstraintValidator(absence_loader)
    
    def repair_all_violations(self, schedule: Schedule) -> Dict[str, int]:
        """全ての違反を修復
        
        Returns:
            修正結果の統計情報
        """
        self.logger.info("=== スケジュール修復開始 ===")
        
        results = {
            'exchange_sync_fixed': 0,
            'jiritsu_violations_fixed': 0,
            'daily_duplicates_fixed': 0,
            'teacher_absence_fixed': 0,
            'gym_conflicts_fixed': 0,
            'grade5_sync_fixed': 0,
            'total_fixed': 0
        }
        
        # 1. 交流学級同期違反を修正（最優先）
        fixed = self.fix_exchange_class_sync(schedule)
        results['exchange_sync_fixed'] = fixed
        results['total_fixed'] += fixed
        
        # 2. 自立活動制約違反を修正
        fixed = self.fix_jiritsu_violations(schedule)
        results['jiritsu_violations_fixed'] = fixed
        results['total_fixed'] += fixed
        
        # 3. 教師不在違反を修正
        fixed = self.fix_teacher_absence_violations(schedule)
        results['teacher_absence_fixed'] = fixed
        results['total_fixed'] += fixed
        
        # 4. 日内重複を修正
        fixed = self.fix_daily_duplicates(schedule)
        results['daily_duplicates_fixed'] = fixed
        results['total_fixed'] += fixed
        
        # 5. 体育館使用競合を修正
        fixed = self.fix_gym_conflicts(schedule)
        results['gym_conflicts_fixed'] = fixed
        results['total_fixed'] += fixed
        
        # 6. 5組同期違反を修正
        fixed = self.fix_grade5_sync(schedule)
        results['grade5_sync_fixed'] = fixed
        results['total_fixed'] += fixed
        
        self.logger.info(f"=== スケジュール修復完了: 計{results['total_fixed']}件修正 ===")
        return results
    
    def fix_exchange_class_sync(self, schedule: Schedule) -> int:
        """交流学級同期違反を修正"""
        fixed_count = 0
        violations = self.exchange_service.get_exchange_violations(schedule)
        
        # 同期違反のみを対象（自立活動制約は別途処理）
        sync_violations = [v for v in violations if v['type'] == 'sync_violation']
        
        for violation in sync_violations:
            exchange_class = violation['exchange_class']
            parent_class = violation['parent_class']
            time_slot = violation['time_slot']
            
            # ロックされている場合はスキップ
            if schedule.is_locked(time_slot, exchange_class):
                continue
            
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            if not parent_assignment:
                continue
            
            # 交流学級を親学級に同期
            if self.exchange_service.sync_exchange_with_parent(
                schedule, self.school, time_slot, parent_class, parent_assignment
            ):
                fixed_count += 1
                self.logger.info(f"交流学級同期修正: {exchange_class} {time_slot}")
        
        return fixed_count
    
    def fix_jiritsu_violations(self, schedule: Schedule) -> int:
        """自立活動制約違反を修正"""
        fixed_count = 0
        violations = self.exchange_service.get_exchange_violations(schedule)
        
        # 自立活動制約違反のみを対象
        jiritsu_violations = [v for v in violations if v['type'] == 'jiritsu_constraint']
        
        for violation in jiritsu_violations:
            exchange_class = violation['exchange_class']
            parent_class = violation['parent_class']
            time_slot = violation['time_slot']
            
            exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            
            if not exchange_assignment or not parent_assignment:
                continue
            
            # 交流学級が自立活動で、親学級が数/英でない場合
            if (self.exchange_service.is_jiritsu_activity(exchange_assignment.subject.name) and
                parent_assignment.subject.name not in self.exchange_service.ALLOWED_PARENT_SUBJECTS):
                
                # 親学級を数学または英語に変更を試みる
                if self._try_change_to_math_or_english(schedule, time_slot, parent_class):
                    fixed_count += 1
                    self.logger.info(f"自立活動制約修正: {parent_class} {time_slot}")
        
        return fixed_count
    
    def fix_teacher_absence_violations(self, schedule: Schedule) -> int:
        """教師不在違反を修正"""
        fixed_count = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in self.school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if not assignment:
                        continue
                    
                    # 教師が不在かチェック
                    if not self.constraint_validator.check_teacher_availability(
                        assignment.teacher, time_slot
                    ):
                        # 代替教師を探す
                        alt_teacher = self._find_alternative_teacher(
                            assignment.subject, class_ref, time_slot
                        )
                        
                        if alt_teacher:
                            # 教師を変更
                            new_assignment = Assignment(
                                class_ref, assignment.subject, alt_teacher
                            )
                            schedule.remove_assignment(time_slot, class_ref)
                            if schedule.assign(time_slot, new_assignment):
                                fixed_count += 1
                                self.logger.info(
                                    f"教師不在修正: {class_ref} {time_slot} "
                                    f"{assignment.teacher.name} → {alt_teacher.name}"
                                )
        
        return fixed_count
    
    def fix_daily_duplicates(self, schedule: Schedule) -> int:
        """日内重複を修正"""
        fixed_count = 0
        
        for class_ref in self.school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                # 各科目の出現回数をカウント
                subject_slots = defaultdict(list)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subject_slots[assignment.subject.name].append((time_slot, assignment))
                
                # 重複している科目を処理
                for subject_name, slots in subject_slots.items():
                    # 固定科目はスキップ
                    if self.exchange_service.is_fixed_subject(subject_name):
                        continue
                    
                    max_allowed = 1
                    if subject_name in {"算", "国", "理", "社", "英", "数"}:
                        max_allowed = 2
                    
                    if len(slots) > max_allowed:
                        # 超過分を他の科目に置換
                        excess_count = len(slots) - max_allowed
                        for i in range(excess_count):
                            time_slot, assignment = slots[-(i+1)]  # 後ろから処理
                            
                            # ロックされていない場合のみ
                            if not schedule.is_locked(time_slot, class_ref):
                                # 不足している科目を探す
                                replacement = self._find_replacement_subject(
                                    schedule, class_ref, time_slot, day
                                )
                                
                                if replacement:
                                    subject, teacher = replacement
                                    new_assignment = Assignment(class_ref, subject, teacher)
                                    schedule.remove_assignment(time_slot, class_ref)
                                    if schedule.assign(time_slot, new_assignment):
                                        fixed_count += 1
                                        self.logger.info(
                                            f"日内重複修正: {class_ref} {time_slot} "
                                            f"{subject_name} → {subject.name}"
                                        )
        
        return fixed_count
    
    def fix_gym_conflicts(self, schedule: Schedule) -> int:
        """体育館使用競合を修正"""
        fixed_count = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if self.constraint_validator.is_test_period(time_slot):
                    continue
                
                # 体育を行っているクラスを収集
                pe_classes = []
                for class_ref in self.school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append((class_ref, assignment))
                
                # 2クラス以上が体育の場合
                if len(pe_classes) > 1:
                    # 最初のクラスを残し、他を変更
                    for i in range(1, len(pe_classes)):
                        class_ref, assignment = pe_classes[i]
                        
                        if not schedule.is_locked(time_slot, class_ref):
                            # 他の科目に変更
                            replacement = self._find_non_pe_replacement(
                                schedule, class_ref, time_slot
                            )
                            
                            if replacement:
                                subject, teacher = replacement
                                new_assignment = Assignment(class_ref, subject, teacher)
                                schedule.remove_assignment(time_slot, class_ref)
                                if schedule.assign(time_slot, new_assignment):
                                    fixed_count += 1
                                    self.logger.info(
                                        f"体育館競合修正: {class_ref} {time_slot} "
                                        f"保 → {subject.name}"
                                    )
        
        return fixed_count
    
    def fix_grade5_sync(self, schedule: Schedule) -> int:
        """5組同期違反を修正"""
        fixed_count = 0
        grade5_classes = self.constraint_validator.grade5_classes
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各5組の割り当てを取得
                assignments = {}
                for class_ref in grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments[class_ref] = assignment
                
                if len(assignments) < 2:
                    continue
                
                # 最も多い科目を見つける
                subject_counts = defaultdict(list)
                for class_ref, assignment in assignments.items():
                    subject_counts[assignment.subject.name].append(class_ref)
                
                # 最多の科目を基準にする
                most_common_subject = max(subject_counts, key=lambda x: len(subject_counts[x]))
                
                # 異なる科目のクラスを修正
                for subject_name, classes in subject_counts.items():
                    if subject_name != most_common_subject:
                        for class_ref in classes:
                            if not schedule.is_locked(time_slot, class_ref):
                                # 最多科目の教師を取得
                                target_subject = Subject(most_common_subject)
                                teacher = self.school.get_assigned_teacher(target_subject, class_ref)
                                
                                if teacher:
                                    new_assignment = Assignment(class_ref, target_subject, teacher)
                                    schedule.remove_assignment(time_slot, class_ref)
                                    if schedule.assign(time_slot, new_assignment):
                                        fixed_count += 1
                                        self.logger.info(
                                            f"5組同期修正: {class_ref} {time_slot} "
                                            f"{subject_name} → {most_common_subject}"
                                        )
        
        return fixed_count
    
    def _try_change_to_math_or_english(
        self, 
        schedule: Schedule, 
        time_slot: TimeSlot, 
        parent_class: ClassReference
    ) -> bool:
        """親学級を数学または英語に変更を試みる"""
        # 数学と英語を試す
        for subject_name in ["数", "英", "算"]:
            subject = Subject(subject_name)
            teacher = self.school.get_assigned_teacher(subject, parent_class)
            
            if teacher:
                assignment = Assignment(parent_class, subject, teacher)
                
                # 制約チェック
                can_place, _ = self.constraint_validator.can_place_assignment(
                    schedule, self.school, time_slot, assignment, 'normal'
                )
                
                if can_place:
                    # 既存の割り当てを削除
                    schedule.remove_assignment(time_slot, parent_class)
                    
                    # 新しい割り当てを配置
                    if schedule.assign(time_slot, assignment):
                        return True
        
        return False
    
    def _find_alternative_teacher(
        self,
        subject: Subject,
        class_ref: ClassReference,
        time_slot: TimeSlot
    ) -> Optional[Teacher]:
        """代替教師を見つける"""
        # その科目を教えられる全教師を取得
        all_teachers = self.school.get_subject_teachers(subject)
        
        for teacher in all_teachers:
            # 利用可能かチェック
            if self.constraint_validator.check_teacher_availability(teacher, time_slot):
                # 重複していないかチェック
                assignment = Assignment(class_ref, subject, teacher)
                conflict = self.constraint_validator.check_teacher_conflict(
                    schedule, self.school, time_slot, assignment
                )
                if not conflict:
                    return teacher
        
        return None
    
    def _find_replacement_subject(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        day: str
    ) -> Optional[Tuple[Subject, Teacher]]:
        """置換用の科目と教師を見つける"""
        # 不足している科目を取得
        base_hours = self.school.get_all_standard_hours(class_ref)
        current_hours = defaultdict(int)
        
        # 現在の割り当てをカウント
        for d in ["月", "火", "水", "木", "金"]:
            for p in range(1, 7):
                ts = TimeSlot(d, p)
                assignment = schedule.get_assignment(ts, class_ref)
                if assignment:
                    current_hours[assignment.subject] += 1
        
        # 不足科目を優先度順に試す
        for subject, required in sorted(base_hours.items(), key=lambda x: x[1] - current_hours.get(x[0], 0), reverse=True):
            if current_hours.get(subject, 0) < required:
                # その日に既に配置されていないかチェック
                day_count = self.constraint_validator.get_daily_subject_count(
                    schedule, class_ref, day, subject
                )
                
                if day_count == 0:  # その日にまだない
                    teacher = self.school.get_assigned_teacher(subject, class_ref)
                    if teacher:
                        # 制約チェック
                        assignment = Assignment(class_ref, subject, teacher)
                        can_place, _ = self.constraint_validator.can_place_assignment(
                            schedule, self.school, time_slot, assignment, 'normal'
                        )
                        if can_place:
                            return subject, teacher
        
        return None
    
    def _find_non_pe_replacement(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        time_slot: TimeSlot
    ) -> Optional[Tuple[Subject, Teacher]]:
        """体育以外の科目を見つける"""
        replacement = self._find_replacement_subject(
            schedule, class_ref, time_slot, time_slot.day
        )
        
        # 体育以外であることを確認
        if replacement and replacement[0].name != "保":
            return replacement
        
        return None