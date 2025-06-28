"""人間の時間割担当者のアプローチを模倣したスケジューラー

人間が時間割を作成する際の思考プロセスを再現：
1. 全体のバランスを見ながら配置
2. 日内重複を避けつつ、必要なら後で調整
3. 空白を最小限に抑える
4. 教員の都合を柔軟に調整
"""

import logging
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import random
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...value_objects.assignment import Assignment
from ...constraints.base import ConstraintValidator


class HumanLikeScheduler(LoggingMixin):
    """人間の時間割担当者のアプローチを模倣したスケジューラー"""
    
    def __init__(self, constraint_validator: ConstraintValidator):
        self.constraint_validator = constraint_validator
        super().__init__()
    
    def optimize_schedule(self, schedule: Schedule, school: School, 
                         force_fill_all: bool = True) -> Schedule:
        """スケジュールを人間的なアプローチで最適化"""
        self.logger.info("=== 人間的アプローチによるスケジュール最適化を開始 ===")
        
        # Step 1: 現状分析
        stats = self._analyze_schedule(schedule, school)
        self._log_statistics(stats)
        
        # Step 2: 日内重複の解消（固定教科も含めて分析）
        self._fix_all_daily_duplicates(schedule, school)
        
        # Step 3: 空白を埋める（積極的なアプローチ）
        if force_fill_all:
            self._aggressively_fill_empty_slots(schedule, school)
        
        # Step 4: 教科バランスの調整
        self._balance_subject_distribution(schedule, school)
        
        # Step 5: 最終的な日内重複チェックと修正
        self._final_duplicate_check(schedule, school)
        
        # Step 6: 最終統計
        final_stats = self._analyze_schedule(schedule, school)
        self._log_statistics(final_stats, "最終")
        
        return schedule
    
    def _analyze_schedule(self, schedule: Schedule, school: School) -> Dict:
        """スケジュールの現状を分析"""
        stats = {
            'total_slots': 0,
            'filled_slots': 0,
            'empty_slots': 0,
            'daily_duplicates': [],
            'subject_hours': defaultdict(lambda: defaultdict(int)),
            'teacher_load': defaultdict(int)
        }
        
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                daily_subjects = defaultdict(int)
                
                for period in range(1, 7):
                    stats['total_slots'] += 1
                    slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(slot, class_ref)
                    
                    if assignment:
                        stats['filled_slots'] += 1
                        subject_name = assignment.subject.name
                        stats['subject_hours'][class_ref][subject_name] += 1
                        stats['teacher_load'][assignment.teacher.name] += 1
                        
                        # 日内重複チェック（固定教科も含む）
                        daily_subjects[subject_name] += 1
                    else:
                        stats['empty_slots'] += 1
                
                # 日内重複を記録
                for subject_name, count in daily_subjects.items():
                    if count > 1:
                        stats['daily_duplicates'].append((class_ref, day, subject_name, count))
        
        return stats
    
    def _log_statistics(self, stats: Dict, prefix: str = "現在") -> None:
        """統計情報をログ出力"""
        self.logger.info(f"=== {prefix}のスケジュール統計 ===")
        self.logger.info(f"総スロット数: {stats['total_slots']}")
        self.logger.info(f"埋まっているスロット: {stats['filled_slots']} ({stats['filled_slots']/stats['total_slots']*100:.1f}%)")
        self.logger.info(f"空きスロット: {stats['empty_slots']} ({stats['empty_slots']/stats['total_slots']*100:.1f}%)")
        self.logger.info(f"日内重複: {len(stats['daily_duplicates'])}件")
        
        if stats['daily_duplicates']:
            self.logger.warning("日内重複の詳細:")
            for class_ref, day, subject, count in stats['daily_duplicates'][:10]:  # 最初の10件のみ
                self.logger.warning(f"  {class_ref} {day}曜: {subject} が {count}回")
    
    def _fix_all_daily_duplicates(self, schedule: Schedule, school: School) -> None:
        """全ての日内重複を解消（固定教科も考慮）"""
        self.logger.info("=== 日内重複の解消を開始 ===")
        
        fixed_count = 0
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                # その日の教科をカウント
                subject_slots = defaultdict(list)
                for period in range(1, 7):
                    slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(slot, class_ref)
                    if assignment:
                        subject_slots[assignment.subject.name].append((slot, assignment))
                
                # 重複を修正（2回以上は完全禁止）
                for subject_name, slot_assignments in subject_slots.items():
                    if len(slot_assignments) > 1:
                        # 固定教科の場合は警告のみ
                        if subject_name in ["道徳", "道", "学活", "学", "学総", "YT", "欠", "総合", "総", "行事", "行"]:
                            self.logger.warning(f"{class_ref} {day}曜: 固定教科 {subject_name} が {len(slot_assignments)}回出現")
                            continue
                        
                        # 通常教科の重複を必ず修正
                        self.logger.warning(f"日内重複検出: {class_ref} {day}曜 {subject_name} が {len(slot_assignments)}回")
                        if self._fix_single_daily_duplicate(schedule, school, class_ref, day, 
                                                          subject_name, slot_assignments):
                            fixed_count += 1
                        else:
                            self.logger.error(f"日内重複修正失敗: {class_ref} {day}曜 {subject_name}")
        
        self.logger.info(f"=== 日内重複修正完了: {fixed_count}件を修正 ===")
    
    def _fix_single_daily_duplicate(self, schedule: Schedule, school: School,
                                   class_ref: ClassReference, day: str,
                                   subject_name: str, slot_assignments: List[Tuple]) -> bool:
        """単一の日内重複を修正（完全禁止）"""
        # 2回以上は必ず修正
        if len(slot_assignments) >= 2:
            self.logger.warning(
                f"日内重複違反: {class_ref} {day}曜日 {subject_name} が {len(slot_assignments)}回"
            )
        
        # ロックされていないスロットを対象に
        unlocked_assignments = [(slot, assign) for slot, assign in slot_assignments 
                               if not schedule.is_locked(slot, class_ref)]
        
        if len(unlocked_assignments) == 0:
            return False
        
        # 最大1回のみ許可（2回目以降は必ず移動）
        max_allowed = 1
        
        # 最初の1個を残して、残りを別の日に移動または入れ替え
        for i in range(1, len(unlocked_assignments)):
            slot, assignment = unlocked_assignments[i]
            
            # 別の日の空きスロットを探す
            moved = False
            for alt_day in ["月", "火", "水", "木", "金"]:
                if alt_day == day:
                    continue
                
                for alt_period in range(1, 7):
                    alt_slot = TimeSlot(alt_day, alt_period)
                    
                    # 空きスロットかチェック
                    if schedule.get_assignment(alt_slot, class_ref):
                        continue
                    
                    # ロックされていないかチェック
                    if schedule.is_locked(alt_slot, class_ref):
                        continue
                    
                    # 教員が利用可能かチェック
                    if not schedule.is_teacher_available(alt_slot, assignment.teacher):
                        continue
                    
                    # 日内重複にならないかチェック
                    if self._would_create_daily_duplicate(schedule, class_ref, alt_slot, assignment.subject):
                        continue
                    
                    # 移動実行
                    schedule.remove_assignment(slot, class_ref)
                    schedule.assign(alt_slot, assignment)
                    self.logger.debug(f"{class_ref}: {subject_name} を {slot} → {alt_slot} に移動")
                    moved = True
                    break
                
                if moved:
                    break
            
            if not moved:
                # 入れ替えを試みる
                if self._try_swap_to_fix_duplicate(schedule, school, class_ref, slot, assignment):
                    moved = True
            
            if not moved:
                # 最終手段：削除
                schedule.remove_assignment(slot, class_ref)
                self.logger.warning(f"{class_ref} {slot}: {subject_name} を削除（移動先なし）")
        
        return True
    
    def _try_swap_to_fix_duplicate(self, schedule: Schedule, school: School,
                                  class_ref: ClassReference, source_slot: TimeSlot,
                                  source_assignment: Assignment) -> bool:
        """授業を入れ替えて日内重複を解消"""
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                target_slot = TimeSlot(day, period)
                target_assignment = schedule.get_assignment(target_slot, class_ref)
                
                if not target_assignment:
                    continue
                
                # ロックされているスロットはスキップ
                if schedule.is_locked(target_slot, class_ref):
                    continue
                
                # 同じ教科なら意味がない
                if target_assignment.subject == source_assignment.subject:
                    continue
                
                # 入れ替えて日内重複が解消されるかチェック
                if (not self._would_create_daily_duplicate(schedule, class_ref, source_slot, target_assignment.subject) and
                    not self._would_create_daily_duplicate(schedule, class_ref, target_slot, source_assignment.subject)):
                    
                    # 教員の利用可能性をチェック
                    if (schedule.is_teacher_available(source_slot, target_assignment.teacher) and
                        schedule.is_teacher_available(target_slot, source_assignment.teacher)):
                        
                        # 入れ替え実行
                        schedule.remove_assignment(source_slot, class_ref)
                        schedule.remove_assignment(target_slot, class_ref)
                        schedule.assign(source_slot, target_assignment)
                        schedule.assign(target_slot, source_assignment)
                        self.logger.debug(f"{class_ref}: {source_slot} と {target_slot} を入れ替え")
                        return True
        
        return False
    
    def _would_create_daily_duplicate(self, schedule: Schedule, class_ref: ClassReference,
                                    slot: TimeSlot, subject: Subject) -> bool:
        """日内重複が発生するかチェック"""
        for period in range(1, 7):
            if period == slot.period:
                continue
            
            other_slot = TimeSlot(slot.day, period)
            assignment = schedule.get_assignment(other_slot, class_ref)
            
            if assignment and assignment.subject == subject:
                return True
        
        return False
    
    def _aggressively_fill_empty_slots(self, schedule: Schedule, school: School) -> None:
        """積極的に空白を埋める（人間的アプローチ）"""
        self.logger.info("=== 積極的な空白埋めを開始 ===")
        
        # 教師不在を尊重する設定の場合はスキップ
        if getattr(self, 'respect_teacher_absence', True):
            self.logger.info("教師不在を尊重するため、積極的な空白埋めはスキップします")
            return
        
        filled_count = 0
        
        # 各クラスの空きスロットを処理
        for class_ref in school.get_all_classes():
            # 現在の教科別時数をカウント
            subject_hours = defaultdict(int)
            empty_slots = []
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(slot, class_ref)
                    
                    if assignment:
                        subject_hours[assignment.subject.name] += 1
                    elif not schedule.is_locked(slot, class_ref):
                        empty_slots.append(slot)
            
            if not empty_slots:
                continue
            
            # 不足している教科を優先順位付き（標準時数の多い順）で取得
            needed_subjects = self._get_needed_subjects_prioritized(
                school, class_ref, subject_hours)
            
            # 空きスロットを埋める
            for slot in empty_slots:
                filled = False
                
                # 優先順位の高い教科から試す
                for subject, standard_hours in needed_subjects:
                    if subject_hours.get(subject.name, 0) >= standard_hours:
                        continue
                    
                    # 教員を探す（複数の候補から）
                    teachers = self._find_available_teachers(schedule, school, slot, class_ref, subject)
                    
                    for teacher in teachers:
                        # 日内重複チェック
                        if self._would_create_daily_duplicate(schedule, class_ref, slot, subject):
                            continue
                        
                        # 配置
                        # セル別配置禁止制約のチェック
                        forbidden = False
                        from ...constraints.cell_forbidden_subject_constraint import CellForbiddenSubjectConstraint
                        for constraint in self.constraint_validator.constraints:
                            if isinstance(constraint, CellForbiddenSubjectConstraint):
                                forbidden_subjects = constraint.forbidden_cells.get((slot, class_ref), set())
                                if subject.name in forbidden_subjects:
                                    self.logger.debug(f"セル配置禁止: {class_ref}の{slot}に{subject.name}は配置不可")
                                    forbidden = True
                                    break
                        
                        if not forbidden:
                            assignment = Assignment(class_ref, subject, teacher)
                            schedule.assign(slot, assignment)
                            subject_hours[subject.name] += 1
                            filled_count += 1
                            filled = True
                            self.logger.debug(f"{class_ref} {slot}: {subject}({teacher}) を配置")
                            break
                    
                    if filled:
                        break
                
                # それでも埋まらない場合は、標準時数を超えても配置
                if not filled:
                    filled = self._fill_slot_exceeding_standard(
                        schedule, school, slot, class_ref, subject_hours)
                    if filled:
                        filled_count += 1
        
        self.logger.info(f"=== 積極的な空白埋め完了: {filled_count}個を埋めました ===")
    
    def _get_needed_subjects_prioritized(self, school: School, class_ref: ClassReference,
                                       current_hours: Dict[str, int]) -> List[Tuple[Subject, float]]:
        """必要な教科を優先順位付きで取得"""
        needed = []
        
        for subject in school.get_required_subjects(class_ref):
            standard = school.get_standard_hours(class_ref, subject)
            current = current_hours.get(subject.name, 0)
            
            # 固定教科はスキップ
            if subject.name in ["道徳", "道", "学活", "学", "学総", "YT", "欠", "総合", "総", "行事", "行"]:
                continue
            
            if current < standard:
                needed.append((subject, standard))
        
        # 標準時数の多い順にソート（週4以上を優先）
        needed.sort(key=lambda x: x[1], reverse=True)
        return needed
    
    def _find_available_teachers(self, schedule: Schedule, school: School,
                                slot: TimeSlot, class_ref: ClassReference,
                                subject: Subject) -> List[Teacher]:
        """利用可能な教員を探す（複数の候補）"""
        teachers = []
        
        # 通常の担当教員
        primary_teacher = school.get_assigned_teacher(subject, class_ref)
        if (primary_teacher and 
            schedule.is_teacher_available(slot, primary_teacher) and
            not school.is_teacher_unavailable(slot.day, slot.period, primary_teacher)):
            teachers.append(primary_teacher)
        
        # 代替教員を探す
        all_subject_teachers = school.get_subject_teachers(subject)
        for teacher in all_subject_teachers:
            if (teacher != primary_teacher and
                schedule.is_teacher_available(slot, teacher) and
                not school.is_teacher_unavailable(slot.day, slot.period, teacher)):
                teachers.append(teacher)
        
        return teachers
    
    def _fill_slot_exceeding_standard(self, schedule: Schedule, school: School,
                                     slot: TimeSlot, class_ref: ClassReference,
                                     subject_hours: Dict[str, int]) -> bool:
        """標準時数を超えても空白を埋める"""
        # 最も頻度の高い教科を配置
        subjects_by_frequency = sorted(
            [(Subject(name), hours) for name, hours in subject_hours.items()],
            key=lambda x: x[1], reverse=True
        )
        
        for subject, _ in subjects_by_frequency:
            # 固定教科はスキップ
            if subject.name in ["道徳", "道", "学活", "学", "学総", "YT", "欠", "総合", "総", "行事", "行"]:
                continue
            
            # 日内重複チェック
            if self._would_create_daily_duplicate(schedule, class_ref, slot, subject):
                continue
            
            # 教員を探す
            teachers = self._find_available_teachers(schedule, school, slot, class_ref, subject)
            
            for teacher in teachers:
                # セル別配置禁止制約のチェック
                forbidden = False
                from ...constraints.cell_forbidden_subject_constraint import CellForbiddenSubjectConstraint
                for constraint in self.constraint_validator.constraints:
                    if isinstance(constraint, CellForbiddenSubjectConstraint):
                        forbidden_subjects = constraint.forbidden_cells.get((slot, class_ref), set())
                        if subject.name in forbidden_subjects:
                            self.logger.debug(f"セル配置禁止: {class_ref}の{slot}に{subject.name}は配置不可（標準超過）")
                            forbidden = True
                            break
                
                if not forbidden:
                    assignment = Assignment(class_ref, subject, teacher)
                    schedule.assign(slot, assignment)
                    self.logger.debug(f"{class_ref} {slot}: {subject}({teacher}) を配置（標準超過）")
                    return True
        
        return False
    
    def _balance_subject_distribution(self, schedule: Schedule, school: School) -> None:
        """教科の配置バランスを調整"""
        self.logger.info("=== 教科配置バランスの調整を開始 ===")
        
        adjusted_count = 0
        
        for class_ref in school.get_all_classes():
            # 各曜日の教科分布を分析
            daily_subjects = defaultdict(list)
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(slot, class_ref)
                    if assignment:
                        daily_subjects[day].append((slot, assignment))
            
            # 同じ教科が連続している場合は分散
            for day, assignments in daily_subjects.items():
                consecutive_same = []
                
                for i in range(len(assignments) - 1):
                    slot1, assign1 = assignments[i]
                    slot2, assign2 = assignments[i + 1]
                    
                    if (assign1.subject == assign2.subject and 
                        abs(slot1.period - slot2.period) == 1 and
                        not schedule.is_locked(slot1, class_ref) and
                        not schedule.is_locked(slot2, class_ref)):
                        consecutive_same.append((slot1, assign1, slot2, assign2))
                
                # 連続を解消
                for slot1, assign1, slot2, assign2 in consecutive_same:
                    if self._try_distribute_consecutive(schedule, school, class_ref, 
                                                      slot1, assign1, slot2, assign2):
                        adjusted_count += 1
        
        self.logger.info(f"=== 教科配置バランス調整完了: {adjusted_count}件を調整 ===")
    
    def _try_distribute_consecutive(self, schedule: Schedule, school: School,
                                  class_ref: ClassReference,
                                  slot1: TimeSlot, assign1: Assignment,
                                  slot2: TimeSlot, assign2: Assignment) -> bool:
        """連続する同じ教科を分散"""
        # 他の時間と入れ替え
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                target_slot = TimeSlot(day, period)
                
                # 同じ日の隣接時間は避ける
                if (target_slot.day == slot1.day and 
                    abs(target_slot.period - slot1.period) <= 1):
                    continue
                
                target_assignment = schedule.get_assignment(target_slot, class_ref)
                if not target_assignment:
                    continue
                
                # ロックされているスロットはスキップ
                if schedule.is_locked(target_slot, class_ref):
                    continue
                
                # 異なる教科で、入れ替えても問題ない場合
                if (target_assignment.subject != assign1.subject and
                    not self._would_create_daily_duplicate(schedule, class_ref, slot2, target_assignment.subject) and
                    not self._would_create_daily_duplicate(schedule, class_ref, target_slot, assign2.subject)):
                    
                    # 教員の利用可能性をチェック
                    if (schedule.is_teacher_available(slot2, target_assignment.teacher) and
                        schedule.is_teacher_available(target_slot, assign2.teacher)):
                        
                        # 入れ替え実行
                        schedule.remove_assignment(slot2, class_ref)
                        schedule.remove_assignment(target_slot, class_ref)
                        schedule.assign(slot2, target_assignment)
                        schedule.assign(target_slot, assign2)
                        self.logger.debug(f"{class_ref}: 連続する{assign1.subject}を分散（{slot2} ↔ {target_slot}）")
                        return True
        
        return False
    
    def _final_duplicate_check(self, schedule: Schedule, school: School) -> None:
        """最終的な日内重複チェックと修正"""
        self.logger.info("=== 最終的な日内重複チェック ===")
        
        remaining_duplicates = []
        
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subject_count = defaultdict(int)
                
                for period in range(1, 7):
                    slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(slot, class_ref)
                    if assignment:
                        subject_count[assignment.subject.name] += 1
                
                for subject_name, count in subject_count.items():
                    if count > 1:
                        remaining_duplicates.append((class_ref, day, subject_name, count))
        
        if remaining_duplicates:
            self.logger.warning(f"最終チェック: {len(remaining_duplicates)}件の日内重複が残存")
            for class_ref, day, subject, count in remaining_duplicates[:5]:
                self.logger.warning(f"  {class_ref} {day}曜: {subject} が {count}回")
        else:
            self.logger.info("最終チェック: 日内重複なし ✓")