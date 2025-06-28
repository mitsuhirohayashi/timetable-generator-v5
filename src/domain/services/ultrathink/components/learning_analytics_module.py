"""
学習・分析モジュール

過去の生成結果から学習し、パターン認識・予測・最適化パラメータの自動調整を行う。
"""
import logging
import json
import os
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import numpy as np
from pathlib import Path

from ....entities.schedule import Schedule
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class ViolationPattern:
    """違反パターン"""
    type: str
    context: Dict[str, Any]
    frequency: int = 1
    solutions: List[Dict[str, Any]] = field(default_factory=list)
    success_rate: float = 0.0


@dataclass
class SuccessPattern:
    """成功パターン"""
    context: Dict[str, Any]
    strategy: str
    parameters: Dict[str, Any]
    score: float
    execution_time: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LearningData:
    """学習データ"""
    violation_patterns: Dict[str, ViolationPattern] = field(default_factory=dict)
    success_patterns: List[SuccessPattern] = field(default_factory=list)
    parameter_performance: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    generation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 統計情報
    total_generations: int = 0
    successful_generations: int = 0
    average_execution_time: float = 0.0
    common_violations: Counter = field(default_factory=Counter)


class LearningAnalyticsModule(LoggingMixin):
    """学習・分析モジュール"""
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        pattern_threshold: float = 0.7,
        data_dir: Optional[str] = None
    ):
        super().__init__()
        self.learning_rate = learning_rate
        self.pattern_threshold = pattern_threshold
        
        # データディレクトリ
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(__file__), "..", "learning_data"
        )
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # 学習データ
        self.learning_data = self._load_learning_data()
        
        # 実行時キャッシュ
        self.pattern_cache = {}
        self.prediction_cache = {}
    
    def analyze_generation_result(
        self,
        schedule: Schedule,
        school: School,
        violations: List[Any],
        execution_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成結果を分析"""
        self.logger.info("生成結果の分析を開始")
        
        # 基本統計の更新
        self.learning_data.total_generations += 1
        if len(violations) == 0:
            self.learning_data.successful_generations += 1
        
        # 実行時間の更新
        execution_time = execution_context.get('execution_time', 0)
        self._update_average_execution_time(execution_time)
        
        # 違反パターンの分析
        violation_analysis = self._analyze_violations(violations, execution_context)
        
        # 成功パターンの記録
        if len(violations) == 0:
            self._record_success_pattern(execution_context)
        
        # パラメータパフォーマンスの更新
        self._update_parameter_performance(execution_context, violations)
        
        # 予測と推奨
        predictions = self._make_predictions(school, execution_context)
        recommendations = self._generate_recommendations(violation_analysis, predictions)
        
        # 履歴に追加
        self._add_to_history(schedule, violations, execution_context)
        
        # 定期的な保存
        if self.learning_data.total_generations % 10 == 0:
            self._save_learning_data()
        
        return {
            'violation_analysis': violation_analysis,
            'predictions': predictions,
            'recommendations': recommendations,
            'learning_stats': self._get_learning_statistics()
        }
    
    def predict_difficulty(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成の難易度を予測"""
        # キャッシュチェック
        cache_key = self._get_prediction_cache_key(school, context)
        if cache_key in self.prediction_cache:
            return self.prediction_cache[cache_key]
        
        predictions = {
            'estimated_time': self._predict_execution_time(school, context),
            'violation_risk': self._predict_violation_risk(school, context),
            'recommended_strategy': self._recommend_strategy(school, context),
            'parameter_suggestions': self._suggest_parameters(school, context)
        }
        
        # キャッシュに保存
        self.prediction_cache[cache_key] = predictions
        
        return predictions
    
    def get_violation_solutions(
        self,
        violation_type: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """違反に対する解決策を取得"""
        pattern_key = self._get_pattern_key(violation_type, context)
        
        if pattern_key in self.learning_data.violation_patterns:
            pattern = self.learning_data.violation_patterns[pattern_key]
            # 成功率の高い順にソート
            return sorted(
                pattern.solutions,
                key=lambda s: s.get('success_rate', 0),
                reverse=True
            )
        
        return []
    
    def update_solution_feedback(
        self,
        violation_type: str,
        context: Dict[str, Any],
        solution: Dict[str, Any],
        success: bool
    ):
        """解決策のフィードバックを更新"""
        pattern_key = self._get_pattern_key(violation_type, context)
        
        if pattern_key in self.learning_data.violation_patterns:
            pattern = self.learning_data.violation_patterns[pattern_key]
            
            # 解決策を更新
            for sol in pattern.solutions:
                if sol.get('id') == solution.get('id'):
                    sol['attempts'] = sol.get('attempts', 0) + 1
                    if success:
                        sol['successes'] = sol.get('successes', 0) + 1
                    sol['success_rate'] = sol['successes'] / sol['attempts']
                    break
            
            # パターンの成功率も更新
            total_attempts = sum(s.get('attempts', 0) for s in pattern.solutions)
            total_successes = sum(s.get('successes', 0) for s in pattern.solutions)
            pattern.success_rate = total_successes / total_attempts if total_attempts > 0 else 0
    
    def _analyze_violations(
        self,
        violations: List[Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """違反を分析"""
        violation_types = Counter()
        patterns = []
        
        for violation in violations:
            violation_type = violation.type if hasattr(violation, 'type') else str(type(violation))
            violation_types[violation_type] += 1
            
            # パターンの抽出
            pattern_context = self._extract_pattern_context(violation, context)
            pattern_key = self._get_pattern_key(violation_type, pattern_context)
            
            # パターンの更新または作成
            if pattern_key not in self.learning_data.violation_patterns:
                self.learning_data.violation_patterns[pattern_key] = ViolationPattern(
                    type=violation_type,
                    context=pattern_context
                )
            else:
                self.learning_data.violation_patterns[pattern_key].frequency += 1
            
            patterns.append(pattern_key)
        
        # 共通違反の更新
        self.learning_data.common_violations.update(violation_types)
        
        return {
            'violation_counts': dict(violation_types),
            'patterns': patterns,
            'most_common': violation_types.most_common(5),
            'new_patterns': len([p for p in patterns if 
                               self.learning_data.violation_patterns[p].frequency == 1])
        }
    
    def _record_success_pattern(self, context: Dict[str, Any]):
        """成功パターンを記録"""
        success_pattern = SuccessPattern(
            context=self._extract_success_context(context),
            strategy=context.get('strategy', 'unknown'),
            parameters=context.get('parameters', {}),
            score=context.get('score', 0),
            execution_time=context.get('execution_time', 0)
        )
        
        self.learning_data.success_patterns.append(success_pattern)
        
        # 古いパターンを削除（最新1000件のみ保持）
        if len(self.learning_data.success_patterns) > 1000:
            self.learning_data.success_patterns = self.learning_data.success_patterns[-1000:]
    
    def _update_parameter_performance(
        self,
        context: Dict[str, Any],
        violations: List[Any]
    ):
        """パラメータパフォーマンスを更新"""
        parameters = context.get('parameters', {})
        performance_score = self._calculate_performance_score(violations, context)
        
        for param_name, param_value in parameters.items():
            key = f"{param_name}={param_value}"
            self.learning_data.parameter_performance[key].append(performance_score)
            
            # 古いデータを削除（最新100件のみ保持）
            if len(self.learning_data.parameter_performance[key]) > 100:
                self.learning_data.parameter_performance[key] = \
                    self.learning_data.parameter_performance[key][-100:]
    
    def _make_predictions(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """予測を生成"""
        # 類似した過去の生成を探す
        similar_generations = self._find_similar_generations(school, context)
        
        if not similar_generations:
            return {
                'confidence': 'low',
                'expected_violations': 'unknown',
                'expected_time': self.learning_data.average_execution_time
            }
        
        # 統計を計算
        violation_counts = [g['violations'] for g in similar_generations]
        execution_times = [g['execution_time'] for g in similar_generations]
        
        return {
            'confidence': 'high' if len(similar_generations) > 10 else 'medium',
            'expected_violations': np.mean(violation_counts),
            'expected_time': np.mean(execution_times),
            'violation_std': np.std(violation_counts),
            'similar_cases': len(similar_generations)
        }
    
    def _generate_recommendations(
        self,
        violation_analysis: Dict[str, Any],
        predictions: Dict[str, Any]
    ) -> List[str]:
        """推奨事項を生成"""
        recommendations = []
        
        # 違反パターンに基づく推奨
        for violation_type, count in violation_analysis['most_common']:
            if count > 5:
                recommendations.append(
                    f"{violation_type}が{count}件発生。"
                    f"この違反を優先的に解決することを推奨"
                )
        
        # 予測に基づく推奨
        if predictions['confidence'] in ['high', 'medium']:
            expected_violations = predictions['expected_violations']
            if expected_violations > 10:
                recommendations.append(
                    f"過去の類似ケースでは平均{expected_violations:.1f}件の違反が発生。"
                    f"より強力な最適化戦略の使用を推奨"
                )
        
        # パラメータ調整の推奨
        poor_params = self._identify_poor_parameters()
        if poor_params:
            recommendations.append(
                f"パラメータ {', '.join(poor_params)} の性能が低い。"
                f"値の調整を推奨"
            )
        
        return recommendations
    
    def _predict_execution_time(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> float:
        """実行時間を予測"""
        # 学校規模に基づく基本予測
        total_slots = len(school.get_all_classes()) * 30
        base_time = total_slots * 0.01  # スロットあたり0.01秒
        
        # 戦略による調整
        strategy = context.get('strategy', 'unknown')
        strategy_multipliers = {
            'BeamSearch': 1.5,
            'LocalSearch': 1.0,
            'SimulatedAnnealing': 2.0
        }
        multiplier = strategy_multipliers.get(strategy, 1.2)
        
        # 過去の実績による調整
        if self.learning_data.average_execution_time > 0:
            return self.learning_data.average_execution_time * multiplier
        
        return base_time * multiplier
    
    def _predict_violation_risk(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> Dict[str, float]:
        """違反リスクを予測"""
        risks = {}
        
        # 各違反タイプのリスクを計算
        total_generations = self.learning_data.total_generations or 1
        
        for violation_type, count in self.learning_data.common_violations.most_common():
            frequency = count / total_generations
            risks[violation_type] = min(frequency * 1.5, 1.0)  # 最大100%
        
        return risks
    
    def _recommend_strategy(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> str:
        """戦略を推奨"""
        # 成功パターンから最適な戦略を選択
        strategy_scores = defaultdict(list)
        
        for pattern in self.learning_data.success_patterns[-100:]:  # 最新100件
            if self._is_similar_context(pattern.context, context):
                strategy_scores[pattern.strategy].append(pattern.score)
        
        # 平均スコアが最も高い戦略を選択
        best_strategy = 'BeamSearch'  # デフォルト
        best_score = 0
        
        for strategy, scores in strategy_scores.items():
            avg_score = np.mean(scores)
            if avg_score > best_score:
                best_strategy = strategy
                best_score = avg_score
        
        return best_strategy
    
    def _suggest_parameters(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """パラメータを提案"""
        suggestions = {}
        
        # パフォーマンスデータから最適値を推定
        for param_key, scores in self.learning_data.parameter_performance.items():
            if '=' in param_key and len(scores) >= 5:
                param_name, param_value = param_key.split('=', 1)
                avg_score = np.mean(scores)
                
                # 現在の値より良いスコアの値を探す
                current_score = context.get('parameters', {}).get(param_name, 0)
                if avg_score > current_score:
                    try:
                        suggestions[param_name] = eval(param_value)
                    except:
                        suggestions[param_name] = param_value
        
        return suggestions
    
    def _extract_pattern_context(
        self,
        violation: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """パターンコンテキストを抽出"""
        pattern_context = {
            'school_size': context.get('school_size', 'unknown'),
            'time_of_day': context.get('time_of_day', 'unknown'),
            'day_of_week': context.get('day_of_week', 'unknown')
        }
        
        # 違反固有の情報を追加
        if hasattr(violation, 'details'):
            pattern_context.update(violation.details)
        
        return pattern_context
    
    def _extract_success_context(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """成功コンテキストを抽出"""
        return {
            'school_size': context.get('school_size', 'unknown'),
            'optimization_level': context.get('optimization_level', 'unknown'),
            'initial_violations': context.get('initial_violations', 0),
            'time_limit': context.get('time_limit', 0)
        }
    
    def _get_pattern_key(
        self,
        violation_type: str,
        context: Dict[str, Any]
    ) -> str:
        """パターンキーを生成"""
        context_str = json.dumps(context, sort_keys=True)
        return f"{violation_type}:{hash(context_str)}"
    
    def _get_prediction_cache_key(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> str:
        """予測キャッシュキーを生成"""
        school_key = f"{len(school.get_all_classes())}_{len(school.get_all_teachers())}"
        context_key = json.dumps(context, sort_keys=True)
        return f"{school_key}:{hash(context_key)}"
    
    def _update_average_execution_time(self, execution_time: float):
        """平均実行時間を更新"""
        n = self.learning_data.total_generations
        current_avg = self.learning_data.average_execution_time
        self.learning_data.average_execution_time = (
            (current_avg * (n - 1) + execution_time) / n
        )
    
    def _calculate_performance_score(
        self,
        violations: List[Any],
        context: Dict[str, Any]
    ) -> float:
        """パフォーマンススコアを計算"""
        # 違反が少ないほど高スコア
        violation_penalty = len(violations) * 10
        
        # 実行時間が短いほど高スコア
        execution_time = context.get('execution_time', 100)
        time_penalty = execution_time / 10
        
        # 基本スコア100から減算
        return max(0, 100 - violation_penalty - time_penalty)
    
    def _find_similar_generations(
        self,
        school: School,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """類似した過去の生成を探す"""
        similar = []
        
        school_size = len(school.get_all_classes())
        
        for generation in self.learning_data.generation_history[-100:]:  # 最新100件
            if abs(generation.get('school_size', 0) - school_size) <= 3:
                if self._is_similar_context(generation.get('context', {}), context):
                    similar.append(generation)
        
        return similar
    
    def _is_similar_context(
        self,
        context1: Dict[str, Any],
        context2: Dict[str, Any]
    ) -> bool:
        """コンテキストが類似しているか判定"""
        # 重要なキーで比較
        important_keys = ['optimization_level', 'strategy', 'time_limit']
        
        for key in important_keys:
            if context1.get(key) != context2.get(key):
                return False
        
        return True
    
    def _identify_poor_parameters(self) -> List[str]:
        """性能の悪いパラメータを特定"""
        poor_params = []
        
        for param_key, scores in self.learning_data.parameter_performance.items():
            if len(scores) >= 10:
                avg_score = np.mean(scores)
                if avg_score < 30:  # スコア30未満は低性能
                    poor_params.append(param_key)
        
        return poor_params
    
    def _add_to_history(
        self,
        schedule: Schedule,
        violations: List[Any],
        context: Dict[str, Any]
    ):
        """履歴に追加"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'school_size': context.get('school_size', 0),
            'violations': len(violations),
            'execution_time': context.get('execution_time', 0),
            'strategy': context.get('strategy', 'unknown'),
            'parameters': context.get('parameters', {}),
            'context': context
        }
        
        self.learning_data.generation_history.append(history_entry)
        
        # 古い履歴を削除（最新1000件のみ保持）
        if len(self.learning_data.generation_history) > 1000:
            self.learning_data.generation_history = \
                self.learning_data.generation_history[-1000:]
    
    def _get_learning_statistics(self) -> Dict[str, Any]:
        """学習統計を取得"""
        success_rate = (
            self.learning_data.successful_generations / 
            self.learning_data.total_generations * 100
            if self.learning_data.total_generations > 0 else 0
        )
        
        return {
            'total_generations': self.learning_data.total_generations,
            'success_rate': success_rate,
            'average_execution_time': self.learning_data.average_execution_time,
            'violation_patterns': len(self.learning_data.violation_patterns),
            'success_patterns': len(self.learning_data.success_patterns),
            'most_common_violations': self.learning_data.common_violations.most_common(5)
        }
    
    def _save_learning_data(self):
        """学習データを保存"""
        try:
            file_path = os.path.join(self.data_dir, 'learning_data.json')
            
            # データを辞書に変換
            data_dict = {
                'violation_patterns': {
                    k: asdict(v) for k, v in self.learning_data.violation_patterns.items()
                },
                'success_patterns': [
                    asdict(p) for p in self.learning_data.success_patterns[-100:]
                ],
                'parameter_performance': dict(self.learning_data.parameter_performance),
                'generation_history': self.learning_data.generation_history[-100:],
                'statistics': {
                    'total_generations': self.learning_data.total_generations,
                    'successful_generations': self.learning_data.successful_generations,
                    'average_execution_time': self.learning_data.average_execution_time,
                    'common_violations': dict(self.learning_data.common_violations.most_common(20))
                }
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)
            
            self.logger.debug("学習データを保存しました")
            
        except Exception as e:
            self.logger.error(f"学習データの保存に失敗: {e}")
    
    def _load_learning_data(self) -> LearningData:
        """学習データを読み込む"""
        try:
            file_path = os.path.join(self.data_dir, 'learning_data.json')
            
            if not os.path.exists(file_path):
                return LearningData()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data_dict = json.load(f)
            
            # LearningDataオブジェクトを再構築
            learning_data = LearningData()
            
            # 違反パターンの復元
            for key, pattern_dict in data_dict.get('violation_patterns', {}).items():
                learning_data.violation_patterns[key] = ViolationPattern(**pattern_dict)
            
            # 成功パターンの復元
            for pattern_dict in data_dict.get('success_patterns', []):
                # datetimeの復元
                if 'timestamp' in pattern_dict:
                    pattern_dict['timestamp'] = datetime.fromisoformat(pattern_dict['timestamp'])
                learning_data.success_patterns.append(SuccessPattern(**pattern_dict))
            
            # その他のデータの復元
            learning_data.parameter_performance = defaultdict(
                list,
                data_dict.get('parameter_performance', {})
            )
            learning_data.generation_history = data_dict.get('generation_history', [])
            
            # 統計情報の復元
            stats = data_dict.get('statistics', {})
            learning_data.total_generations = stats.get('total_generations', 0)
            learning_data.successful_generations = stats.get('successful_generations', 0)
            learning_data.average_execution_time = stats.get('average_execution_time', 0.0)
            learning_data.common_violations = Counter(stats.get('common_violations', {}))
            
            self.logger.info("学習データを読み込みました")
            return learning_data
            
        except Exception as e:
            self.logger.error(f"学習データの読み込みに失敗: {e}")
            return LearningData()