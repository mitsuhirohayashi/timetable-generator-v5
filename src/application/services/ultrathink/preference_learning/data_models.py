"""教師の好み学習システムのデータモデル

学習システムで使用するデータクラスを定義します。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any

from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference


@dataclass
class PlacementFeedback:
    """配置に対するフィードバック
    
    Attributes:
        teacher_name: 教師名
        time_slot: タイムスロット
        class_ref: クラス参照
        subject: 科目名
        satisfaction_score: 満足度スコア（0.0～1.0）
        factors: 満足度の要因
        timestamp: タイムスタンプ
        source: フィードバックの源（system, manual, student）
    """
    teacher_name: str
    time_slot: TimeSlot
    class_ref: ClassReference
    subject: str
    satisfaction_score: float  # 0.0～1.0
    factors: Dict[str, float]  # 満足度の要因
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"  # system, manual, student


@dataclass
class LearningState:
    """学習システムの状態
    
    学習プロセスの現在の状態を保持します。
    """
    # 成功パターンのデータベース
    success_patterns: List[Dict[str, Any]] = field(default_factory=list)
    
    # 失敗パターンのデータベース
    failure_patterns: List[Dict[str, Any]] = field(default_factory=list)
    
    # 教師ごとの学習データ
    teacher_learning_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # フィードバック履歴
    feedback_history: List[PlacementFeedback] = field(default_factory=list)
    
    # 適応的パラメータ
    adaptive_parameters: Dict[str, float] = field(default_factory=lambda: {
        'learning_rate': 0.1,
        'decay_rate': 0.95,
        'exploration_rate': 0.1,
        'confidence_threshold': 0.7
    })
    
    # 統計情報
    statistics: Dict[str, Any] = field(default_factory=lambda: {
        'total_placements': 0,
        'successful_placements': 0,
        'average_satisfaction': 0.0,
        'improvement_rate': 0.0
    })


@dataclass
class TeacherLearningData:
    """教師ごとの学習データ
    
    個々の教師に関する学習情報を保持します。
    """
    teacher_name: str
    preference_scores: Dict[str, float] = field(default_factory=dict)
    placement_history: List[Dict[str, Any]] = field(default_factory=list)
    satisfaction_trend: List[float] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    confidence_level: float = 0.5
    
    # 時間帯別の好み
    time_preferences: Dict[str, float] = field(default_factory=lambda: {
        'morning': 0.5,
        'afternoon': 0.5,
        'early': 0.5,
        'late': 0.5
    })
    
    # 科目別の時間帯好み
    subject_time_preferences: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # クラス別の親和性
    class_affinity: Dict[str, float] = field(default_factory=dict)