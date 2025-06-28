"""教師の好みスコア計算モジュール

教師の配置に対する満足度スコアを計算する機能を提供します。
"""
import logging
from typing import Dict, Optional, List, Any

from .data_models import LearningState
from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.assignment import Assignment
from .....domain.value_objects.time_slot import ClassReference


class PreferenceCalculator:
    """教師の好みスコア計算クラス"""
    
    def __init__(self, state: LearningState, pattern_analyzer):
        """初期化
        
        Args:
            state: 学習状態
            pattern_analyzer: パターン分析器
        """
        self.logger = logging.getLogger(__name__)
        self.state = state
        self.pattern_analyzer = pattern_analyzer
    
    def calculate_preference_score(
        self,
        teacher_name: str,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        context: Optional[Dict] = None
    ) -> float:
        """教師の好みに基づいて配置スコアを計算
        
        Args:
            teacher_name: 教師名
            time_slot: タイムスロット
            class_ref: クラス参照
            context: 追加のコンテキスト情報
            
        Returns:
            好みスコア（0.0～1.0）
        """
        # 基本スコア（パターン分析器から）
        base_score = self.pattern_analyzer.calculate_placement_score(
            teacher_name, time_slot, class_ref, context
        )
        
        # 学習データからの調整
        learning_adjustment = self._get_learning_adjustment(
            teacher_name, time_slot, class_ref
        )
        
        # 季節・時期による調整
        seasonal_adjustment = self._get_seasonal_adjustment(time_slot)
        
        # コンテキストによる調整
        context_adjustment = self._get_context_adjustment(
            teacher_name, context
        )
        
        # 最終スコアを計算
        final_score = base_score * 0.4 + learning_adjustment * 0.3 + \
                     seasonal_adjustment * 0.15 + context_adjustment * 0.15
        
        # 信頼度による調整
        confidence = self._get_confidence(teacher_name)
        if confidence < self.state.adaptive_parameters['confidence_threshold']:
            # 信頼度が低い場合は中央値に近づける
            final_score = final_score * confidence + 0.5 * (1 - confidence)
        
        return max(0.0, min(1.0, final_score))
    
    def evaluate_placement(
        self,
        assignment: Assignment,
        time_slot: TimeSlot,
        schedule: Schedule,
        school: School,
        violations: List[Any]
    ) -> float:
        """配置の満足度を評価
        
        Args:
            assignment: 配置する授業
            time_slot: タイムスロット
            schedule: スケジュール
            school: 学校情報
            violations: 制約違反リスト
            
        Returns:
            満足度スコア（0.0～1.0）
        """
        factors = {
            'time_preference': 0.0,
            'workload_balance': 0.0,
            'class_compatibility': 0.0,
            'subject_timing': 0.0,
            'violation_penalty': 0.0
        }
        
        teacher_name = assignment.teacher.name
        preference = self.pattern_analyzer.get_teacher_preference(teacher_name)
        
        # 時間帯の好み
        if time_slot.period <= 3:
            factors['time_preference'] = preference.morning_preference
        else:
            factors['time_preference'] = preference.afternoon_preference
        
        # ワークロードバランス
        daily_count = self._count_daily_assignments(
            schedule, teacher_name, time_slot.day
        )
        if daily_count <= preference.daily_max_preferred:
            factors['workload_balance'] = 1.0
        else:
            factors['workload_balance'] = max(
                0.0, 
                1.0 - (daily_count - preference.daily_max_preferred) * 0.2
            )
        
        # クラスとの相性
        class_key = f"{assignment.class_ref.grade}-{assignment.class_ref.class_number}"
        factors['class_compatibility'] = preference.class_affinities.get(class_key, 0.5)
        
        # 科目のタイミング
        factors['subject_timing'] = self._evaluate_subject_timing(
            assignment.subject.name, time_slot, preference
        )
        
        # 違反によるペナルティ
        relevant_violations = self._count_relevant_violations(
            violations, teacher_name, time_slot
        )
        factors['violation_penalty'] = 1.0 - min(relevant_violations * 0.2, 1.0)
        
        # 重み付き平均
        weights = {
            'time_preference': 0.25,
            'workload_balance': 0.25,
            'class_compatibility': 0.20,
            'subject_timing': 0.15,
            'violation_penalty': 0.15
        }
        
        satisfaction = sum(
            factors[key] * weights[key]
            for key in factors
        )
        
        return satisfaction
    
    def _get_learning_adjustment(
        self,
        teacher_name: str,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> float:
        """学習データからの調整値を取得"""
        teacher_data = self.state.teacher_learning_data.get(teacher_name, {})
        if not teacher_data:
            return 0.5
        
        # 類似の配置パターンを探す
        placements = teacher_data.get('placements', [])
        similar_placements = []
        
        for p in placements[-50:]:  # 最新50件
            if (p['time_slot']['day'] == time_slot.day and
                abs(p['time_slot']['period'] - time_slot.period) <= 1):
                similar_placements.append(p['satisfaction'])
        
        if similar_placements:
            return sum(similar_placements) / len(similar_placements)
        
        return teacher_data.get('average_satisfaction', 0.5)
    
    def _get_seasonal_adjustment(self, time_slot: TimeSlot) -> float:
        """季節・時期による調整値を取得"""
        # 簡略化された実装
        return 0.5
    
    def _get_context_adjustment(
        self,
        teacher_name: str,
        context: Optional[Dict]
    ) -> float:
        """コンテキストによる調整値を取得"""
        if not context:
            return 0.5
        
        adjustment = 0.5
        
        # 連続授業の考慮
        if context.get('is_consecutive'):
            preference = self.pattern_analyzer.get_teacher_preference(teacher_name)
            adjustment *= preference.consecutive_preference
        
        # チーム教育の考慮
        if context.get('team_teaching'):
            adjustment *= 1.2  # チーム教育を好む傾向
        
        # 新任教師のサポート
        if context.get('is_new_teacher') and context.get('near_mentor'):
            adjustment *= 1.3
        
        return min(1.0, adjustment)
    
    def get_confidence(self, teacher_name: str) -> float:
        """教師データの信頼度を取得"""
        teacher_data = self.state.teacher_learning_data.get(teacher_name, {})
        placements = teacher_data.get('placements', [])
        
        # 配置数に基づく信頼度
        placement_confidence = min(1.0, len(placements) / 50.0)
        
        # 分散に基づく信頼度
        if len(placements) > 10:
            satisfactions = [p['satisfaction'] for p in placements[-20:]]
            avg = sum(satisfactions) / len(satisfactions)
            variance = sum((s - avg) ** 2 for s in satisfactions) / len(satisfactions)
            variance_confidence = max(0.0, 1.0 - variance * 2)
        else:
            variance_confidence = 0.5
        
        return (placement_confidence + variance_confidence) / 2
    
    def _count_daily_assignments(
        self,
        schedule: Schedule,
        teacher_name: str,
        day: str
    ) -> int:
        """指定日の教師の授業数をカウント"""
        count = 0
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            for class_ref in schedule.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                    count += 1
        return count
    
    def _evaluate_subject_timing(
        self,
        subject_name: str,
        time_slot: TimeSlot,
        preference
    ) -> float:
        """科目のタイミングの適切性を評価"""
        # 主要科目は午前が好ましい
        core_subjects = {"国", "数", "英", "理", "社"}
        if subject_name in core_subjects and time_slot.period <= 3:
            return 0.8
        elif subject_name in core_subjects and time_slot.period > 3:
            return 0.4
        
        # 体育は2-4限が好ましい
        if subject_name == "保" and 2 <= time_slot.period <= 4:
            return 0.9
        elif subject_name == "保":
            return 0.5
        
        # その他の科目
        return 0.6
    
    def _count_relevant_violations(
        self,
        violations: List[Any],
        teacher_name: str,
        time_slot: TimeSlot
    ) -> int:
        """関連する制約違反数をカウント"""
        count = 0
        for v in violations:
            if ((hasattr(v, 'teacher') and v.teacher == teacher_name) or
                (hasattr(v, 'time_slot') and v.time_slot == time_slot)):
                count += 1
        return count