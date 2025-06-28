"""
Ultrathink学習システム統合アダプター

制約違反学習システムを既存のスケジュール生成システムと統合するためのアダプター。
生成プロセスの前後で学習システムと連携し、制約違反の予防と学習を実現する。
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from src.domain.entities import Schedule, School
from src.domain.constraints.base import ConstraintViolation
from .ultrathink.constraint_violation_learning_system import ConstraintViolationLearningSystem
from src.infrastructure.config import PathConfig


logger = logging.getLogger(__name__)


class UltrathinkLearningAdapter:
    """Ultrathink学習システムの統合アダプター"""
    
    def __init__(self, learning_dir: Optional[str] = None):
        """
        Args:
            learning_dir: 学習データの保存ディレクトリ（デフォルト: data/learning）
        """
        self.learning_system = ConstraintViolationLearningSystem(learning_dir)
        self.active_strategies: Dict[str, Any] = {}
        self.generation_start_time: Optional[datetime] = None
        self.pre_generation_violations: int = 0
        
    def pre_generation_analysis(self, schedule: Schedule, school: School) -> Dict[str, Any]:
        """生成前の分析と予防的回避戦略の適用
        
        Args:
            schedule: 現在のスケジュール
            school: 学校データ
            
        Returns:
            分析結果と適用された戦略の情報
        """
        logger.info("Starting pre-generation analysis with Ultrathink learning system")
        self.generation_start_time = datetime.now()
        
        # 違反予測と回避提案を取得
        suggestions = self.learning_system.apply_learning_to_schedule(
            schedule, school, self._pre_check_callback
        )
        
        # 高リスクな配置を特定
        high_risk_slots = []
        for day in range(5):
            for period in range(6):
                for class_info in school.classes.values():
                    class_id = class_info.id
                    current = schedule.get_assignment(day, period, class_id)
                    
                    if current and current.subject:
                        violation_prob = self.learning_system.predict_violations(
                            day, period, class_id,
                            current.subject, current.teacher
                        )
                        
                        if violation_prob > 0.5:  # 50%以上の違反確率
                            high_risk_slots.append({
                                "day": day,
                                "period": period,
                                "class_id": class_id,
                                "subject": current.subject,
                                "teacher": current.teacher,
                                "probability": violation_prob
                            })
        
        # 回避戦略を取得
        for slot in high_risk_slots:
            strategies = self.learning_system.get_avoidance_strategies(
                slot["day"], slot["period"], slot["class_id"],
                slot["subject"], slot["teacher"]
            )
            
            if strategies:
                key = f"{slot['day']}_{slot['period']}_{slot['class_id']}"
                self.active_strategies[key] = strategies[0]  # 最高優先度の戦略を保存
        
        result = {
            "suggestions": suggestions,
            "high_risk_slots": high_risk_slots,
            "active_strategies": len(self.active_strategies),
            "total_patterns": len(self.learning_system.state.pattern_database),
            "learning_generation": self.learning_system.state.generation_count
        }
        
        logger.info(f"Pre-generation analysis complete: {len(high_risk_slots)} high-risk slots identified")
        
        return result
    
    def _pre_check_callback(self, day: int, period: int, class_id: str, 
                           strategy: Any) -> None:
        """事前チェックのコールバック関数"""
        logger.debug(f"Applying strategy {strategy.strategy_id} for {class_id} at ({day}, {period})")
    
    def post_generation_learning(self, violations: List[ConstraintViolation],
                               schedule: Schedule, school: School) -> Dict[str, Any]:
        """生成後の学習と戦略評価
        
        Args:
            violations: 発生した制約違反のリスト
            schedule: 生成されたスケジュール
            school: 学校データ
            
        Returns:
            学習結果と統計情報
        """
        logger.info(f"Starting post-generation learning with {len(violations)} violations")
        
        # 違反から学習
        self.learning_system.learn_from_violations(violations, schedule, school)
        
        # アクティブな戦略の効果を評価
        for key, strategy in self.active_strategies.items():
            # keyから情報を抽出
            parts = key.split("_")
            day, period, class_id = int(parts[0]), int(parts[1]), parts[2]
            
            # この位置で違反が発生したかチェック
            violation_at_position = any(
                v.details.get("day") == day and
                v.details.get("period") == period and
                v.details.get("class_id") == class_id
                for v in violations
            )
            
            # 戦略の成功/失敗を記録
            success = not violation_at_position
            self.learning_system.update_strategy_result(strategy.strategy_id, success)
        
        # 学習レポートを生成
        report = self.learning_system.get_learning_report()
        
        # 生成時間を計算
        generation_time = (datetime.now() - self.generation_start_time).total_seconds()
        
        result = {
            "violations_learned": len(violations),
            "generation_time": generation_time,
            "strategy_effectiveness": self._calculate_strategy_effectiveness(),
            "learning_report": report,
            "improvement_rate": self._calculate_improvement_rate(len(violations))
        }
        
        # アクティブな戦略をクリア
        self.active_strategies.clear()
        
        logger.info(f"Post-generation learning complete. Improvement rate: {result['improvement_rate']:.2%}")
        
        return result
    
    def _calculate_strategy_effectiveness(self) -> float:
        """戦略の効果を計算"""
        if not self.active_strategies:
            return 0.0
        
        effective_count = 0
        for strategy in self.learning_system.state.strategy_database.values():
            if strategy.success_rate > 0.5 and strategy.success_count > 0:
                effective_count += 1
        
        total = len(self.learning_system.state.strategy_database)
        return effective_count / total if total > 0 else 0.0
    
    def _calculate_improvement_rate(self, current_violations: int) -> float:
        """改善率を計算"""
        history = self.learning_system.state.generation_history
        if len(history) < 2:
            return 0.0
        
        # 過去5世代の平均違反数
        recent_history = history[-6:-1] if len(history) > 5 else history[:-1]
        if not recent_history:
            return 0.0
            
        avg_past_violations = sum(h["violations"] for h in recent_history) / len(recent_history)
        
        if avg_past_violations == 0:
            return 0.0
        
        improvement = (avg_past_violations - current_violations) / avg_past_violations
        return max(0.0, improvement)  # 負の改善率は0とする
    
    def get_violation_heatmap(self) -> str:
        """違反のヒートマップを取得"""
        return self.learning_system.visualize_patterns()
    
    def get_suggested_constraints(self) -> List[Dict[str, Any]]:
        """学習結果から推奨される新しい制約を生成
        
        Returns:
            推奨制約のリスト
        """
        suggestions = []
        
        # 高頻度パターンから制約を提案
        high_freq_patterns = self.learning_system.analyzer.get_high_frequency_patterns(min_frequency=5)
        
        for pattern in high_freq_patterns[:5]:  # 上位5パターン
            if pattern.confidence_score > 0.7:  # 信頼度70%以上
                suggestion = self._pattern_to_constraint_suggestion(pattern)
                if suggestion:
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _pattern_to_constraint_suggestion(self, pattern: Any) -> Optional[Dict[str, Any]]:
        """パターンから制約の提案を生成"""
        if not pattern.features:
            return None
        
        feature = pattern.features[0]
        
        suggestion = {
            "type": "learned_constraint",
            "pattern_id": pattern.pattern_id,
            "frequency": pattern.frequency,
            "confidence": pattern.confidence_score,
            "description": None,
            "constraint_params": {}
        }
        
        # 違反タイプに応じた制約を提案
        if feature.violation_type == "TeacherConflict":
            suggestion["description"] = (
                f"Avoid assigning {feature.teacher} to multiple classes "
                f"at day {feature.day + 1}, period {feature.period + 1}"
            )
            suggestion["constraint_params"] = {
                "teacher": feature.teacher,
                "day": feature.day,
                "period": feature.period
            }
        
        elif feature.violation_type == "DailyDuplicate":
            suggestion["description"] = (
                f"Restrict {feature.subject} to once per day for {feature.class_id}"
            )
            suggestion["constraint_params"] = {
                "subject": feature.subject,
                "class_id": feature.class_id
            }
        
        elif "jiritsu" in feature.violation_type.lower():
            suggestion["description"] = (
                f"Ensure parent class has Math/English when {feature.class_id} has Jiritsu"
            )
            suggestion["constraint_params"] = {
                "exchange_class": feature.class_id,
                "required_subjects": ["数学", "英語", "数", "英"]
            }
        
        else:
            return None
        
        return suggestion
    
    def export_learning_data(self, filepath: Optional[str] = None) -> str:
        """学習データをエクスポート
        
        Args:
            filepath: エクスポート先のファイルパス
            
        Returns:
            実際にエクスポートされたファイルパス
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"data/learning/export_{timestamp}.json"
        
        self.learning_system.analyzer.export_patterns(filepath)
        logger.info(f"Learning data exported to {filepath}")
        
        return filepath
    
    def import_learning_data(self, filepath: str) -> Dict[str, Any]:
        """学習データをインポート
        
        Args:
            filepath: インポート元のファイルパス
            
        Returns:
            インポート結果の統計情報
        """
        before_patterns = len(self.learning_system.state.pattern_database)
        
        self.learning_system.analyzer.import_patterns(filepath)
        
        after_patterns = len(self.learning_system.state.pattern_database)
        
        result = {
            "imported_patterns": after_patterns - before_patterns,
            "total_patterns": after_patterns,
            "source_file": filepath
        }
        
        logger.info(f"Learning data imported from {filepath}: {result['imported_patterns']} new patterns")
        
        return result