"""
違反パターン分析器

制約違反のパターンを分析し、特徴を抽出して学習可能な形式に変換する。
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime
import json
import hashlib

# NumPyとscikit-learnをオプショナルに
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    # NumPyがない場合のダミー実装
    class np:
        @staticmethod
        def array(x):
            return x
        @staticmethod
        def mean(x):
            return sum(x) / len(x) if x else 0
        @staticmethod
        def std(x):
            if not x:
                return 0
            mean = sum(x) / len(x)
            return (sum((i - mean) ** 2 for i in x) / len(x)) ** 0.5

try:
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    # scikit-learnがない場合のダミークラス
    class DBSCAN:
        def __init__(self, *args, **kwargs):
            pass
        def fit(self, X):
            # 全て同じクラスタに割り当てる簡易実装
            self.labels_ = [0] * len(X)
            return self
    
    class StandardScaler:
        def __init__(self):
            pass
        def fit_transform(self, X):
            return X

from src.domain.entities import Schedule, School
from src.domain.constraints.base import Constraint, ConstraintViolation, ConstraintPriority


@dataclass
class ViolationFeature:
    """違反の特徴を表現するクラス"""
    violation_type: str
    day: int
    period: int
    class_id: str
    subject: str
    teacher: Optional[str]
    constraint_priority: ConstraintPriority
    additional_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_vector(self) -> List[float]:
        """特徴をベクトル化（クラスタリング用）"""
        # 基本的な数値特徴
        vector = [
            self.day,
            self.period,
            hash(self.class_id) % 100,  # クラスIDを数値化
            hash(self.subject) % 100,    # 科目を数値化
            hash(self.teacher or "") % 100,  # 教師を数値化
            self.constraint_priority.value
        ]
        return vector
    
    def to_pattern_key(self) -> str:
        """パターンの一意なキーを生成"""
        key_parts = [
            self.violation_type,
            f"day{self.day}",
            f"period{self.period}",
            self.class_id,
            self.subject,
            self.teacher or "none"
        ]
        return "_".join(key_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "violation_type": self.violation_type,
            "day": self.day,
            "period": self.period,
            "class_id": self.class_id,
            "subject": self.subject,
            "teacher": self.teacher,
            "priority": self.constraint_priority.name,
            "context": self.additional_context
        }


@dataclass
class ViolationPattern:
    """違反パターンを表現するクラス"""
    pattern_id: str
    features: List[ViolationFeature]
    frequency: int
    first_seen: datetime
    last_seen: datetime
    confidence_score: float = 0.0
    cluster_id: Optional[int] = None
    
    def update_confidence(self, total_generations: int, successful_avoidance: int):
        """信頼度スコアを更新"""
        # 頻度ベースのスコア
        frequency_score = min(self.frequency / 10, 1.0)  # 10回以上で最大
        
        # 回避成功率
        avoidance_rate = successful_avoidance / max(self.frequency, 1)
        
        # 最近性スコア（最近の違反ほど重要）
        days_since_last = (datetime.now() - self.last_seen).days
        recency_score = 1.0 / (1.0 + days_since_last / 30)  # 30日で半減
        
        # 総合スコア
        self.confidence_score = (
            frequency_score * 0.4 +
            avoidance_rate * 0.4 +
            recency_score * 0.2
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "pattern_id": self.pattern_id,
            "features": [f.to_dict() for f in self.features],
            "frequency": self.frequency,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "confidence_score": self.confidence_score,
            "cluster_id": self.cluster_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ViolationPattern':
        """辞書から復元"""
        features = []
        for f_data in data["features"]:
            feature = ViolationFeature(
                violation_type=f_data["violation_type"],
                day=f_data["day"],
                period=f_data["period"],
                class_id=f_data["class_id"],
                subject=f_data["subject"],
                teacher=f_data.get("teacher"),
                constraint_priority=ConstraintPriority[f_data["priority"]],
                additional_context=f_data.get("context", {})
            )
            features.append(feature)
        
        return cls(
            pattern_id=data["pattern_id"],
            features=features,
            frequency=data["frequency"],
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            confidence_score=data.get("confidence_score", 0.0),
            cluster_id=data.get("cluster_id")
        )


class ViolationPatternAnalyzer:
    """違反パターンを分析するクラス"""
    
    def __init__(self):
        self.patterns: Dict[str, ViolationPattern] = {}
        self.violation_history: List[ViolationFeature] = []
        self.cluster_model = None
        self.scaler = StandardScaler()
        
    def extract_features(self, violation: ConstraintViolation, 
                        schedule: Schedule, school: School) -> ViolationFeature:
        """制約違反から特徴を抽出"""
        # 違反の詳細情報を解析
        details = violation.details
        
        # 基本情報の抽出
        violation_type = violation.constraint_type
        constraint_priority = violation.priority
        
        # 時間と場所の情報
        day = details.get("day", -1)
        period = details.get("period", -1)
        class_id = details.get("class_id", "")
        
        # 科目と教師の情報
        subject = details.get("subject", "")
        teacher = details.get("teacher")
        
        # 追加のコンテキスト情報
        additional_context = {
            "message": violation.message,
            "related_classes": details.get("related_classes", []),
            "conflicting_subjects": details.get("conflicting_subjects", []),
            "gym_usage": details.get("gym_usage", False),
            "is_test_period": details.get("is_test_period", False)
        }
        
        return ViolationFeature(
            violation_type=violation_type,
            day=day,
            period=period,
            class_id=class_id,
            subject=subject,
            teacher=teacher,
            constraint_priority=constraint_priority,
            additional_context=additional_context
        )
    
    def analyze_violations(self, violations: List[ConstraintViolation],
                          schedule: Schedule, school: School) -> List[ViolationPattern]:
        """違反のリストを分析してパターンを抽出"""
        # 特徴を抽出
        features = []
        for violation in violations:
            feature = self.extract_features(violation, schedule, school)
            features.append(feature)
            self.violation_history.append(feature)
        
        # パターンを検出
        patterns = self._detect_patterns(features)
        
        # クラスタリングで類似パターンをグループ化
        if len(self.violation_history) > 10:
            self._cluster_patterns()
        
        return patterns
    
    def _detect_patterns(self, features: List[ViolationFeature]) -> List[ViolationPattern]:
        """特徴からパターンを検出"""
        new_patterns = []
        
        for feature in features:
            pattern_key = feature.to_pattern_key()
            
            if pattern_key in self.patterns:
                # 既存パターンを更新
                pattern = self.patterns[pattern_key]
                pattern.frequency += 1
                pattern.last_seen = datetime.now()
                pattern.features.append(feature)
            else:
                # 新しいパターンを作成
                pattern_id = self._generate_pattern_id(feature)
                pattern = ViolationPattern(
                    pattern_id=pattern_id,
                    features=[feature],
                    frequency=1,
                    first_seen=datetime.now(),
                    last_seen=datetime.now()
                )
                self.patterns[pattern_key] = pattern
                new_patterns.append(pattern)
        
        return new_patterns
    
    def _generate_pattern_id(self, feature: ViolationFeature) -> str:
        """パターンIDを生成"""
        content = f"{feature.violation_type}_{feature.day}_{feature.period}_{feature.class_id}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _cluster_patterns(self) -> None:
        """パターンをクラスタリング"""
        if len(self.violation_history) < 5:
            return
        
        # 特徴ベクトルを作成
        vectors = [f.to_vector() for f in self.violation_history[-100:]]  # 最新100件
        
        # 正規化
        vectors_scaled = self.scaler.fit_transform(vectors)
        
        # DBSCANでクラスタリング
        self.cluster_model = DBSCAN(eps=0.5, min_samples=3)
        clusters = self.cluster_model.fit_predict(vectors_scaled)
        
        # クラスタIDを対応するパターンに割り当て
        for i, feature in enumerate(self.violation_history[-100:]):
            pattern_key = feature.to_pattern_key()
            if pattern_key in self.patterns:
                self.patterns[pattern_key].cluster_id = int(clusters[i])
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = {
            "total_violations": len(self.violation_history),
            "unique_patterns": len(self.patterns),
            "violation_types": Counter([f.violation_type for f in self.violation_history]),
            "time_distribution": self._get_time_distribution(),
            "class_distribution": self._get_class_distribution(),
            "teacher_distribution": self._get_teacher_distribution(),
            "priority_distribution": self._get_priority_distribution()
        }
        
        return stats
    
    def _get_time_distribution(self) -> Dict[str, Dict[int, int]]:
        """時間帯別の違反分布"""
        distribution = defaultdict(lambda: defaultdict(int))
        
        for feature in self.violation_history:
            if feature.day >= 0 and feature.period >= 0:
                distribution[f"day_{feature.day}"][feature.period] += 1
        
        return dict(distribution)
    
    def _get_class_distribution(self) -> Dict[str, int]:
        """クラス別の違反分布"""
        return Counter([f.class_id for f in self.violation_history if f.class_id])
    
    def _get_teacher_distribution(self) -> Dict[str, int]:
        """教師別の違反分布"""
        return Counter([f.teacher for f in self.violation_history if f.teacher])
    
    def _get_priority_distribution(self) -> Dict[str, int]:
        """優先度別の違反分布"""
        return Counter([f.constraint_priority.name for f in self.violation_history])
    
    def get_high_frequency_patterns(self, min_frequency: int = 3) -> List[ViolationPattern]:
        """高頻度パターンを取得"""
        patterns = [p for p in self.patterns.values() if p.frequency >= min_frequency]
        return sorted(patterns, key=lambda p: p.frequency, reverse=True)
    
    def get_recent_patterns(self, days: int = 7) -> List[ViolationPattern]:
        """最近のパターンを取得"""
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        patterns = [p for p in self.patterns.values() 
                   if p.last_seen.timestamp() > cutoff]
        return sorted(patterns, key=lambda p: p.last_seen, reverse=True)
    
    def export_patterns(self, filepath: str) -> None:
        """パターンをファイルにエクスポート"""
        data = {
            "patterns": {k: v.to_dict() for k, v in self.patterns.items()},
            "statistics": self.get_statistics(),
            "export_date": datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def import_patterns(self, filepath: str) -> None:
        """パターンをファイルからインポート"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.patterns = {}
        for key, pattern_data in data["patterns"].items():
            pattern = ViolationPattern.from_dict(pattern_data)
            self.patterns[key] = pattern