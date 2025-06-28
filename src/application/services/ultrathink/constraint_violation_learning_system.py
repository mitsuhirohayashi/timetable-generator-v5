"""
制約違反学習システム

過去の制約違反を学習し、将来の生成時に同じ違反を回避するための
戦略を提供する機械学習ベースのシステム。
"""

from typing import Dict, List, Set, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import numpy as np
from collections import defaultdict
import logging

from src.domain.entities import Schedule, School
from src.domain.constraints.base import Constraint, ConstraintViolation, ConstraintPriority
from .violation_pattern_analyzer import (
    ViolationPatternAnalyzer, ViolationPattern, ViolationFeature
)


logger = logging.getLogger(__name__)


@dataclass
class AvoidanceStrategy:
    """違反回避戦略"""
    strategy_id: str
    pattern_id: str
    description: str
    priority: float
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    success_count: int = 0
    failure_count: int = 0
    
    @property
    def success_rate(self) -> float:
        """成功率を計算"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "strategy_id": self.strategy_id,
            "pattern_id": self.pattern_id,
            "description": self.description,
            "priority": self.priority,
            "conditions": self.conditions,
            "actions": self.actions,
            "success_count": self.success_count,
            "failure_count": self.failure_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AvoidanceStrategy':
        """辞書から復元"""
        return cls(
            strategy_id=data["strategy_id"],
            pattern_id=data["pattern_id"],
            description=data["description"],
            priority=data["priority"],
            conditions=data["conditions"],
            actions=data["actions"],
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0)
        )


@dataclass
class LearningState:
    """学習状態を保持するクラス"""
    generation_count: int = 0
    total_violations: int = 0
    avoided_violations: int = 0
    pattern_database: Dict[str, ViolationPattern] = field(default_factory=dict)
    strategy_database: Dict[str, AvoidanceStrategy] = field(default_factory=dict)
    generation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "generation_count": self.generation_count,
            "total_violations": self.total_violations,
            "avoided_violations": self.avoided_violations,
            "pattern_database": {k: v.to_dict() for k, v in self.pattern_database.items()},
            "strategy_database": {k: v.to_dict() for k, v in self.strategy_database.items()},
            "generation_history": self.generation_history[-100:],  # 最新100世代のみ保存
            "last_updated": self.last_updated.isoformat()
        }


class ConstraintViolationLearningSystem:
    """制約違反学習システムのメインクラス"""
    
    def __init__(self, data_dir: Optional[str] = None):
        self.analyzer = ViolationPatternAnalyzer()
        self.state = LearningState()
        self.data_dir = data_dir or "data/learning"
        self.violation_patterns_file = os.path.join(self.data_dir, "violation_patterns.json")
        self.learning_state_file = os.path.join(self.data_dir, "learning_state.json")
        
        # データディレクトリを作成
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # 既存のデータを読み込み
        self._load_data()
        
        # 予測モデル（簡易的な確率モデル）
        self.violation_probability: Dict[str, float] = {}
        
    def _load_data(self) -> None:
        """保存されたデータを読み込み"""
        # パターンデータを読み込み
        if os.path.exists(self.violation_patterns_file):
            try:
                self.analyzer.import_patterns(self.violation_patterns_file)
                logger.info(f"Loaded violation patterns from {self.violation_patterns_file}")
            except Exception as e:
                logger.error(f"Failed to load violation patterns: {e}")
        
        # 学習状態を読み込み
        if os.path.exists(self.learning_state_file):
            try:
                with open(self.learning_state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.state.generation_count = data["generation_count"]
                    self.state.total_violations = data["total_violations"]
                    self.state.avoided_violations = data["avoided_violations"]
                    self.state.generation_history = data["generation_history"]
                    self.state.last_updated = datetime.fromisoformat(data["last_updated"])
                    
                    # パターンデータベースを復元
                    for key, pattern_data in data["pattern_database"].items():
                        pattern = ViolationPattern.from_dict(pattern_data)
                        self.state.pattern_database[key] = pattern
                    
                    # 戦略データベースを復元
                    for key, strategy_data in data["strategy_database"].items():
                        strategy = AvoidanceStrategy.from_dict(strategy_data)
                        self.state.strategy_database[key] = strategy
                        
                logger.info(f"Loaded learning state from {self.learning_state_file}")
            except Exception as e:
                logger.error(f"Failed to load learning state: {e}")
    
    def _save_data(self) -> None:
        """データを保存"""
        # パターンデータを保存
        self.analyzer.export_patterns(self.violation_patterns_file)
        
        # 学習状態を保存
        with open(self.learning_state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info("Saved learning data")
    
    def learn_from_violations(self, violations: List[ConstraintViolation],
                            schedule: Schedule, school: School) -> None:
        """制約違反から学習"""
        self.state.generation_count += 1
        self.state.total_violations += len(violations)
        
        # パターンを分析
        patterns = self.analyzer.analyze_violations(violations, schedule, school)
        
        # パターンデータベースを更新
        for pattern in self.analyzer.patterns.values():
            self.state.pattern_database[pattern.pattern_id] = pattern
        
        # 回避戦略を生成
        for pattern in patterns:
            if pattern.frequency >= 2:  # 2回以上発生したパターンに対して戦略を生成
                strategies = self._generate_avoidance_strategies(pattern, schedule, school)
                for strategy in strategies:
                    self.state.strategy_database[strategy.strategy_id] = strategy
        
        # 世代履歴を記録
        generation_info = {
            "generation": self.state.generation_count,
            "violations": len(violations),
            "patterns": len(patterns),
            "timestamp": datetime.now().isoformat()
        }
        self.state.generation_history.append(generation_info)
        
        # 確率モデルを更新
        self._update_probability_model()
        
        # データを保存
        self._save_data()
    
    def _generate_avoidance_strategies(self, pattern: ViolationPattern,
                                     schedule: Schedule, school: School) -> List[AvoidanceStrategy]:
        """パターンから回避戦略を生成"""
        strategies = []
        
        # パターンの特徴を分析
        features = pattern.features
        if not features:
            return strategies
        
        # 代表的な特徴を取得
        representative = features[0]
        
        # 戦略1: 時間帯を避ける
        if representative.day >= 0 and representative.period >= 0:
            strategy = AvoidanceStrategy(
                strategy_id=f"avoid_time_{pattern.pattern_id}",
                pattern_id=pattern.pattern_id,
                description=f"Avoid {representative.subject} at day {representative.day}, period {representative.period} for {representative.class_id}",
                priority=pattern.confidence_score,
                conditions={
                    "day": representative.day,
                    "period": representative.period,
                    "class_id": representative.class_id,
                    "subject": representative.subject
                },
                actions=[
                    {"type": "avoid_assignment", "params": {
                        "alternative_periods": self._find_alternative_periods(
                            representative.day, representative.period
                        )
                    }}
                ]
            )
            strategies.append(strategy)
        
        # 戦略2: 教師の競合を避ける
        if representative.teacher and representative.violation_type == "TeacherConflict":
            strategy = AvoidanceStrategy(
                strategy_id=f"avoid_teacher_conflict_{pattern.pattern_id}",
                pattern_id=pattern.pattern_id,
                description=f"Avoid teacher {representative.teacher} conflicts",
                priority=pattern.confidence_score * 1.2,  # 教師競合は高優先度
                conditions={
                    "teacher": representative.teacher,
                    "violation_type": "TeacherConflict"
                },
                actions=[
                    {"type": "check_teacher_availability", "params": {
                        "teacher": representative.teacher
                    }},
                    {"type": "use_alternative_teacher", "params": {
                        "subject": representative.subject
                    }}
                ]
            )
            strategies.append(strategy)
        
        # 戦略3: 交流学級の自立活動ルール
        if "jiritsu" in representative.violation_type.lower():
            strategy = AvoidanceStrategy(
                strategy_id=f"ensure_jiritsu_rule_{pattern.pattern_id}",
                pattern_id=pattern.pattern_id,
                description="Ensure parent class has Math/English when exchange class has Jiritsu",
                priority=pattern.confidence_score * 1.5,  # 自立活動ルールは最高優先度
                conditions={
                    "violation_type": "JiritsuRule",
                    "exchange_class": representative.class_id
                },
                actions=[
                    {"type": "check_parent_class_subject", "params": {
                        "allowed_subjects": ["数学", "英語", "数", "英"]
                    }},
                    {"type": "swap_to_allowed_subject", "params": {}}
                ]
            )
            strategies.append(strategy)
        
        return strategies
    
    def _find_alternative_periods(self, day: int, period: int) -> List[Tuple[int, int]]:
        """代替時間帯を探す"""
        alternatives = []
        
        # 同じ日の他の時間
        for p in range(6):  # 1日6時限
            if p != period:
                alternatives.append((day, p))
        
        # 他の日の同じ時間
        for d in range(5):  # 週5日
            if d != day:
                alternatives.append((d, period))
        
        return alternatives[:5]  # 最大5つの代替案
    
    def _update_probability_model(self) -> None:
        """違反確率モデルを更新"""
        # 各パターンの発生確率を計算
        total_generations = max(self.state.generation_count, 1)
        
        for pattern_id, pattern in self.state.pattern_database.items():
            # 基本確率 = 頻度 / 総世代数
            base_probability = pattern.frequency / total_generations
            
            # 最近性による調整
            days_since_last = (datetime.now() - pattern.last_seen).days
            recency_factor = 1.0 / (1.0 + days_since_last / 30)
            
            # 最終確率
            self.violation_probability[pattern_id] = base_probability * recency_factor
    
    def predict_violations(self, day: int, period: int, class_id: str,
                         subject: str, teacher: Optional[str]) -> float:
        """特定の配置に対する違反確率を予測"""
        # 該当するパターンを検索
        matching_patterns = []
        
        for pattern in self.state.pattern_database.values():
            for feature in pattern.features:
                if (feature.day == day and feature.period == period and
                    feature.class_id == class_id and feature.subject == subject):
                    matching_patterns.append(pattern)
                    break
        
        if not matching_patterns:
            return 0.0
        
        # 最大確率を返す
        max_probability = max(
            self.violation_probability.get(p.pattern_id, 0.0)
            for p in matching_patterns
        )
        
        return max_probability
    
    def get_avoidance_strategies(self, day: int, period: int, class_id: str,
                               subject: str, teacher: Optional[str]) -> List[AvoidanceStrategy]:
        """特定の配置に対する回避戦略を取得"""
        applicable_strategies = []
        
        for strategy in self.state.strategy_database.values():
            conditions = strategy.conditions
            
            # 条件をチェック
            if (conditions.get("day") == day and
                conditions.get("period") == period and
                conditions.get("class_id") == class_id and
                conditions.get("subject") == subject):
                applicable_strategies.append(strategy)
            
            # 教師の条件もチェック
            elif (conditions.get("teacher") == teacher and
                  teacher is not None):
                applicable_strategies.append(strategy)
        
        # 優先度でソート
        applicable_strategies.sort(key=lambda s: s.priority, reverse=True)
        
        return applicable_strategies
    
    def apply_learning_to_schedule(self, schedule: Schedule, school: School,
                                 pre_check_func: Optional[Callable] = None) -> List[str]:
        """学習結果をスケジュールに適用"""
        suggestions = []
        
        for day in range(5):
            for period in range(6):
                for class_info in school.classes.values():
                    class_id = class_info.id
                    current = schedule.get_assignment(day, period, class_id)
                    
                    if current and current.subject:
                        # 違反確率を予測
                        violation_prob = self.predict_violations(
                            day, period, class_id,
                            current.subject, current.teacher
                        )
                        
                        if violation_prob > 0.3:  # 30%以上の確率で違反
                            # 回避戦略を取得
                            strategies = self.get_avoidance_strategies(
                                day, period, class_id,
                                current.subject, current.teacher
                            )
                            
                            for strategy in strategies[:3]:  # 上位3つの戦略
                                suggestion = self._create_suggestion(
                                    strategy, day, period, class_id, current
                                )
                                if suggestion:
                                    suggestions.append(suggestion)
                                    
                                    # 事前チェック関数があれば実行
                                    if pre_check_func:
                                        pre_check_func(day, period, class_id, strategy)
        
        return suggestions
    
    def _create_suggestion(self, strategy: AvoidanceStrategy, day: int, period: int,
                         class_id: str, current: Any) -> Optional[str]:
        """戦略から提案を作成"""
        for action in strategy.actions:
            action_type = action["type"]
            params = action.get("params", {})
            
            if action_type == "avoid_assignment":
                alternatives = params.get("alternative_periods", [])
                if alternatives:
                    alt_day, alt_period = alternatives[0]
                    return (f"Move {current.subject} from ({day}, {period}) to "
                           f"({alt_day}, {alt_period}) for {class_id} "
                           f"(violation probability: {self.violation_probability.get(strategy.pattern_id, 0):.2f})")
            
            elif action_type == "use_alternative_teacher":
                return (f"Consider using a different teacher for {current.subject} "
                       f"at ({day}, {period}) for {class_id}")
            
            elif action_type == "swap_to_allowed_subject":
                return (f"Ensure parent class has Math/English when {class_id} "
                       f"has Jiritsu at ({day}, {period})")
        
        return None
    
    def update_strategy_result(self, strategy_id: str, success: bool) -> None:
        """戦略の結果を更新"""
        if strategy_id in self.state.strategy_database:
            strategy = self.state.strategy_database[strategy_id]
            if success:
                strategy.success_count += 1
                self.state.avoided_violations += 1
            else:
                strategy.failure_count += 1
            
            # データを保存
            self._save_data()
    
    def get_learning_report(self) -> Dict[str, Any]:
        """学習レポートを生成"""
        stats = self.analyzer.get_statistics()
        
        # 高頻度パターン
        high_freq_patterns = self.analyzer.get_high_frequency_patterns(min_frequency=3)
        
        # 効果的な戦略
        effective_strategies = [
            s for s in self.state.strategy_database.values()
            if s.success_rate > 0.7 and s.success_count >= 5
        ]
        effective_strategies.sort(key=lambda s: s.success_rate, reverse=True)
        
        report = {
            "summary": {
                "generation_count": self.state.generation_count,
                "total_violations": self.state.total_violations,
                "avoided_violations": self.state.avoided_violations,
                "avoidance_rate": self.state.avoided_violations / max(self.state.total_violations, 1),
                "unique_patterns": len(self.state.pattern_database),
                "active_strategies": len(self.state.strategy_database)
            },
            "statistics": stats,
            "high_frequency_patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "frequency": p.frequency,
                    "confidence": p.confidence_score,
                    "description": self._describe_pattern(p)
                }
                for p in high_freq_patterns[:10]
            ],
            "effective_strategies": [
                {
                    "strategy_id": s.strategy_id,
                    "description": s.description,
                    "success_rate": s.success_rate,
                    "usage_count": s.success_count + s.failure_count
                }
                for s in effective_strategies[:10]
            ],
            "recent_trends": self._analyze_recent_trends()
        }
        
        return report
    
    def _describe_pattern(self, pattern: ViolationPattern) -> str:
        """パターンを人間が読みやすい形で説明"""
        if not pattern.features:
            return "Unknown pattern"
        
        feature = pattern.features[0]
        desc_parts = [
            f"{feature.violation_type} violation",
            f"at day {feature.day + 1}, period {feature.period + 1}",
            f"for class {feature.class_id}"
        ]
        
        if feature.subject:
            desc_parts.append(f"subject: {feature.subject}")
        
        if feature.teacher:
            desc_parts.append(f"teacher: {feature.teacher}")
        
        return ", ".join(desc_parts)
    
    def _analyze_recent_trends(self) -> Dict[str, Any]:
        """最近のトレンドを分析"""
        if len(self.state.generation_history) < 10:
            return {"message": "Not enough data for trend analysis"}
        
        recent_history = self.state.generation_history[-10:]
        
        # 違反数の推移
        violation_counts = [h["violations"] for h in recent_history]
        
        # トレンド計算（簡単な線形回帰）
        x = np.arange(len(violation_counts))
        y = np.array(violation_counts)
        
        if len(x) > 1:
            slope = np.polyfit(x, y, 1)[0]
            trend = "improving" if slope < -0.1 else "worsening" if slope > 0.1 else "stable"
        else:
            trend = "unknown"
        
        return {
            "trend": trend,
            "recent_violations": violation_counts,
            "average_violations": np.mean(violation_counts),
            "min_violations": np.min(violation_counts),
            "max_violations": np.max(violation_counts)
        }
    
    def visualize_patterns(self) -> str:
        """パターンの可視化（簡易テキストベース）"""
        output = []
        output.append("=" * 60)
        output.append("CONSTRAINT VIOLATION PATTERNS VISUALIZATION")
        output.append("=" * 60)
        
        # 時間帯ヒートマップ
        output.append("\n[Time-based Violation Heatmap]")
        time_dist = self.analyzer._get_time_distribution()
        
        output.append("   Period: 1  2  3  4  5  6")
        for day in range(5):
            day_key = f"day_{day}"
            day_name = ["Mon", "Tue", "Wed", "Thu", "Fri"][day]
            counts = []
            
            for period in range(6):
                count = time_dist.get(day_key, {}).get(period, 0)
                counts.append(str(count).rjust(2))
            
            output.append(f"{day_name}: {' '.join(counts)}")
        
        # 違反タイプ分布
        output.append("\n[Violation Type Distribution]")
        type_dist = self.analyzer.get_statistics()["violation_types"]
        
        for vtype, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True)[:10]:
            bar = "#" * min(count, 50)
            output.append(f"{vtype:30s} {bar} ({count})")
        
        return "\n".join(output)