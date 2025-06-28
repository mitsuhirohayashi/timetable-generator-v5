"""教師重複違反修正器"""
import logging
from typing import List, Optional, Set
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import Violation, SwapCandidate, SwapChain


class TeacherConflictFixer:
    """教師重複違反を修正"""
    
    def __init__(self, grade5_refs: Set[ClassReference]):
        """初期化
        
        Args:
            grade5_refs: 5組のクラス参照セット
        """
        self.logger = logging.getLogger(__name__)
        self.grade5_refs = grade5_refs
    
    def fix(
        self,
        violation: Violation,
        schedule: Schedule,
        school: School,
        max_candidates: int = 50
    ) -> Optional[SwapChain]:
        """教師重複を修正
        
        Args:
            violation: 教師重複違反
            schedule: スケジュール
            school: 学校情報
            max_candidates: 最大候補数
            
        Returns:
            修正のための交換連鎖、または None
        """
        if not violation.teacher:
            return None
        
        conflicting_classes = violation.class_refs
        time_slot = violation.time_slot
        
        # 移動可能なクラスを選択（優先度: 非5組）
        target_class = None
        for class_ref in conflicting_classes:
            if class_ref not in self.grade5_refs:
                target_class = class_ref
                break
        
        if not target_class:
            target_class = conflicting_classes[0]
        
        # 交換候補を探索
        best_chain = None
        best_score = float('-inf')
        
        # 1. 空きスロットへの移動を試す
        empty_slot = self._find_best_empty_slot(
            schedule, school, target_class, violation.teacher, time_slot
        )
        
        if empty_slot:
            swap = SwapCandidate(
                source_slot=time_slot,
                source_class=target_class,
                target_slot=empty_slot,
                target_class=target_class,
                improvement_score=0.8,  # 空きスロットへの移動は高評価
                violations_fixed={violation}
            )
            
            chain = SwapChain()
            chain.add_swap(swap)
            return chain
        
        # 2. 他のスロットとの交換を試す
        candidates = self._find_swap_candidates(
            schedule, school, target_class, violation.teacher, 
            time_slot, max_candidates
        )
        
        for candidate in candidates:
            score = self._evaluate_swap(candidate, schedule, school)
            if score > best_score:
                best_score = score
                chain = SwapChain()
                chain.add_swap(candidate)
                best_chain = chain
        
        return best_chain
    
    def _find_best_empty_slot(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        teacher,
        avoid_slot: TimeSlot
    ) -> Optional[TimeSlot]:
        """最適な空きスロットを探す"""
        days = ["月", "火", "水", "木", "金"]
        best_slot = None
        best_score = float('-inf')
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if time_slot == avoid_slot:
                    continue
                
                # 空きかチェック
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    continue
                
                # 教師が利用可能かチェック
                if not self._is_teacher_available(schedule, school, teacher, time_slot):
                    continue
                
                # スコアを計算
                score = self._calculate_slot_score(time_slot, class_ref, teacher, schedule)
                if score > best_score:
                    best_score = score
                    best_slot = time_slot
        
        return best_slot
    
    def _find_swap_candidates(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        teacher,
        current_slot: TimeSlot,
        max_candidates: int
    ) -> List[SwapCandidate]:
        """交換候補を探す"""
        candidates = []
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if time_slot == current_slot:
                    continue
                
                target_assignment = schedule.get_assignment(time_slot, class_ref)
                if not target_assignment:
                    continue
                
                # 交換可能かチェック
                if self._can_swap(
                    schedule, school, class_ref, current_slot,
                    class_ref, time_slot
                ):
                    candidate = SwapCandidate(
                        source_slot=current_slot,
                        source_class=class_ref,
                        target_slot=time_slot,
                        target_class=class_ref,
                        improvement_score=0.5
                    )
                    candidates.append(candidate)
                
                if len(candidates) >= max_candidates:
                    break
            
            if len(candidates) >= max_candidates:
                break
        
        return candidates
    
    def _is_teacher_available(
        self,
        schedule: Schedule,
        school: School,
        teacher,
        time_slot: TimeSlot
    ) -> bool:
        """教師が利用可能かチェック"""
        # 他のクラスで授業があるか確認
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher == teacher:
                return False
        return True
    
    def _can_swap(
        self,
        schedule: Schedule,
        school: School,
        source_class: ClassReference,
        source_slot: TimeSlot,
        target_class: ClassReference,
        target_slot: TimeSlot
    ) -> bool:
        """交換可能かチェック"""
        source_assignment = schedule.get_assignment(source_slot, source_class)
        target_assignment = schedule.get_assignment(target_slot, target_class)
        
        if not source_assignment or not target_assignment:
            return False
        
        # 固定科目はスキップ
        fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行"}
        if (source_assignment.subject.name in fixed_subjects or
            target_assignment.subject.name in fixed_subjects):
            return False
        
        # 教師の利用可能性をチェック
        if source_assignment.teacher:
            if not self._is_teacher_available(schedule, school, source_assignment.teacher, target_slot):
                return False
        
        if target_assignment.teacher:
            if not self._is_teacher_available(schedule, school, target_assignment.teacher, source_slot):
                return False
        
        return True
    
    def _calculate_slot_score(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        teacher,
        schedule: Schedule
    ) -> float:
        """スロットのスコアを計算"""
        score = 0.0
        
        # 午前中は高評価
        if time_slot.period <= 3:
            score += 0.2
        
        # 月曜1限と金曜6限は低評価
        if (time_slot.day == "月" and time_slot.period == 1) or \
           (time_slot.day == "金" and time_slot.period == 6):
            score -= 0.3
        
        # 教師の既存授業との連続性を評価
        if time_slot.period > 1:
            prev_slot = TimeSlot(time_slot.day, time_slot.period - 1)
            prev_assignment = schedule.get_assignment(prev_slot, class_ref)
            if prev_assignment and prev_assignment.teacher == teacher:
                score += 0.1  # 連続授業
        
        if time_slot.period < 6:
            next_slot = TimeSlot(time_slot.day, time_slot.period + 1)
            next_assignment = schedule.get_assignment(next_slot, class_ref)
            if next_assignment and next_assignment.teacher == teacher:
                score += 0.1  # 連続授業
        
        return score
    
    def _evaluate_swap(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School
    ) -> float:
        """交換の評価"""
        score = candidate.improvement_score
        
        # 追加の評価基準を実装
        # TODO: より詳細な評価ロジック
        
        return score