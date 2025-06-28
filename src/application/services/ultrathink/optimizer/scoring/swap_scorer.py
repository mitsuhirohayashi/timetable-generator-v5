"""交換スコア計算器"""
import logging
from typing import List, Set

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference
from ..data_models import SwapCandidate, Violation


class SwapScorer:
    """交換のスコアを計算"""
    
    def __init__(self, slot_scorer):
        """初期化
        
        Args:
            slot_scorer: スロットスコア計算器
        """
        self.logger = logging.getLogger(__name__)
        self.slot_scorer = slot_scorer
    
    def calculate_score(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School,
        current_violations: List[Violation]
    ) -> float:
        """交換のスコアを計算
        
        Args:
            candidate: 交換候補
            schedule: スケジュール
            school: 学校情報
            current_violations: 現在の違反リスト
            
        Returns:
            スコア（高いほど良い）
        """
        score = 0.0
        
        # 基本的な改善スコア
        score += candidate.improvement_score
        
        # 違反の解決による改善
        violations_fixed_score = len(candidate.violations_fixed) * 0.5
        violations_created_score = len(candidate.violations_created) * 0.5
        score += violations_fixed_score - violations_created_score
        
        # スロットの質の変化を評価
        score += self._evaluate_slot_quality_change(
            candidate, schedule, school
        ) * 0.3
        
        # 教師の満足度変化を評価
        score += self._evaluate_teacher_satisfaction_change(
            candidate, schedule, school
        ) * 0.2
        
        # 全体的なバランスへの影響を評価
        score += self._evaluate_balance_impact(
            candidate, schedule, school
        ) * 0.2
        
        return score
    
    def _evaluate_slot_quality_change(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School
    ) -> float:
        """スロットの質の変化を評価"""
        # 元のスロットの割り当てを取得
        source_assignment = schedule.get_assignment(
            candidate.source_slot, candidate.source_class
        )
        target_assignment = schedule.get_assignment(
            candidate.target_slot, candidate.target_class
        )
        
        if not source_assignment or not target_assignment:
            return 0.0
        
        # 現在のスロットスコア
        current_source_score = self.slot_scorer.calculate_score(
            candidate.source_slot, candidate.source_class,
            source_assignment.teacher, source_assignment.subject,
            schedule
        )
        current_target_score = self.slot_scorer.calculate_score(
            candidate.target_slot, candidate.target_class,
            target_assignment.teacher, target_assignment.subject,
            schedule
        )
        
        # 交換後のスロットスコア（仮想的に計算）
        new_source_score = self.slot_scorer.calculate_score(
            candidate.source_slot, candidate.source_class,
            target_assignment.teacher, target_assignment.subject,
            schedule
        )
        new_target_score = self.slot_scorer.calculate_score(
            candidate.target_slot, candidate.target_class,
            source_assignment.teacher, source_assignment.subject,
            schedule
        )
        
        # 変化量を計算
        improvement = (new_source_score + new_target_score) - \
                     (current_source_score + current_target_score)
        
        return improvement
    
    def _evaluate_teacher_satisfaction_change(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School
    ) -> float:
        """教師の満足度変化を評価"""
        # 簡略化された実装
        # TODO: より詳細な教師満足度モデルを実装
        
        source_assignment = schedule.get_assignment(
            candidate.source_slot, candidate.source_class
        )
        target_assignment = schedule.get_assignment(
            candidate.target_slot, candidate.target_class
        )
        
        if not source_assignment or not target_assignment:
            return 0.0
        
        satisfaction_change = 0.0
        
        # 連続授業の解消/生成を評価
        if source_assignment.teacher == target_assignment.teacher:
            # 同じ教師の場合、移動による影響は少ない
            satisfaction_change += 0.1
        else:
            # 異なる教師の場合、両方の負荷バランスを考慮
            satisfaction_change += 0.0
        
        return satisfaction_change
    
    def _evaluate_balance_impact(
        self,
        candidate: SwapCandidate,
        schedule: Schedule,
        school: School
    ) -> float:
        """全体的なバランスへの影響を評価"""
        balance_score = 0.0
        
        # 日内のバランス
        balance_score += self._evaluate_daily_balance(
            candidate, schedule
        ) * 0.5
        
        # 週内のバランス
        balance_score += self._evaluate_weekly_balance(
            candidate, schedule
        ) * 0.5
        
        return balance_score
    
    def _evaluate_daily_balance(
        self,
        candidate: SwapCandidate,
        schedule: Schedule
    ) -> float:
        """日内バランスの評価"""
        # 同じ日内での交換は影響が少ない
        if candidate.source_slot.day == candidate.target_slot.day:
            return 0.1
        
        # 異なる日への移動は、両日のバランスを考慮
        return 0.0
    
    def _evaluate_weekly_balance(
        self,
        candidate: SwapCandidate,
        schedule: Schedule
    ) -> float:
        """週内バランスの評価"""
        # 月曜と金曜を避ける傾向
        unfavorable_days = {"月", "金"}
        
        score = 0.0
        
        # 不利な日から有利な日への移動
        if (candidate.source_slot.day in unfavorable_days and
            candidate.target_slot.day not in unfavorable_days):
            score += 0.2
        
        # 有利な日から不利な日への移動
        elif (candidate.source_slot.day not in unfavorable_days and
              candidate.target_slot.day in unfavorable_days):
            score -= 0.2
        
        return score