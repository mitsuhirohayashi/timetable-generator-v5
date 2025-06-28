"""自立活動制約違反修正器"""
import logging
from typing import List, Optional, Dict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School, Subject
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import Violation, SwapCandidate, SwapChain


class JiritsuConstraintFixer:
    """自立活動制約違反を修正"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # 交流学級と親学級の対応関係
        self.exchange_pairs: Dict[ClassReference, ClassReference] = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
    
    def fix(
        self,
        violation: Violation,
        schedule: Schedule,
        school: School,
        max_candidates: int = 50
    ) -> Optional[SwapChain]:
        """自立活動制約違反を修正
        
        交流学級が自立活動の時、親学級は数学か英語でなければならない。
        
        Args:
            violation: 自立活動制約違反
            schedule: スケジュール
            school: 学校情報
            max_candidates: 最大候補数
            
        Returns:
            修正のための交換連鎖、または None
        """
        if len(violation.class_refs) < 2:
            return None
        
        exchange_class = violation.class_refs[0]
        parent_class = violation.class_refs[1]
        time_slot = violation.time_slot
        
        # 現在の親学級の授業を取得
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        if not parent_assignment:
            return None
        
        # 修正方法を選択
        # 1. 親学級の授業を数学/英語に変更
        # 2. 交流学級の自立活動を別の時間に移動
        
        # 方法1を優先的に試す
        chain = self._try_change_parent_to_math_or_english(
            schedule, school, parent_class, time_slot, max_candidates
        )
        
        if chain:
            return chain
        
        # 方法2: 自立活動を移動
        return self._try_move_jiritsu(
            schedule, school, exchange_class, parent_class, 
            time_slot, max_candidates
        )
    
    def _try_change_parent_to_math_or_english(
        self,
        schedule: Schedule,
        school: School,
        parent_class: ClassReference,
        target_slot: TimeSlot,
        max_candidates: int
    ) -> Optional[SwapChain]:
        """親学級の授業を数学または英語に変更"""
        days = ["月", "火", "水", "木", "金"]
        best_chain = None
        best_score = float('-inf')
        candidate_count = 0
        
        # 数学と英語の授業を探す
        for day in days:
            for period in range(1, 7):
                if candidate_count >= max_candidates:
                    break
                
                time_slot = TimeSlot(day, period)
                if time_slot == target_slot:
                    continue
                
                assignment = schedule.get_assignment(time_slot, parent_class)
                if not assignment:
                    continue
                
                # 数学または英語の授業を見つける
                if assignment.subject.name in ["数", "英"]:
                    # 交換可能かチェック
                    if self._can_swap_subjects(
                        schedule, school, parent_class,
                        target_slot, time_slot
                    ):
                        candidate = SwapCandidate(
                            source_slot=target_slot,
                            source_class=parent_class,
                            target_slot=time_slot,
                            target_class=parent_class,
                            improvement_score=0.9  # 高優先度
                        )
                        
                        score = self._evaluate_parent_swap(
                            candidate, schedule, school
                        )
                        
                        if score > best_score:
                            best_score = score
                            chain = SwapChain()
                            chain.add_swap(candidate)
                            best_chain = chain
                        
                        candidate_count += 1
        
        return best_chain
    
    def _try_move_jiritsu(
        self,
        schedule: Schedule,
        school: School,
        exchange_class: ClassReference,
        parent_class: ClassReference,
        current_slot: TimeSlot,
        max_candidates: int
    ) -> Optional[SwapChain]:
        """自立活動を別の時間に移動"""
        days = ["月", "火", "水", "木", "金"]
        best_chain = None
        best_score = float('-inf')
        candidate_count = 0
        
        for day in days:
            for period in range(1, 5):  # 6限は除外
                if candidate_count >= max_candidates:
                    break
                
                time_slot = TimeSlot(day, period)
                if time_slot == current_slot:
                    continue
                
                # 親学級の授業をチェック
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                if not parent_assignment:
                    continue
                
                # 親学級が数学または英語の時間を探す
                if parent_assignment.subject.name in ["数", "英"]:
                    # 交流学級のその時間の授業を確認
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    if not exchange_assignment:
                        continue
                    
                    # 自立活動と交換可能か
                    if self._can_swap_jiritsu(
                        schedule, school, exchange_class,
                        current_slot, time_slot
                    ):
                        candidate = SwapCandidate(
                            source_slot=current_slot,
                            source_class=exchange_class,
                            target_slot=time_slot,
                            target_class=exchange_class,
                            improvement_score=0.8
                        )
                        
                        score = self._evaluate_jiritsu_move(
                            candidate, schedule, school, parent_class
                        )
                        
                        if score > best_score:
                            best_score = score
                            chain = SwapChain()
                            chain.add_swap(candidate)
                            best_chain = chain
                        
                        candidate_count += 1
        
        return best_chain
    
    def _can_swap_subjects(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        slot1: TimeSlot,
        slot2: TimeSlot
    ) -> bool:
        """科目交換が可能かチェック"""
        assignment1 = schedule.get_assignment(slot1, class_ref)
        assignment2 = schedule.get_assignment(slot2, class_ref)
        
        if not assignment1 or not assignment2:
            return False
        
        # 固定科目はスキップ
        fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行"}
        if (assignment1.subject.name in fixed_subjects or
            assignment2.subject.name in fixed_subjects):
            return False
        
        # 教師の利用可能性をチェック
        if assignment1.teacher:
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(slot2, other_class)
                if other_assignment and other_assignment.teacher == assignment1.teacher:
                    return False
        
        if assignment2.teacher:
            for other_class in school.get_all_classes():
                if other_class == class_ref:
                    continue
                other_assignment = schedule.get_assignment(slot1, other_class)
                if other_assignment and other_assignment.teacher == assignment2.teacher:
                    return False
        
        return True
    
    def _can_swap_jiritsu(
        self,
        schedule: Schedule,
        school: School,
        exchange_class: ClassReference,
        jiritsu_slot: TimeSlot,
        target_slot: TimeSlot
    ) -> bool:
        """自立活動の交換が可能かチェック"""
        jiritsu_assignment = schedule.get_assignment(jiritsu_slot, exchange_class)
        target_assignment = schedule.get_assignment(target_slot, exchange_class)
        
        if not jiritsu_assignment or not target_assignment:
            return False
        
        if jiritsu_assignment.subject.name != "自立":
            return False
        
        # 対象が固定科目でないか
        if target_assignment.subject.name in {"欠", "YT", "道", "学", "総", "学総", "行"}:
            return False
        
        # 6限でないか
        if target_slot.period == 6:
            return False
        
        return True
    
    def _evaluate_parent_swap(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School
    ) -> float:
        """親学級の交換を評価"""
        score = candidate.improvement_score
        
        # 時限の評価
        if candidate.source_slot.period <= 3:
            score += 0.1  # 午前中の自立活動は好ましい
        
        return score
    
    def _evaluate_jiritsu_move(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School,
        parent_class: ClassReference
    ) -> float:
        """自立活動の移動を評価"""
        score = candidate.improvement_score
        
        # 時限の評価
        if candidate.target_slot.period <= 3:
            score += 0.1  # 午前中は好ましい
        
        if candidate.target_slot.period == 5:
            score -= 0.2  # 5限は避ける
        
        return score