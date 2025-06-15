"""ランダム交換による局所探索最適化の実装"""
import random
import logging
from typing import List, Tuple
from collections import defaultdict

from ..interfaces.local_search_optimizer import LocalSearchOptimizer, OptimizationResult
from ..interfaces.jiritsu_placement_service import JiritsuRequirement
from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.assignment import Assignment
from ....infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfig


class RandomSwapOptimizer(LocalSearchOptimizer):
    """ランダム交換による局所探索最適化"""
    
    def __init__(self, config: AdvancedCSPConfig, constraint_validator, evaluator):
        self.config = config
        self.constraint_validator = constraint_validator
        self.evaluator = evaluator
        self.logger = logging.getLogger(__name__)
        self.stats = {
            'swap_attempts': 0,
            'swap_success': 0
        }
    
    def optimize(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement],
                max_iterations: int) -> OptimizationResult:
        """局所探索による最適化を実行"""
        self.logger.info("局所探索による最適化を開始")
        
        # 統計情報をリセット
        self.stats = {'swap_attempts': 0, 'swap_success': 0}
        
        initial_score = self.evaluator.evaluate(schedule, school, jiritsu_requirements)
        best_score = initial_score
        no_improvement_count = 0
        iterations_performed = 0
        
        for iteration in range(max_iterations):
            if no_improvement_count > 20:  # 早期終了
                break
            
            # ランダムな交換を試行
            if self.try_swap(schedule, school, jiritsu_requirements):
                current_score = self.evaluator.evaluate(schedule, school, jiritsu_requirements)
                
                if current_score < best_score:
                    best_score = current_score
                    no_improvement_count = 0
                    self.logger.debug(f"改善: イテレーション{iteration}, スコア{best_score}")
                else:
                    no_improvement_count += 1
            else:
                no_improvement_count += 1
            
            iterations_performed += 1
        
        # 改善率を計算
        improvement_percentage = 0.0
        if initial_score > 0:
            improvement_percentage = (initial_score - best_score) / initial_score * 100
        
        return OptimizationResult(
            initial_score=initial_score,
            final_score=best_score,
            iterations_performed=iterations_performed,
            swap_attempts=self.stats['swap_attempts'],
            swap_successes=self.stats['swap_success'],
            improvement_percentage=improvement_percentage
        )
    
    def try_swap(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement]) -> bool:
        """ランダムな交換を試みる"""
        self.stats['swap_attempts'] += 1
        
        # 交換候補を選択
        candidates = self.select_swap_candidates(schedule)
        if not candidates or not candidates[0] or not candidates[1]:
            return False
        
        (slot1, assignment1), (slot2, assignment2) = candidates
        
        # 保護された教科はスキップ
        if (assignment1.subject.is_protected_subject() or 
            assignment2.subject.is_protected_subject()):
            return False
        
        # 自立活動の交換は特別な処理
        if assignment1.subject.name == "自立" or assignment2.subject.name == "自立":
            return self._try_jiritsu_swap(
                schedule, school, slot1, assignment1, slot2, assignment2, jiritsu_requirements
            )
        
        # 通常の交換
        return self._perform_swap(schedule, school, slot1, assignment1, slot2, assignment2)
    
    def select_swap_candidates(self, schedule: Schedule) -> Tuple[Tuple, Tuple]:
        """交換候補を選択"""
        all_assignments = list(schedule.get_all_assignments())
        if len(all_assignments) < 2:
            return None, None
        
        # 同じクラスの2つの割り当てを選択
        class_assignments = defaultdict(list)
        for slot, assignment in all_assignments:
            if not schedule.is_locked(slot, assignment.class_ref):
                class_assignments[assignment.class_ref].append((slot, assignment))
        
        # 交換可能なクラスを選択（交流学級は除外）
        eligible_classes = [
            class_ref for class_ref, assignments in class_assignments.items()
            if len(assignments) >= 2 and class_ref.class_number not in [6, 7]
        ]
        
        if not eligible_classes:
            return None, None
        
        class_ref = random.choice(eligible_classes)
        assignments = class_assignments[class_ref]
        
        if len(assignments) < 2:
            return None, None
        
        # ランダムに2つを選択
        return random.sample(assignments, 2)
    
    def evaluate_swap(self, schedule: Schedule, school: School,
                     jiritsu_requirements: List[JiritsuRequirement],
                     before_score: float) -> bool:
        """交換の評価"""
        after_score = self.evaluator.evaluate(schedule, school, jiritsu_requirements)
        
        # 改善された場合は常に受け入れる
        if after_score < before_score:
            return True
        
        # 確率的に悪化も受け入れる（シミュレーテッドアニーリング）
        if self.config.temperature > 0:
            delta = after_score - before_score
            probability = min(1.0, pow(2.718, -delta / self.config.temperature))
            return random.random() < probability
        
        return False
    
    def _perform_swap(self, schedule: Schedule, school: School,
                     slot1, assignment1, slot2, assignment2) -> bool:
        """実際の交換を実行"""
        # 一時的に削除
        schedule.remove_assignment(slot1, assignment1.class_ref)
        schedule.remove_assignment(slot2, assignment2.class_ref)
        
        # 新しい割り当てを作成
        new_assignment1 = Assignment(
            assignment1.class_ref, assignment2.subject, assignment2.teacher
        )
        new_assignment2 = Assignment(
            assignment2.class_ref, assignment1.subject, assignment1.teacher
        )
        
        # 制約チェック
        if (self.constraint_validator.check_assignment(schedule, school, slot1, new_assignment1) and
            self.constraint_validator.check_assignment(schedule, school, slot2, new_assignment2)):
            schedule.assign(slot1, new_assignment1)
            schedule.assign(slot2, new_assignment2)
            self.stats['swap_success'] += 1
            return True
        else:
            # 元に戻す
            schedule.assign(slot1, assignment1)
            schedule.assign(slot2, assignment2)
            return False
    
    def _try_jiritsu_swap(self, schedule: Schedule, school: School,
                         slot1, assignment1, slot2, assignment2,
                         requirements: List[JiritsuRequirement]) -> bool:
        """自立活動の交換を試みる"""
        # 自立活動制約を維持できるかチェック
        # 簡単な実装：自立活動の交換は禁止
        return False