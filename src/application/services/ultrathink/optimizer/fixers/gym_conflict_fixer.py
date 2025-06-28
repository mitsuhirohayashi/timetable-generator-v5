"""体育館競合違反修正器"""
import logging
from typing import List, Optional, Set

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import Violation, SwapCandidate, SwapChain


class GymConflictFixer:
    """体育館競合を修正"""
    
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
        """体育館競合を修正
        
        Args:
            violation: 体育館競合違反
            schedule: スケジュール
            school: 学校情報
            max_candidates: 最大候補数
            
        Returns:
            修正のための交換連鎖、または None
        """
        conflicting_classes = violation.class_refs
        time_slot = violation.time_slot
        
        # 5組を除外して処理
        non_grade5_conflicts = [c for c in conflicting_classes if c not in self.grade5_refs]
        
        if not non_grade5_conflicts:
            # 5組のみの競合は正常
            return None
        
        # 移動対象を選択（優先度: 高学年 > 低学年）
        target_class = max(non_grade5_conflicts, key=lambda c: c.grade)
        
        # 体育の授業を別の時間に移動
        best_chain = self._find_best_pe_move(
            schedule, school, target_class, time_slot, max_candidates
        )
        
        return best_chain
    
    def _find_best_pe_move(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        current_slot: TimeSlot,
        max_candidates: int
    ) -> Optional[SwapChain]:
        """体育の授業を移動する最適な方法を探す"""
        days = ["月", "火", "水", "木", "金"]
        best_chain = None
        best_score = float('-inf')
        candidate_count = 0
        
        # 空きスロットを優先的に探す
        for day in days:
            for period in [2, 3, 4]:  # 体育に適した時間帯
                if candidate_count >= max_candidates:
                    break
                
                time_slot = TimeSlot(day, period)
                if time_slot == current_slot:
                    continue
                
                # 体育館が利用可能かチェック
                if not self._is_gym_available(schedule, school, time_slot):
                    continue
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                # 空きスロットの場合
                if not assignment:
                    candidate = SwapCandidate(
                        source_slot=current_slot,
                        source_class=class_ref,
                        target_slot=time_slot,
                        target_class=class_ref,
                        improvement_score=0.9  # 空きスロットへの移動は高評価
                    )
                    
                    chain = SwapChain()
                    chain.add_swap(candidate)
                    return chain  # 即座に返す
                
                # 交換可能な授業の場合
                if self._can_swap_with_pe(schedule, school, class_ref, current_slot, time_slot):
                    candidate = SwapCandidate(
                        source_slot=current_slot,
                        source_class=class_ref,
                        target_slot=time_slot,
                        target_class=class_ref,
                        improvement_score=0.7
                    )
                    
                    score = self._evaluate_pe_swap(candidate, schedule, school)
                    
                    if score > best_score:
                        best_score = score
                        chain = SwapChain()
                        chain.add_swap(candidate)
                        best_chain = chain
                    
                    candidate_count += 1
        
        return best_chain
    
    def _is_gym_available(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot
    ) -> bool:
        """体育館が利用可能かチェック"""
        pe_count = 0
        grade5_pe = False
        
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == "保":
                if class_ref in self.grade5_refs:
                    grade5_pe = True
                else:
                    pe_count += 1
        
        # 5組の体育がある場合、通常学級は不可
        if grade5_pe:
            return pe_count == 0
        
        # 通常学級は1クラスまで
        return pe_count == 0
    
    def _can_swap_with_pe(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        pe_slot: TimeSlot,
        target_slot: TimeSlot
    ) -> bool:
        """体育と交換可能かチェック"""
        pe_assignment = schedule.get_assignment(pe_slot, class_ref)
        target_assignment = schedule.get_assignment(target_slot, class_ref)
        
        if not pe_assignment or not target_assignment:
            return False
        
        if pe_assignment.subject.name != "保":
            return False
        
        # 固定科目は交換不可
        if target_assignment.subject.name in {"欠", "YT", "道", "学", "総", "学総", "行"}:
            return False
        
        # 教師の利用可能性をチェック
        if pe_assignment.teacher:
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(target_slot, other_class)
                if other_assignment and other_assignment.teacher == pe_assignment.teacher:
                    return False
        
        if target_assignment.teacher:
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(pe_slot, other_class)
                if other_assignment and other_assignment.teacher == target_assignment.teacher:
                    return False
        
        return True
    
    def _evaluate_pe_swap(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School
    ) -> float:
        """体育の交換を評価"""
        score = candidate.improvement_score
        
        # 時限の評価（体育に適した時間）
        ideal_periods = {2: 1.0, 3: 1.0, 4: 0.9}
        period_score = ideal_periods.get(candidate.target_slot.period, 0.5)
        score *= period_score
        
        # 曜日の評価
        if candidate.target_slot.day in ["火", "木"]:
            score += 0.1  # 中日が好ましい
        
        # 1限と6限は避ける
        if candidate.target_slot.period in [1, 6]:
            score -= 0.3
        
        return score