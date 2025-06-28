"""シミュレーテッドアニーリングによるスケジュール最適化"""
import logging
import random
import math
from typing import List, Tuple, Optional

from ....domain.interfaces.schedule_optimizer import ScheduleOptimizer
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.base import ConstraintValidator
from ....domain.interfaces.csp_configuration import ICSPConfiguration


class SimulatedAnnealingOptimizer(ScheduleOptimizer):
    """シミュレーテッドアニーリングによる最適化"""
    
    def __init__(self, config: ICSPConfiguration, constraint_validator: ConstraintValidator,
                 schedule_evaluator):
        self.config = config
        self.constraint_validator = constraint_validator
        self.evaluator = schedule_evaluator
        self.logger = logging.getLogger(__name__)
        
        # アニーリングパラメータ
        self.initial_temperature = 100.0
        self.cooling_rate = 0.95
        self.min_temperature = 0.01
        self.iterations_per_temperature = 50
    
    def optimize(self, schedule: Schedule, school: School, max_iterations: int = 1000) -> Schedule:
        """シミュレーテッドアニーリングでスケジュールを最適化"""
        self.logger.info("シミュレーテッドアニーリング最適化を開始")
        
        # 初期状態
        current_schedule = schedule.copy()
        current_score = self.evaluator.evaluate(current_schedule, school)
        best_schedule = current_schedule.copy()
        best_score = current_score
        
        # 温度とイテレーション
        temperature = self.initial_temperature
        total_iterations = 0
        accepted_moves = 0
        
        while temperature > self.min_temperature and total_iterations < max_iterations:
            for _ in range(self.iterations_per_temperature):
                total_iterations += 1
                
                # 近傍解を生成
                neighbor_schedule, move_info = self._generate_neighbor(current_schedule, school)
                if not neighbor_schedule:
                    continue
                
                # 近傍解を評価
                neighbor_score = self.evaluator.evaluate(neighbor_schedule, school)
                
                # 受理確率を計算
                delta = neighbor_score - current_score
                if delta < 0 or random.random() < math.exp(-delta / temperature):
                    # 移動を受理
                    current_schedule = neighbor_schedule
                    current_score = neighbor_score
                    accepted_moves += 1
                    
                    # ベスト解を更新
                    if current_score < best_score:
                        best_schedule = current_schedule.copy()
                        best_score = current_score
                        self.logger.debug(f"新しいベスト解: スコア={best_score:.2f}")
            
            # 温度を下げる
            temperature *= self.cooling_rate
            
            # 定期的にログ出力
            if total_iterations % 100 == 0:
                self.logger.debug(f"イテレーション {total_iterations}: "
                                f"温度={temperature:.2f}, ベストスコア={best_score:.2f}, "
                                f"受理率={accepted_moves/total_iterations:.2%}")
        
        self.logger.info(f"最適化完了: イテレーション={total_iterations}, "
                        f"受理移動={accepted_moves}, "
                        f"最終スコア={best_score:.2f}")
        
        return best_schedule
    
    def _generate_neighbor(self, schedule: Schedule, school: School) -> Tuple[Optional[Schedule], Optional[dict]]:
        """近傍解を生成"""
        # 移動タイプをランダムに選択
        move_type = random.choice(['swap', 'relocate', 'chain_swap'])
        
        if move_type == 'swap':
            return self._swap_move(schedule, school)
        elif move_type == 'relocate':
            return self._relocate_move(schedule, school)
        else:  # chain_swap
            return self._chain_swap_move(schedule, school)
    
    def _swap_move(self, schedule: Schedule, school: School) -> Tuple[Optional[Schedule], Optional[dict]]:
        """2つの授業を交換"""
        all_slots = self._get_all_slots(schedule)
        if len(all_slots) < 2:
            return None, None
        
        # ランダムに2つのスロットを選択
        slot1, class1 = random.choice(all_slots)
        slot2, class2 = random.choice(all_slots)
        
        if (slot1, class1) == (slot2, class2):
            return None, None
        
        # 割り当てを取得
        assign1 = schedule.get_assignment(slot1, class1)
        assign2 = schedule.get_assignment(slot2, class2)
        
        # 両方が空の場合はスキップ
        if not assign1 and not assign2:
            return None, None
        
        # コピーを作成
        new_schedule = schedule.copy()
        
        try:
            # ロックチェック
            if new_schedule.is_locked(slot1, class1) or new_schedule.is_locked(slot2, class2):
                return None, None
            
            # 交換を実行
            if assign1:
                new_schedule.remove_assignment(slot1, class1)
            if assign2:
                new_schedule.remove_assignment(slot2, class2)
            
            # 制約チェックして配置
            success = True
            if assign2:
                new_assign2_at_slot1 = Assignment(class1, assign2.subject, assign2.teacher)
                if self.constraint_validator.check_assignment(new_schedule, school, slot1, new_assign2_at_slot1):
                    new_schedule.assign(slot1, new_assign2_at_slot1)
                else:
                    success = False
            
            if success and assign1:
                new_assign1_at_slot2 = Assignment(class2, assign1.subject, assign1.teacher)
                if self.constraint_validator.check_assignment(new_schedule, school, slot2, new_assign1_at_slot2):
                    new_schedule.assign(slot2, new_assign1_at_slot2)
                else:
                    success = False
            
            if not success:
                return None, None
            
            move_info = {
                'type': 'swap',
                'slot1': slot1,
                'class1': class1,
                'slot2': slot2,
                'class2': class2
            }
            
            return new_schedule, move_info
            
        except Exception:
            return None, None
    
    def _relocate_move(self, schedule: Schedule, school: School) -> Tuple[Optional[Schedule], Optional[dict]]:
        """1つの授業を別の空きスロットに移動"""
        all_slots = self._get_all_slots(schedule)
        if not all_slots:
            return None, None
        
        # 授業があるスロットを選択
        filled_slots = [(s, c) for s, c in all_slots if schedule.get_assignment(s, c)]
        if not filled_slots:
            return None, None
        
        source_slot, source_class = random.choice(filled_slots)
        assignment = schedule.get_assignment(source_slot, source_class)
        
        # 移動先候補を探す
        candidates = []
        for day in self.config.weekdays:
            for period in range(1, 7):
                target_slot = TimeSlot(day, period)
                if target_slot == source_slot:
                    continue
                
                # 空きスロットかつロックされていない
                if (not schedule.get_assignment(target_slot, source_class) and
                    not schedule.is_locked(target_slot, source_class)):
                    candidates.append(target_slot)
        
        if not candidates:
            return None, None
        
        target_slot = random.choice(candidates)
        
        # コピーを作成して移動を試みる
        new_schedule = schedule.copy()
        
        try:
            # 元の位置から削除
            new_schedule.remove_assignment(source_slot, source_class)
            
            # 新しい位置に配置
            if self.constraint_validator.check_assignment(new_schedule, school, target_slot, assignment):
                new_schedule.assign(target_slot, assignment)
                
                move_info = {
                    'type': 'relocate',
                    'source_slot': source_slot,
                    'target_slot': target_slot,
                    'class': source_class
                }
                
                return new_schedule, move_info
            
        except Exception:
            pass
        
        return None, None
    
    def _chain_swap_move(self, schedule: Schedule, school: School) -> Tuple[Optional[Schedule], Optional[dict]]:
        """3つ以上の授業の連鎖的な交換"""
        all_slots = self._get_all_slots(schedule)
        if len(all_slots) < 3:
            return None, None
        
        # チェーンの長さ（3〜5）
        chain_length = random.randint(3, min(5, len(all_slots)))
        
        # チェーンを構築
        chain = []
        used = set()
        
        for _ in range(chain_length):
            candidates = [(s, c) for s, c in all_slots if (s, c) not in used]
            if not candidates:
                break
            slot, class_ref = random.choice(candidates)
            chain.append((slot, class_ref))
            used.add((slot, class_ref))
        
        if len(chain) < 3:
            return None, None
        
        # 割り当てを取得
        assignments = []
        for slot, class_ref in chain:
            assignments.append(schedule.get_assignment(slot, class_ref))
        
        # コピーを作成
        new_schedule = schedule.copy()
        
        try:
            # ロックチェック
            for slot, class_ref in chain:
                if new_schedule.is_locked(slot, class_ref):
                    return None, None
            
            # すべて削除
            for i, (slot, class_ref) in enumerate(chain):
                if assignments[i]:
                    new_schedule.remove_assignment(slot, class_ref)
            
            # 循環的に配置
            success = True
            for i in range(len(chain)):
                next_i = (i + 1) % len(chain)
                if assignments[i]:
                    slot, class_ref = chain[next_i]
                    new_assignment = Assignment(class_ref, assignments[i].subject, assignments[i].teacher)
                    
                    if self.constraint_validator.check_assignment(new_schedule, school, slot, new_assignment):
                        new_schedule.assign(slot, new_assignment)
                    else:
                        success = False
                        break
            
            if not success:
                return None, None
            
            move_info = {
                'type': 'chain_swap',
                'chain': chain
            }
            
            return new_schedule, move_info
            
        except Exception:
            return None, None
    
    def _get_all_slots(self, schedule: Schedule) -> List[Tuple[TimeSlot, ClassReference]]:
        """すべてのスロットを取得"""
        slots = []
        for slot, assignment in schedule.get_all_assignments():
            slots.append((slot, assignment.class_ref))
        
        # 空きスロットも含める
        all_classes = list(set(a.class_ref for _, a in schedule.get_all_assignments()))
        for day in self.config.weekdays:
            for period in range(1, 7):
                slot = TimeSlot(day, period)
                for class_ref in all_classes:
                    if not any((s, a.class_ref) == (slot, class_ref) 
                             for s, a in schedule.get_all_assignments()):
                        slots.append((slot, class_ref))
        
        return slots