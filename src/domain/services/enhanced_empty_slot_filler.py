"""空きコマを積極的に埋める改良版サービス"""
import logging
from typing import List, Set, Tuple, Optional, Dict
import random

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment
from ..constraints.base import ConstraintPriority
from .unified_constraint_system import UnifiedConstraintSystem


class EnhancedEmptySlotFiller:
    """空きコマを積極的に埋めるサービス"""
    
    def __init__(self, constraint_system: UnifiedConstraintSystem, absence_loader=None):
        self.constraint_system = constraint_system
        self.logger = logging.getLogger(__name__)
        self.absence_loader = absence_loader
        self._teacher_cache = {}  # 教師の可用性キャッシュ
        self._forbidden_cells = self._extract_forbidden_cells()  # 非○○制約を抽出
    
    def fill_empty_slots_multi_pass(self, schedule: Schedule, school: School, max_passes: int = 5) -> int:
        """複数パスで空きコマを埋める"""
        total_filled = 0
        
        for pass_num in range(1, max_passes + 1):
            self.logger.info(f"\n=== 空きコマ埋め第{pass_num}パス開始 ===")
            filled = self.fill_empty_slots(schedule, school, pass_num)
            total_filled += filled
            
            if filled == 0:
                self.logger.info(f"第{pass_num}パスで埋められるコマがなくなりました")
                break
            
            self.logger.info(f"第{pass_num}パスで{filled}コマを埋めました")
        
        return total_filled
    
    def fill_empty_slots(self, schedule: Schedule, school: School, pass_num: int = 1) -> int:
        """空きコマを埋める"""
        filled_count = 0
        empty_slots = self._find_empty_slots(schedule, school)
        
        self.logger.info(f"空きコマ数: {len(empty_slots)}")
        
        # パスごとに戦略を変える（より積極的に埋めるため）
        if pass_num == 1:
            # 第1パス：不足科目を優先的に埋める
            strategy = "shortage_based"
        elif pass_num == 2:
            # 第2パス：バランスを考慮して埋める
            strategy = "balanced"
        elif pass_num == 3:
            # 第3パス：より緩い制約で埋める
            strategy = "relaxed"
        else:
            # 第4パス以降：最大限緩い制約（ultra_relaxed）
            strategy = "ultra_relaxed"
        
        for time_slot, class_ref in empty_slots:
            if self._fill_empty_slot(schedule, school, time_slot, class_ref, strategy):
                filled_count += 1
        
        return filled_count
    
    def _find_empty_slots(self, schedule: Schedule, school: School) -> List[Tuple[TimeSlot, ClassReference]]:
        """空きコマを見つける"""
        empty_slots = []
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):  # 1〜6時限
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 特別な空きコマはスキップ
                    if self._should_skip_slot(time_slot, class_ref):
                        continue
                    
                    # 既に割り当てがある場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    empty_slots.append((time_slot, class_ref))
        
        # ランダムな順序で処理
        random.shuffle(empty_slots)
        return empty_slots
    
    def _should_skip_slot(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """このスロットをスキップすべきか判定"""
        # 月曜6時限は「欠」なのでスキップ
        if time_slot.day == "月" and time_slot.period == 6:
            return True
        
        # 火水金の6時限は「YT」なのでスキップ
        if time_slot.day in ["火", "水", "金"] and time_slot.period == 6:
            return True
        
        return False
    
    def _fill_empty_slot(self, schedule: Schedule, school: School, 
                        time_slot: TimeSlot, class_ref: ClassReference, 
                        strategy: str) -> bool:
        """空きコマを埋める"""
        # 不足科目を取得
        shortage_subjects = self._get_shortage_subjects(schedule, school, class_ref)
        
        # 禁止教科を除外
        forbidden_key = (time_slot, class_ref)
        forbidden_subjects = self._forbidden_cells.get(forbidden_key, set())
        if forbidden_subjects:
            self.logger.debug(f"{class_ref}の{time_slot}で禁止教科: {forbidden_subjects}")
            # 禁止教科を除外
            shortage_subjects = {s: count for s, count in shortage_subjects.items() 
                               if s.name not in forbidden_subjects}
        
        # 主要5教科（国語・数学・理科・社会・英語）を定義
        core_subjects = ["国", "数", "理", "社", "英"]
        
        if strategy == "shortage_based":
            # 主要5教科を最優先し、その中で不足が大きい科目を優先
            core_candidates = [(s, c) for s, c in shortage_subjects.items() if s.name in core_subjects]
            other_candidates = [(s, c) for s, c in shortage_subjects.items() if s.name not in core_subjects]
            
            # 主要5教科を不足数で降順ソート
            core_candidates.sort(key=lambda x: x[1], reverse=True)
            # その他の教科も不足数で降順ソート
            other_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # 主要5教科を先に、その後その他の教科
            candidates = core_candidates + other_candidates
            
        elif strategy == "balanced":
            # バランスを考慮しつつ主要5教科を優先
            core_candidates = [(s, c) for s, c in shortage_subjects.items() if s.name in core_subjects and c > 0]
            other_candidates = [(s, c) for s, c in shortage_subjects.items() if s.name not in core_subjects and c > 0]
            
            random.shuffle(core_candidates)
            random.shuffle(other_candidates)
            
            # 主要5教科を先に
            candidates = core_candidates + other_candidates
            
        elif strategy in ["relaxed", "very_relaxed", "ultra_relaxed"]:
            # すべての科目を候補に（不足がなくても）
            all_subjects = set(school.subjects.values())
            # 固定教科と禁止教科を除外
            valid_subjects = [(subj, shortage_subjects.get(subj, 0)) for subj in all_subjects 
                         if subj.name not in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
                         and subj.name not in forbidden_subjects]
            
            # 主要5教科とその他に分類
            core_candidates = [(s, c) for s, c in valid_subjects if s.name in core_subjects]
            other_candidates = [(s, c) for s, c in valid_subjects if s.name not in core_subjects]
            
            # それぞれ不足数でソート
            core_candidates.sort(key=lambda x: x[1], reverse=True)
            other_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # 主要5教科を優先
            candidates = core_candidates + other_candidates
        else:
            # その他の戦略でも主要5教科を優先
            core_candidates = [(s, c) for s, c in shortage_subjects.items() if s.name in core_subjects and c > 0]
            other_candidates = [(s, c) for s, c in shortage_subjects.items() if s.name not in core_subjects and c > 0]
            
            random.shuffle(core_candidates)
            random.shuffle(other_candidates)
            
            candidates = core_candidates + other_candidates
        
        # 各科目を試す
        for subject, _ in candidates:
            # 利用可能な教員を探す
            available_teachers = self._find_available_teachers(
                schedule, school, time_slot, class_ref, subject, strategy
            )
            
            for teacher in available_teachers:
                # 割り当てを試みる
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=subject,
                    teacher=teacher
                )
                
                # 制約チェック（strategyに応じて緩める）
                if self._check_constraints(schedule, school, time_slot, class_ref, assignment, strategy):
                    # 割り当て実行
                    schedule.assign(time_slot, assignment)
                    self.logger.debug(f"{time_slot}, {class_ref}: {subject.name} ({teacher.name}) を割り当て")
                    return True
        
        return False
    
    def _get_shortage_subjects(self, schedule: Schedule, school: School, 
                              class_ref: ClassReference) -> dict:
        """不足科目とその不足数を取得"""
        # 基本時数を取得
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 現在の割り当て数をカウント
        current_hours = {}
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    subject = assignment.subject
                    current_hours[subject] = current_hours.get(subject, 0) + 1
        
        # 不足数を計算
        shortage = {}
        for subject, required in base_hours.items():
            current = current_hours.get(subject, 0)
            if current < required:
                shortage[subject] = required - current
        
        return shortage
    
    def _count_teacher_assignments(self, schedule: Schedule, teacher: Teacher) -> int:
        """教師の現在の授業数をカウント"""
        count = 0
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_teacher_at_time(time_slot, teacher)
                if assignments:
                    count += 1
        return count
    
    def _find_available_teachers(self, schedule: Schedule, school: School,
                                time_slot: TimeSlot, class_ref: ClassReference,
                                subject: Subject, strategy: str) -> List[Teacher]:
        """利用可能な教員を探す"""
        # キャッシュキーを作成
        cache_key = (time_slot.day, time_slot.period, subject.name, strategy)
        if cache_key in self._teacher_cache:
            return self._teacher_cache[cache_key]
        
        teachers = []
        
        # この科目を教えられる教員を取得
        subject_teachers = school.get_subject_teachers(subject)
        
        for teacher in subject_teachers:
            # 教員が不在でないかチェック（TeacherAbsenceLoaderを使用）
            if self.absence_loader and self.absence_loader.is_teacher_absent(teacher.name, time_slot.day, time_slot.period):
                self.logger.debug(f"{teacher.name}先生は{time_slot.day}曜{time_slot.period}限に不在")
                continue
            
            # 恒久的な不在もチェック
            if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
                continue
            
            # 既に他のクラスを教えていないかチェック（relaxedモードでは緩める）
            if strategy != "relaxed":
                other_assignments = schedule.get_teacher_at_time(time_slot, teacher)
                if other_assignments:
                    continue
            
            teachers.append(teacher)
        
        # 不足が大きい科目を教える教師を優先
        if teachers and strategy == "shortage_based":
            # 各教師の現在の授業数をカウント
            teacher_loads = {}
            for t in teachers:
                load = self._count_teacher_assignments(schedule, t)
                teacher_loads[t] = load
            
            # 授業数が少ない教師を優先
            teachers.sort(key=lambda t: teacher_loads[t])
        else:
            # ランダムな順序で返す
            random.shuffle(teachers)
        
        # キャッシュに保存
        self._teacher_cache[cache_key] = teachers
        return teachers
    
    def _check_constraints(self, schedule: Schedule, school: School,
                          time_slot: TimeSlot, class_ref: ClassReference,
                          assignment: Assignment, strategy: str) -> bool:
        """制約をチェック"""
        # 最も制限的な制約から先にチェック（早期リターンのため）
        
        # 1. 教師不在チェック（最優先）
        if self.absence_loader and self.absence_loader.is_teacher_absent(
                assignment.teacher.name, time_slot.day, time_slot.period):
            return False
        
        # 2. 教師重複チェック
        other_assignments = schedule.get_teacher_at_time(time_slot, assignment.teacher)
        if other_assignments:
            return False
        
        # 3. 体育館使用制約（体育の場合のみ）
        if assignment.subject.name == "保":
            pe_count = 0
            for other_class in school.get_all_classes():
                if other_class != class_ref:
                    other_assignment = schedule.get_assignment(time_slot, other_class)
                    if other_assignment and other_assignment.subject.name == "保":
                        pe_count += 1
            if pe_count >= 1:  # 既に1クラスが体育を行っている
                return False
        
        # 4. その他の制約チェック（戦略に応じて緩める）
        if strategy == "ultra_relaxed":
            # 最大限緩いモード：CRITICALのみ（体育館制約は既にチェック済み）
            priorities_to_check = [ConstraintPriority.CRITICAL]
        elif strategy == "very_relaxed":
            # かなり緩いモード：CRITICALとHIGHのみ
            priorities_to_check = [ConstraintPriority.CRITICAL, ConstraintPriority.HIGH]
        elif strategy == "relaxed":
            # 緩いモード：MEDIUMまで
            priorities_to_check = [ConstraintPriority.CRITICAL, ConstraintPriority.HIGH, ConstraintPriority.MEDIUM]
        else:
            # 通常モード：すべてチェック
            priorities_to_check = list(ConstraintPriority)
        
        # 優先度順にチェック
        for priority in priorities_to_check:
            constraints = self.constraint_system.constraints.get(priority, [])
            for constraint in constraints:
                if hasattr(constraint, 'check'):
                    if not constraint.check(schedule, school, time_slot, assignment):
                        return False
        
        return True
    
    def _extract_forbidden_cells(self) -> Dict:
        """制約システムから非○○制約情報を抽出"""
        forbidden_cells = {}
        
        # 各優先度の制約をチェック
        from ..constraints.cell_forbidden_subject_constraint import CellForbiddenSubjectConstraint
        from ..services.unified_constraint_system import ConstraintPriority
        
        for priority in ConstraintPriority:
            constraints = self.constraint_system.constraints.get(priority, [])
            for constraint in constraints:
                if isinstance(constraint, CellForbiddenSubjectConstraint):
                    # 禁止セル情報を取得
                    forbidden_cells = constraint.forbidden_cells
                    self.logger.info(f"非○○制約を{len(forbidden_cells)}個抽出しました")
                    return forbidden_cells
        
        return forbidden_cells