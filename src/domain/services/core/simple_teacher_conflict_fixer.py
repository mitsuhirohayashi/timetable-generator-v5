#!/usr/bin/env python3
"""
シンプルな教師重複修正サービス

フェーズ2の簡略版：既存の時間割の教師重複を検出して修正します。
複雑な依存関係を避け、実用的な解決策を提供します。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School, Teacher, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment


class SimpleTeacherConflictFixer(LoggingMixin):
    """シンプルな教師重複修正サービス"""
    
    def __init__(self):
        super().__init__()
        
        # 5組クラス
        self.grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
        
        # テスト期間
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
        
        # 固定科目の教師（実際の教師ではない）
        self.fixed_teachers = {
            "欠", "欠課先生", "YT担当", "YT担当先生", 
            "道担当", "道担当先生", "学担当", "学担当先生", 
            "総担当", "総担当先生", "学総担当", "学総担当先生", 
            "行担当", "行担当先生", "技家担当", "技家担当先生"
        }
    
    def fix_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師重複を修正
        
        Returns:
            修正した重複の数
        """
        
        fixed_count = 0
        conflicts = self._detect_teacher_conflicts(schedule, school)
        
        self.logger.info(f"検出された教師重複: {len(conflicts)}件")
        
        for conflict in conflicts:
            if self._fix_single_conflict(schedule, school, conflict):
                fixed_count += 1
        
        self.logger.info(f"修正完了: {fixed_count}/{len(conflicts)}件")
        return fixed_count
    
    def _detect_teacher_conflicts(self, schedule: Schedule, school: School) -> List[Dict]:
        """教師重複を検出"""
        
        conflicts = []
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 教師ごとにクラスを収集
                teacher_assignments = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        
                        # 固定科目の教師は除外
                        if teacher_name in self.fixed_teachers:
                            continue
                        
                        teacher_assignments[teacher_name].append({
                            'class_ref': class_ref,
                            'assignment': assignment
                        })
                
                # 重複をチェック
                for teacher_name, assignments in teacher_assignments.items():
                    if len(assignments) > 1:
                        # 5組のみの場合は正常
                        all_grade5 = all(a['class_ref'] in self.grade5_refs for a in assignments)
                        
                        if not all_grade5:
                            conflicts.append({
                                'time_slot': time_slot,
                                'teacher': teacher_name,
                                'assignments': assignments
                            })
        
        return conflicts
    
    def _fix_single_conflict(self, schedule: Schedule, school: School, conflict: Dict) -> bool:
        """単一の教師重複を修正"""
        
        time_slot = conflict['time_slot']
        teacher_name = conflict['teacher']
        assignments = conflict['assignments']
        
        self.logger.debug(f"{time_slot}の{teacher_name}先生の重複を修正中...")
        
        # 5組を含む場合の特別処理
        grade5_assignments = [a for a in assignments if a['class_ref'] in self.grade5_refs]
        other_assignments = [a for a in assignments if a['class_ref'] not in self.grade5_refs]
        
        if grade5_assignments and other_assignments:
            # 5組と通常クラスの混在 - 通常クラスを移動
            for assignment_info in other_assignments:
                if self._move_assignment_to_empty_slot(
                    schedule, school, time_slot, assignment_info['class_ref']
                ):
                    return True
        else:
            # 通常クラス同士の重複 - 1つ以外を移動
            for i, assignment_info in enumerate(assignments[1:]):
                if self._move_assignment_to_empty_slot(
                    schedule, school, time_slot, assignment_info['class_ref']
                ):
                    return True
        
        return False
    
    def _move_assignment_to_empty_slot(
        self, 
        schedule: Schedule, 
        school: School,
        from_slot: TimeSlot,
        class_ref: ClassReference
    ) -> bool:
        """授業を空きスロットに移動"""
        
        # 現在の割り当てを取得
        current = schedule.get_assignment(from_slot, class_ref)
        if not current:
            return False
        
        # 空きスロットを探す
        empty_slot = self._find_empty_slot_for_class(
            schedule, class_ref, current.subject, current.teacher
        )
        
        if empty_slot:
            # 移動実行
            schedule.remove_assignment(from_slot, class_ref)
            schedule.assign(empty_slot, current)
            
            self.logger.info(
                f"{class_ref}の{current.subject.name}を"
                f"{from_slot}から{empty_slot}に移動"
            )
            return True
        
        # 空きスロットがない場合は交換を試みる
        return self._try_swap_assignments(schedule, from_slot, class_ref, current)
    
    def _find_empty_slot_for_class(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Teacher
    ) -> Optional[TimeSlot]:
        """クラスの空きスロットを探す"""
        
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            # 同じ曜日に同じ科目がないかチェック
            has_subject_on_day = False
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject == subject:
                    has_subject_on_day = True
                    break
            
            if has_subject_on_day:
                continue  # 日内重複を避ける
            
            # 空きスロットを探す
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 固定授業はスキップ
                if schedule.is_locked(time_slot, class_ref):
                    continue
                
                # 既に授業がある場合はスキップ
                if schedule.get_assignment(time_slot, class_ref):
                    continue
                
                # 教師が空いているかチェック
                if self._is_teacher_available(schedule, teacher, time_slot):
                    return time_slot
        
        return None
    
    def _is_teacher_available(
        self,
        schedule: Schedule,
        teacher: Teacher,
        time_slot: TimeSlot
    ) -> bool:
        """教師が指定時間に空いているかチェック"""
        
        if not teacher:
            return True
        
        # 全クラスをチェック
        from ...entities.school import School
        # 簡易的に18クラスをチェック（実際はschoolから取得すべき）
        for grade in [1, 2, 3]:
            for class_num in [1, 2, 3, 5, 6, 7]:
                class_ref = ClassReference(grade, class_num)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                    # 5組の合同授業チェック
                    if class_ref in self.grade5_refs:
                        continue
                    return False
        
        return True
    
    def _try_swap_assignments(
        self,
        schedule: Schedule,
        conflict_slot: TimeSlot,
        conflict_class: ClassReference,
        conflict_assignment: Assignment
    ) -> bool:
        """他の授業と交換を試みる"""
        
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                target_slot = TimeSlot(day, period)
                
                # 同じスロットはスキップ
                if target_slot == conflict_slot:
                    continue
                
                # 固定授業はスキップ
                if schedule.is_locked(target_slot, conflict_class):
                    continue
                
                target_assignment = schedule.get_assignment(target_slot, conflict_class)
                if not target_assignment:
                    continue
                
                # 交換可能かチェック
                if self._can_swap(
                    schedule, 
                    conflict_slot, conflict_class, conflict_assignment,
                    target_slot, target_assignment
                ):
                    # 交換実行
                    schedule.remove_assignment(conflict_slot, conflict_class)
                    schedule.remove_assignment(target_slot, conflict_class)
                    
                    schedule.assign(conflict_slot, target_assignment)
                    schedule.assign(target_slot, conflict_assignment)
                    
                    self.logger.info(
                        f"{conflict_class}: {conflict_slot}と{target_slot}の授業を交換"
                    )
                    return True
        
        return False
    
    def _can_swap(
        self,
        schedule: Schedule,
        slot1: TimeSlot,
        class_ref: ClassReference,
        assignment1: Assignment,
        slot2: TimeSlot,
        assignment2: Assignment
    ) -> bool:
        """2つの授業が交換可能かチェック"""
        
        # 日内重複チェック
        # assignment1がslot2の日に既にあるか
        for period in range(1, 7):
            if period == slot2.period:
                continue
            check_slot = TimeSlot(slot2.day, period)
            existing = schedule.get_assignment(check_slot, class_ref)
            if existing and existing.subject == assignment1.subject:
                return False
        
        # assignment2がslot1の日に既にあるか
        for period in range(1, 7):
            if period == slot1.period:
                continue
            check_slot = TimeSlot(slot1.day, period)
            existing = schedule.get_assignment(check_slot, class_ref)
            if existing and existing.subject == assignment2.subject:
                return False
        
        # 教師の空き状況チェック
        if assignment1.teacher:
            if not self._is_teacher_available(schedule, assignment1.teacher, slot2):
                return False
        
        if assignment2.teacher:
            if not self._is_teacher_available(schedule, assignment2.teacher, slot1):
                return False
        
        return True
    
    def generate_report(self, schedule: Schedule, school: School) -> str:
        """教師重複のレポートを生成"""
        
        conflicts = self._detect_teacher_conflicts(schedule, school)
        
        report = ["=== 教師重複レポート ===\n"]
        
        if not conflicts:
            report.append("教師重複は検出されませんでした。")
        else:
            report.append(f"検出された教師重複: {len(conflicts)}件\n")
            
            for i, conflict in enumerate(conflicts[:10]):  # 最初の10件
                report.append(f"{i+1}. {conflict['time_slot']} - {conflict['teacher']}先生:")
                for a in conflict['assignments']:
                    report.append(f"   - {a['class_ref']}: {a['assignment'].subject.name}")
                report.append("")
        
        return "\n".join(report)