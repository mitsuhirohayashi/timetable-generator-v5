"""日内重複違反修正器"""
import logging
from typing import List, Optional
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import Violation, SwapCandidate, SwapChain


class DailyDuplicateFixer:
    """日内重複違反を修正"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
    
    def fix(
        self,
        violation: Violation,
        schedule: Schedule,
        school: School,
        max_candidates: int = 50
    ) -> Optional[SwapChain]:
        """日内重複を修正
        
        Args:
            violation: 日内重複違反
            schedule: スケジュール
            school: 学校情報
            max_candidates: 最大候補数
            
        Returns:
            修正のための交換連鎖、または None
        """
        if not violation.subject or not violation.class_refs:
            return None
        
        class_ref = violation.class_refs[0]
        duplicate_subject = violation.subject
        day = violation.time_slot.day
        
        # その日の全授業を取得
        day_assignments = []
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                day_assignments.append((time_slot, assignment))
        
        # 重複している科目のスロットを特定
        duplicate_slots = []
        for time_slot, assignment in day_assignments:
            if assignment.subject == duplicate_subject:
                duplicate_slots.append(time_slot)
        
        if len(duplicate_slots) < 2:
            return None
        
        # 最初の重複を残し、2つ目以降を交換対象とする
        target_slot = duplicate_slots[1]
        
        # 交換候補を探索
        best_chain = self._find_best_swap_for_duplicate(
            schedule, school, class_ref, target_slot, 
            duplicate_subject, day, max_candidates
        )
        
        return best_chain
    
    def _find_best_swap_for_duplicate(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        target_slot: TimeSlot,
        duplicate_subject,
        avoid_day: str,
        max_candidates: int
    ) -> Optional[SwapChain]:
        """重複を解消する最適な交換を探す"""
        days = ["月", "火", "水", "木", "金"]
        best_chain = None
        best_score = float('-inf')
        candidate_count = 0
        
        for day in days:
            if day == avoid_day:
                continue
            
            for period in range(1, 7):
                if candidate_count >= max_candidates:
                    break
                
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if not assignment:
                    continue
                
                # 固定科目はスキップ
                if assignment.subject.name in {"欠", "YT", "道", "学", "総", "学総", "行"}:
                    continue
                
                # 同じ日に既にその科目があるかチェック
                if self._has_subject_on_day(schedule, class_ref, assignment.subject, avoid_day):
                    continue
                
                # 交換可能かチェック
                if self._can_swap_for_duplicate(
                    schedule, school, class_ref, target_slot,
                    time_slot, avoid_day
                ):
                    candidate = SwapCandidate(
                        source_slot=target_slot,
                        source_class=class_ref,
                        target_slot=time_slot,
                        target_class=class_ref,
                        improvement_score=0.7
                    )
                    
                    score = self._evaluate_duplicate_swap(
                        candidate, schedule, school, duplicate_subject
                    )
                    
                    if score > best_score:
                        best_score = score
                        chain = SwapChain()
                        chain.add_swap(candidate)
                        best_chain = chain
                    
                    candidate_count += 1
        
        return best_chain
    
    def _has_subject_on_day(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        subject,
        day: str
    ) -> bool:
        """指定日に指定科目があるかチェック"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                return True
        return False
    
    def _can_swap_for_duplicate(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        source_slot: TimeSlot,
        target_slot: TimeSlot,
        avoid_day: str
    ) -> bool:
        """重複解消のための交換が可能かチェック"""
        source_assignment = schedule.get_assignment(source_slot, class_ref)
        target_assignment = schedule.get_assignment(target_slot, class_ref)
        
        if not source_assignment or not target_assignment:
            return False
        
        # 教師の利用可能性をチェック
        if source_assignment.teacher:
            # 対象スロットで教師が利用可能か
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(target_slot, other_class)
                if other_assignment and other_assignment.teacher == source_assignment.teacher:
                    return False
        
        if target_assignment.teacher:
            # 元のスロットで教師が利用可能か
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(source_slot, other_class)
                if other_assignment and other_assignment.teacher == target_assignment.teacher:
                    return False
        
        return True
    
    def _evaluate_duplicate_swap(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School,
        duplicate_subject
    ) -> float:
        """重複解消の交換を評価"""
        score = candidate.improvement_score
        
        # 科目のバランスを考慮
        source_day = candidate.source_slot.day
        target_day = candidate.target_slot.day
        
        # 曜日間のバランスを評価
        day_weights = {
            "月": 0.9,  # 月曜は避ける
            "火": 1.0,
            "水": 1.0,
            "木": 1.0,
            "金": 0.9   # 金曜も少し避ける
        }
        
        score *= day_weights.get(target_day, 1.0)
        
        # 時限の評価
        if candidate.target_slot.period <= 3:
            score += 0.1  # 午前中は好ましい
        
        return score