"""教師満足度計算モジュール

教師の満足度とワークライフバランスを計算する機能を提供します。
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from ..configs.teacher_optimization_config import TeacherSatisfactionMetrics


class TeacherSatisfactionCalculator:
    """教師満足度計算クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_teacher_satisfaction(
        self,
        schedule: Schedule,
        school: School,
        teacher_pattern_analyzer: Optional[object] = None
    ) -> Dict[str, any]:
        """教師満足度を分析
        
        Args:
            schedule: スケジュール
            school: 学校情報
            teacher_pattern_analyzer: 教師パターン分析器
            
        Returns:
            満足度分析結果
        """
        if not teacher_pattern_analyzer:
            return self._create_empty_satisfaction_stats()
        
        # パターン分析を実行
        analysis_result = teacher_pattern_analyzer.analyze_schedule(schedule, school)
        
        # 個別の満足度スコア
        satisfaction_scores = {}
        low_satisfaction = []
        high_satisfaction = []
        
        for teacher_name, data in analysis_result['teacher_patterns'].items():
            score = data.get('satisfaction_score', 0.5)
            satisfaction_scores[teacher_name] = score
            
            if score < 0.4:
                low_satisfaction.append(teacher_name)
            elif score > 0.8:
                high_satisfaction.append(teacher_name)
        
        # 平均満足度
        avg_satisfaction = (
            sum(satisfaction_scores.values()) / len(satisfaction_scores)
            if satisfaction_scores else 0.5
        )
        
        # 統計を作成
        teacher_satisfaction_stats = {
            'individual_scores': satisfaction_scores,
            'average_satisfaction': avg_satisfaction,
            'low_satisfaction_teachers': low_satisfaction,
            'high_satisfaction_teachers': high_satisfaction,
            'improvement_suggestions': analysis_result.get('recommendations', [])
        }
        
        # ワークロードバランスの分析
        workload_info = analysis_result.get('workload_balance', {})
        if workload_info.get('balance_score', 0) > 0.2:
            teacher_satisfaction_stats['improvement_suggestions'].append(
                f"教師の負荷バランスを改善する必要があります"
                f"（バランススコア: {workload_info['balance_score']:.2f}）"
            )
        
        return teacher_satisfaction_stats
    
    def evaluate_teacher_satisfaction(
        self,
        schedule: Schedule,
        school: School
    ) -> float:
        """教師満足度を評価
        
        Args:
            schedule: スケジュール
            school: 学校情報
            
        Returns:
            総合満足度スコア（0-1）
        """
        total_score = 0.0
        teacher_count = 0
        
        # 各教師の満足度を計算
        for teacher in school.get_all_teachers():
            if self._is_real_teacher(teacher.name):
                satisfaction_metrics = self._calculate_individual_satisfaction(
                    teacher.name, schedule, school
                )
                total_score += satisfaction_metrics.overall_satisfaction
                teacher_count += 1
        
        return total_score / teacher_count if teacher_count > 0 else 0.5
    
    def calculate_worklife_balance_score(
        self,
        teacher_name: str,
        schedule: Schedule
    ) -> float:
        """ワークライフバランススコアを計算
        
        Args:
            teacher_name: 教師名
            schedule: スケジュール
            
        Returns:
            ワークライフバランススコア（0-1）
        """
        daily_loads = self._get_daily_loads(teacher_name, schedule)
        
        # 日ごとの負荷のバランスを評価
        if not daily_loads:
            return 1.0
        
        avg_load = sum(daily_loads.values()) / len(daily_loads)
        variance = sum((load - avg_load) ** 2 for load in daily_loads.values()) / len(daily_loads)
        
        # 分散が小さいほどバランスが良い
        balance_score = 1.0 / (1.0 + variance)
        
        # 過度な連続授業のペナルティ
        consecutive_penalty = self._calculate_consecutive_penalty(teacher_name, schedule)
        
        # 1日の最大授業数のペナルティ
        max_daily_penalty = 0.0
        for load in daily_loads.values():
            if load > 5:
                max_daily_penalty += (load - 5) * 0.1
        
        final_score = balance_score - consecutive_penalty - max_daily_penalty
        return max(0.0, min(1.0, final_score))
    
    def _calculate_individual_satisfaction(
        self,
        teacher_name: str,
        schedule: Schedule,
        school: School
    ) -> TeacherSatisfactionMetrics:
        """個別教師の満足度を計算"""
        # 各要素のスコアを計算
        time_preference_score = self._calculate_time_preference_score(teacher_name, schedule)
        workload_balance_score = self.calculate_worklife_balance_score(teacher_name, schedule)
        collaboration_score = self._calculate_collaboration_score(teacher_name, schedule, school)
        continuous_teaching_score = self._calculate_continuous_teaching_score(teacher_name, schedule)
        break_time_score = self._calculate_break_time_score(teacher_name, schedule)
        subject_consistency_score = self._calculate_subject_consistency_score(teacher_name, schedule)
        
        # 総合スコアを計算（重み付き平均）
        overall_satisfaction = (
            time_preference_score * 0.2 +
            workload_balance_score * 0.3 +
            collaboration_score * 0.1 +
            continuous_teaching_score * 0.15 +
            break_time_score * 0.15 +
            subject_consistency_score * 0.1
        )
        
        return TeacherSatisfactionMetrics(
            teacher_name=teacher_name,
            overall_satisfaction=overall_satisfaction,
            time_preference_score=time_preference_score,
            workload_balance_score=workload_balance_score,
            collaboration_score=collaboration_score,
            continuous_teaching_score=continuous_teaching_score,
            break_time_score=break_time_score,
            subject_consistency_score=subject_consistency_score
        )
    
    def _get_daily_loads(self, teacher_name: str, schedule: Schedule) -> Dict[str, int]:
        """日ごとの授業数を取得"""
        daily_loads = defaultdict(int)
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.teacher and assignment.teacher.name == teacher_name:
                daily_loads[time_slot.day] += 1
        
        return dict(daily_loads)
    
    def _calculate_consecutive_penalty(self, teacher_name: str, schedule: Schedule) -> float:
        """連続授業のペナルティを計算"""
        penalty = 0.0
        
        for day in ["月", "火", "水", "木", "金"]:
            consecutive_count = 0
            prev_has_class = False
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                has_class = False
                
                for class_ref in schedule.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                        has_class = True
                        break
                
                if has_class:
                    if prev_has_class:
                        consecutive_count += 1
                        if consecutive_count >= 3:
                            penalty += 0.1  # 3連続以上でペナルティ
                    else:
                        consecutive_count = 1
                else:
                    consecutive_count = 0
                
                prev_has_class = has_class
        
        return penalty
    
    def _calculate_time_preference_score(self, teacher_name: str, schedule: Schedule) -> float:
        """時間帯の好みスコアを計算（デフォルト実装）"""
        # 実際の実装では教師の好みデータを参照
        return 0.7
    
    def _calculate_collaboration_score(self, teacher_name: str, schedule: Schedule, school: School) -> float:
        """協力関係スコアを計算"""
        # 実際の実装では同じ学年の教師との協力度を評価
        return 0.8
    
    def _calculate_continuous_teaching_score(self, teacher_name: str, schedule: Schedule) -> float:
        """連続授業の適切さスコアを計算"""
        penalty = self._calculate_consecutive_penalty(teacher_name, schedule)
        return max(0.0, 1.0 - penalty)
    
    def _calculate_break_time_score(self, teacher_name: str, schedule: Schedule) -> float:
        """休憩時間の適切さスコアを計算"""
        daily_loads = self._get_daily_loads(teacher_name, schedule)
        
        # 1日6コマ全て授業の日がないかチェック
        full_days = sum(1 for load in daily_loads.values() if load >= 6)
        
        if full_days == 0:
            return 1.0
        else:
            return max(0.0, 1.0 - full_days * 0.2)
    
    def _calculate_subject_consistency_score(self, teacher_name: str, schedule: Schedule) -> float:
        """教科の一貫性スコアを計算"""
        # 実際の実装では教師が担当する教科の種類を評価
        return 0.85
    
    def _is_real_teacher(self, teacher_name: str) -> bool:
        """実在の教師かどうかを判定"""
        return (
            teacher_name and
            not teacher_name.endswith("担当") and
            teacher_name not in ["欠", "YT", "道", "学", "総", "学総", "行"]
        )
    
    def _create_empty_satisfaction_stats(self) -> Dict[str, any]:
        """空の満足度統計を作成"""
        return {
            'individual_scores': {},
            'average_satisfaction': 0.5,
            'low_satisfaction_teachers': [],
            'high_satisfaction_teachers': [],
            'improvement_suggestions': []
        }