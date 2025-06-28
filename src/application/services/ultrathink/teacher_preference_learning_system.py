"""
教師の好み学習システム

成功した配置パターンを学習し、教師ごとの配置スコアを計算します。
長期的な傾向を追跡し、個人の好みを反映した時間割生成を支援します。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from datetime import datetime, timedelta
from collections import defaultdict
import os
import json
import numpy as np

from .teacher_pattern_analyzer import TeacherPatternAnalyzer, TeacherPreference, TeachingPattern
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Teacher, Subject
from ....domain.value_objects.time_slot import TimeSlot
from ....domain.value_objects.time_slot import ClassReference
from ....domain.value_objects.assignment import Assignment

# リファクタリングしたモジュールからインポート
from .preference_learning.data_models import PlacementFeedback, LearningState
from .preference_learning.preference_calculator import PreferenceCalculator
from .preference_learning.pattern_learner import PatternLearner
from .preference_learning.teacher_profiler import TeacherProfiler
from .preference_learning.learning_persistence import LearningPersistence


class TeacherPreferenceLearningSystem:
    """教師の好み学習システム"""
    
    def __init__(
        self,
        pattern_analyzer: Optional[TeacherPatternAnalyzer] = None,
        data_dir: Optional[str] = None
    ):
        """
        Args:
            pattern_analyzer: 教師パターン分析器
            data_dir: 学習データを保存するディレクトリ
        """
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "learning_data")
        
        # パターン分析器
        self.pattern_analyzer = pattern_analyzer or TeacherPatternAnalyzer(
            os.path.join(self.data_dir, "patterns")
        )
        
        # 学習状態
        self.state = LearningState()
        
        # 学習履歴
        self.learning_history: List[Dict[str, Any]] = []
        
        # リファクタリングしたモジュールのインスタンス
        self.preference_calculator = PreferenceCalculator(self.state, self.pattern_analyzer)
        self.pattern_learner = PatternLearner(self.state)
        self.teacher_profiler = TeacherProfiler()
        self.learning_persistence = LearningPersistence(self.data_dir)
        
        # 季節・時期による調整係数
        self.seasonal_factors = self.learning_persistence.initialize_seasonal_factors()
        
        # データの読み込み
        self.learning_history = self.learning_persistence.load_state(self.state)
    
    def learn_from_schedule(
        self,
        schedule: Schedule,
        school: School,
        violations: List[Any],
        feedback: Optional[List[PlacementFeedback]] = None
    ) -> Dict[str, Any]:
        """スケジュールから学習"""
        self.logger.info("教師の好み学習を開始")
        
        learning_result = {
            'timestamp': datetime.now().isoformat(),
            'placements_analyzed': 0,
            'patterns_learned': 0,
            'preferences_updated': 0,
            'satisfaction_improvement': 0.0,
            'new_insights': []
        }
        
        # パターン分析を実行
        pattern_analysis = self.pattern_analyzer.analyze_schedule(schedule, school)
        
        # 各配置を評価して学習
        for time_slot, assignment in schedule.get_all_assignments():
            if not assignment.teacher:
                continue
            
            # 配置の満足度を計算
            satisfaction = self.preference_calculator.evaluate_placement(
                assignment, time_slot, schedule, school, violations
            )
            
            # 学習データに追加
            self.pattern_learner.record_placement(
                assignment, time_slot, satisfaction, pattern_analysis
            )
            
            learning_result['placements_analyzed'] += 1
        
        # フィードバックがある場合は処理
        if feedback:
            for fb in feedback:
                self._process_feedback(fb)
                self.state.feedback_history.append(fb)
        
        # 教師の好みを更新
        for teacher_name in pattern_analysis['teacher_patterns']:
            old_pref = self.pattern_analyzer.get_teacher_preference(teacher_name)
            self._update_teacher_preference(teacher_name, pattern_analysis)
            new_pref = self.pattern_analyzer.get_teacher_preference(teacher_name)
            
            # 変化を検出
            if self.teacher_profiler.preference_changed_significantly(old_pref, new_pref):
                learning_result['preferences_updated'] += 1
                learning_result['new_insights'].append(
                    self.teacher_profiler.generate_insight(teacher_name, old_pref, new_pref)
                )
        
        # パターンの学習
        new_patterns = self.pattern_learner.learn_patterns(schedule, school, violations)
        learning_result['patterns_learned'] = len(new_patterns)
        
        # 満足度の改善を計算
        learning_result['satisfaction_improvement'] = self._calculate_improvement()
        
        # 統計を更新
        self._update_statistics(learning_result)
        
        # 学習履歴に追加
        self.learning_history.append(learning_result)
        
        # データを保存
        self.learning_persistence.save_state(self.state, self.learning_history)
        
        self.logger.info("教師の好み学習完了")
        return learning_result
    
    def get_placement_recommendation(
        self,
        teacher_name: str,
        time_slot: TimeSlot,
        available_classes: List[ClassReference],
        context: Optional[Dict] = None
    ) -> List[Tuple[ClassReference, float]]:
        """配置の推奨度を計算"""
        recommendations = []
        
        for class_ref in available_classes:
            score = self.preference_calculator.calculate_preference_score(
                teacher_name, time_slot, class_ref, context
            )
            recommendations.append((class_ref, score))
        
        # スコアでソート（降順）
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        return recommendations
    
    def get_teacher_insights(self, teacher_name: str) -> Dict[str, Any]:
        """教師に関する洞察を取得"""
        preference = self.pattern_analyzer.get_teacher_preference(teacher_name)
        pattern = self.pattern_analyzer.get_teacher_pattern(teacher_name)
        learning_data = self.state.teacher_learning_data.get(teacher_name, {})
        
        insights = {
            'teacher_name': teacher_name,
            'profile': self.teacher_profiler.generate_teacher_profile(preference, pattern),
            'strengths': self.teacher_profiler.identify_strengths(preference, pattern, learning_data),
            'preferences': self.teacher_profiler.summarize_preferences(preference),
            'collaboration': self.teacher_profiler.analyze_collaboration_preferences(teacher_name, pattern),
            'optimization_suggestions': self.teacher_profiler.generate_optimization_suggestions(
                teacher_name, preference, pattern, learning_data
            ),
            'satisfaction_trend': self.teacher_profiler.get_satisfaction_trend(teacher_name, learning_data),
            'confidence_level': self.preference_calculator.get_confidence(teacher_name)
        }
        
        return insights
    
    def _process_feedback(self, feedback: PlacementFeedback):
        """フィードバックを処理"""
        teacher_name = feedback.teacher_name
        
        # 教師の好みを更新
        preference = self.pattern_analyzer.get_teacher_preference(teacher_name)
        
        # フィードバックに基づいて調整
        alpha = self.state.adaptive_parameters['learning_rate']
        
        # 満足度が高い場合
        if feedback.satisfaction_score > 0.7:
            # 時間帯の好みを強化
            if feedback.time_slot.period <= 3:
                preference.morning_preference = min(1.0, preference.morning_preference + alpha * 0.1)
            else:
                preference.afternoon_preference = min(1.0, preference.afternoon_preference + alpha * 0.1)
            
            # クラスとの相性を更新
            class_key = f"{feedback.class_ref.grade}-{feedback.class_ref.class_number}"
            current_affinity = preference.class_affinities.get(class_key, 0.5)
            preference.class_affinities[class_key] = min(1.0, current_affinity + alpha * 0.1)
        
        # 満足度が低い場合
        elif feedback.satisfaction_score < 0.3:
            # 時間帯の好みを弱める
            if feedback.time_slot.period <= 3:
                preference.morning_preference = max(0.0, preference.morning_preference - alpha * 0.1)
            else:
                preference.afternoon_preference = max(0.0, preference.afternoon_preference - alpha * 0.1)
            
            # クラスとの相性を更新
            class_key = f"{feedback.class_ref.grade}-{feedback.class_ref.class_number}"
            current_affinity = preference.class_affinities.get(class_key, 0.5)
            preference.class_affinities[class_key] = max(0.0, current_affinity - alpha * 0.1)
    
    def _update_teacher_preference(
        self,
        teacher_name: str,
        pattern_analysis: Dict
    ):
        """教師の好みを更新"""
        teacher_data = self.state.teacher_learning_data.get(teacher_name, {})
        if not teacher_data:
            return
        
        # 最近の配置から傾向を分析
        recent_placements = teacher_data.get('placements', [])[-20:]
        if not recent_placements:
            return
        
        # 満足度の高い配置を分析
        high_satisfaction = [
            p for p in recent_placements
            if p['satisfaction'] > 0.7
        ]
        
        if high_satisfaction:
            preference = self.pattern_analyzer.get_teacher_preference(teacher_name)
            alpha = self.state.adaptive_parameters['learning_rate']
            
            # 時間帯の傾向を更新
            morning_count = sum(1 for p in high_satisfaction if p['time_slot']['period'] <= 3)
            morning_ratio = morning_count / len(high_satisfaction)
            
            # 既存の好みと新しい傾向を混合
            preference.morning_preference = (1 - alpha) * preference.morning_preference + \
                                          alpha * morning_ratio
            preference.afternoon_preference = 1 - preference.morning_preference
    
    def _calculate_improvement(self) -> float:
        """満足度の改善率を計算"""
        if len(self.learning_history) < 2:
            return 0.0
        
        # 最新と前回の平均満足度を比較
        recent_satisfactions = []
        for teacher_data in self.state.teacher_learning_data.values():
            if teacher_data.get('average_satisfaction'):
                recent_satisfactions.append(teacher_data['average_satisfaction'])
        
        if recent_satisfactions:
            current_avg = sum(recent_satisfactions) / len(recent_satisfactions)
            
            # 前回の履歴から
            if self.learning_history:
                prev_avg = self.learning_history[-1].get('average_satisfaction', 0.5)
                improvement = current_avg - prev_avg
                return improvement
        
        return 0.0
    
    def _update_statistics(self, learning_result: Dict):
        """統計情報を更新"""
        stats = self.state.statistics
        
        stats['total_placements'] += learning_result['placements_analyzed']
        
        # 成功率を計算
        if stats['total_placements'] > 0:
            success_count = len([
                p for p in self.state.success_patterns
                if datetime.fromisoformat(p['timestamp']) > datetime.now() - timedelta(days=30)
            ])
            stats['successful_placements'] = success_count
        
        # 平均満足度
        all_satisfactions = []
        for teacher_data in self.state.teacher_learning_data.values():
            if teacher_data.get('average_satisfaction'):
                all_satisfactions.append(teacher_data['average_satisfaction'])
        
        if all_satisfactions:
            stats['average_satisfaction'] = sum(all_satisfactions) / len(all_satisfactions)
        
        # 改善率
        stats['improvement_rate'] = learning_result.get('satisfaction_improvement', 0.0)
    
