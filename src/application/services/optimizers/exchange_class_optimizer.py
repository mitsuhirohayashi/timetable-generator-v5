"""交流学級最適化サービス - 自立活動の配置を最適化"""
import logging
from typing import List, Dict, Set, Tuple, Optional
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.exchange_class_sync_constraint import ExchangeClassSyncConstraint


class ExchangeClassOptimizer:
    """交流学級の自立活動配置を最適化するサービス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 交流学級と親学級の対応
        self.exchange_parent_map = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        # 自立活動時に親学級が持つべき教科
        self.required_parent_subjects = {"数", "英"}
        
        # 固定教科（移動不可）
        self.fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
    
    def optimize_jiritsu_placements(self, schedule: Schedule, school: School) -> int:
        """自立活動の配置を最適化
        
        Returns:
            修正した配置の数
        """
        self.logger.info("=== 交流学級の自立活動最適化を開始 ===")
        fixed_count = 0
        
        # 各交流学級の自立活動をチェック
        for exchange_class, parent_class in self.exchange_parent_map.items():
            violations = self._find_jiritsu_violations(schedule, exchange_class, parent_class)
            
            for time_slot, parent_subject in violations:
                self.logger.info(
                    f"違反発見: {exchange_class} {time_slot}で自立活動、"
                    f"親学級{parent_class}は{parent_subject}（数/英である必要）"
                )
                
                # 修正を試みる
                if self._fix_jiritsu_violation(schedule, school, exchange_class, parent_class, time_slot):
                    fixed_count += 1
        
        self.logger.info(f"=== 交流学級最適化完了: {fixed_count}件修正 ===")
        return fixed_count
    
    def _find_jiritsu_violations(
        self, 
        schedule: Schedule, 
        exchange_class: ClassReference, 
        parent_class: ClassReference
    ) -> List[Tuple[TimeSlot, str]]:
        """自立活動の制約違反を検出
        
        Returns:
            違反している時間枠と親学級の教科のリスト
        """
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                if exchange_assignment and exchange_assignment.subject.name == "自立":
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if parent_assignment:
                        if parent_assignment.subject.name not in self.required_parent_subjects:
                            violations.append((time_slot, parent_assignment.subject.name))
                    else:
                        violations.append((time_slot, "空き"))
        
        return violations
    
    def _fix_jiritsu_violation(
        self,
        schedule: Schedule,
        school: School,
        exchange_class: ClassReference,
        parent_class: ClassReference,
        violation_slot: TimeSlot
    ) -> bool:
        """自立活動の制約違反を修正
        
        Returns:
            修正に成功した場合True
        """
        # 親学級の現在の教科を取得
        parent_assignment = schedule.get_assignment(violation_slot, parent_class)
        if not parent_assignment:
            self.logger.warning(f"親学級{parent_class}の{violation_slot}が空きのため修正できません")
            return False
        
        # 固定教科は移動できない
        if parent_assignment.subject.name in self.fixed_subjects:
            self.logger.warning(
                f"親学級の{parent_assignment.subject.name}は固定教科のため移動できません"
            )
            return False
        
        # 数学または英語のスロットを探す
        candidate_slots = self._find_math_or_english_slots(schedule, parent_class)
        
        for candidate_slot in candidate_slots:
            candidate_assignment = schedule.get_assignment(candidate_slot, parent_class)
            
            # 候補スロットの教科が固定教科でないことを確認
            if candidate_assignment.subject.name in self.fixed_subjects:
                continue
            
            # 交流学級の候補スロットをチェック
            exchange_candidate = schedule.get_assignment(candidate_slot, exchange_class)
            if exchange_candidate and exchange_candidate.subject.name in {"自立", "日生", "作業"}:
                # 交流学級も特別な教科の場合はスキップ
                continue
            
            # スワップを試みる
            if self._try_swap_slots(
                schedule, school,
                parent_class, violation_slot, candidate_slot,
                exchange_class
            ):
                self.logger.info(
                    f"修正成功: {parent_class}の{violation_slot}と{candidate_slot}をスワップ"
                )
                return True
        
        self.logger.warning(f"{exchange_class}の{violation_slot}の自立活動違反を修正できませんでした")
        return False
    
    def _find_math_or_english_slots(
        self, 
        schedule: Schedule, 
        class_ref: ClassReference
    ) -> List[TimeSlot]:
        """数学または英語が配置されているスロットを探す"""
        slots = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if assignment and assignment.subject.name in self.required_parent_subjects:
                    slots.append(time_slot)
        
        return slots
    
    def _try_swap_slots(
        self,
        schedule: Schedule,
        school: School,
        parent_class: ClassReference,
        slot1: TimeSlot,
        slot2: TimeSlot,
        exchange_class: ClassReference
    ) -> bool:
        """2つのスロットの内容をスワップ"""
        # 現在の割り当てを取得
        parent_assign1 = schedule.get_assignment(slot1, parent_class)
        parent_assign2 = schedule.get_assignment(slot2, parent_class)
        exchange_assign1 = schedule.get_assignment(slot1, exchange_class)
        exchange_assign2 = schedule.get_assignment(slot2, exchange_class)
        
        if not parent_assign1 or not parent_assign2:
            return False
        
        # ロックされているスロットはスワップできない
        if (schedule.is_locked(slot1, parent_class) or 
            schedule.is_locked(slot2, parent_class) or
            schedule.is_locked(slot1, exchange_class) or
            schedule.is_locked(slot2, exchange_class)):
            return False
        
        try:
            # 一時的に削除
            schedule.remove_assignment(slot1, parent_class)
            schedule.remove_assignment(slot2, parent_class)
            if exchange_assign1:
                schedule.remove_assignment(slot1, exchange_class)
            if exchange_assign2:
                schedule.remove_assignment(slot2, exchange_class)
            
            # スワップして再配置
            new_parent1 = Assignment(parent_class, parent_assign2.subject, parent_assign2.teacher)
            new_parent2 = Assignment(parent_class, parent_assign1.subject, parent_assign1.teacher)
            
            # 親学級の配置
            if not schedule.assign(slot1, new_parent1):
                raise Exception("親学級のスワップ配置に失敗")
            if not schedule.assign(slot2, new_parent2):
                raise Exception("親学級のスワップ配置に失敗")
            
            # 交流学級の配置（自立活動はそのまま、それ以外は親学級に同期）
            if exchange_assign1:
                if exchange_assign1.subject.name == "自立":
                    schedule.assign(slot1, exchange_assign1)
                else:
                    new_exchange1 = Assignment(exchange_class, parent_assign2.subject, parent_assign2.teacher)
                    schedule.assign(slot1, new_exchange1)
            
            if exchange_assign2:
                if exchange_assign2.subject.name == "自立":
                    schedule.assign(slot2, exchange_assign2)
                else:
                    new_exchange2 = Assignment(exchange_class, parent_assign1.subject, parent_assign1.teacher)
                    schedule.assign(slot2, new_exchange2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"スワップ失敗: {e}")
            # ロールバック
            if parent_assign1:
                schedule.assign(slot1, parent_assign1)
            if parent_assign2:
                schedule.assign(slot2, parent_assign2)
            if exchange_assign1:
                schedule.assign(slot1, exchange_assign1)
            if exchange_assign2:
                schedule.assign(slot2, exchange_assign2)
            
            return False