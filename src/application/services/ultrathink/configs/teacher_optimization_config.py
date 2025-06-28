"""教師最適化設定

教師満足度最適化に関する設定を管理します。
"""
from dataclasses import dataclass


@dataclass
class TeacherOptimizationConfig:
    """教師最適化の設定"""
    enable_teacher_preference: bool = True
    enable_pattern_analysis: bool = True
    enable_satisfaction_optimization: bool = True
    satisfaction_weight: float = 0.3  # 最適化における満足度の重み
    min_teacher_satisfaction: float = 0.6  # 最低満足度の閾値
    collaborative_teaching_bonus: float = 0.1  # 協力教育のボーナス
    worklife_balance_weight: float = 0.2  # ワークライフバランスの重み
    learning_rate: float = 0.1  # 学習率
    
    # 教師タイプ別の設定
    new_teacher_support: bool = True  # 新任教師のサポート
    veteran_flexibility: bool = True  # ベテラン教師の柔軟性
    
    # フィードバック設定
    auto_feedback_generation: bool = True  # 自動フィードバック生成
    feedback_threshold: float = 0.3  # フィードバック生成の閾値


@dataclass
class TeacherSatisfactionMetrics:
    """教師満足度メトリクス"""
    teacher_name: str
    overall_satisfaction: float
    time_preference_score: float
    workload_balance_score: float
    collaboration_score: float
    continuous_teaching_score: float
    break_time_score: float
    subject_consistency_score: float
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'teacher_name': self.teacher_name,
            'overall_satisfaction': self.overall_satisfaction,
            'time_preference_score': self.time_preference_score,
            'workload_balance_score': self.workload_balance_score,
            'collaboration_score': self.collaboration_score,
            'continuous_teaching_score': self.continuous_teaching_score,
            'break_time_score': self.break_time_score,
            'subject_consistency_score': self.subject_consistency_score
        }