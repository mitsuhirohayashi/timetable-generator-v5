"""
制約違反パターン学習コンポーネント

過去の制約違反を分析し、同じ失敗を繰り返さないように学習します。
ハイブリッド生成器V6の機能を抽出・改良したものです。
"""
import logging
import json
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.ensemble import RandomForestClassifier
import pickle

from ....entities.schedule import Schedule
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class ViolationPattern:
    """制約違反パターン"""
    pattern_id: str
    violation_type: str
    
    # パターンの特徴
    features: Dict[str, Any] = field(default_factory=dict)
    
    # 発生コンテキスト
    time_context: Optional[str] = None  # 朝、昼、午後など
    day_context: Optional[str] = None   # 曜日
    class_context: Optional[str] = None # クラスタイプ（通常、5組、交流など）
    
    # 統計
    occurrence_count: int = 0
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    # 解決策
    suggested_fixes: List[str] = field(default_factory=list)
    success_rate: float = 0.0


@dataclass
class ViolationInstance:
    """制約違反インスタンス"""
    violation_type: str
    time_slot: TimeSlot
    class_ref: ClassReference
    details: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LearningResult:
    """学習結果"""
    patterns_found: int
    high_risk_slots: List[Tuple[TimeSlot, ClassReference, float]]  # (slot, class, risk_score)
    preventive_rules: List[Dict[str, Any]]
    confidence: float


class ViolationPatternLearner(LoggingMixin):
    """制約違反パターン学習器"""
    
    def __init__(
        self,
        history_file: Optional[str] = None,
        model_file: Optional[str] = None,
        min_pattern_occurrences: int = 3
    ):
        super().__init__()
        self.violation_history: List[ViolationInstance] = []
        self.patterns: Dict[str, ViolationPattern] = {}
        self.min_pattern_occurrences = min_pattern_occurrences
        
        # 機械学習モデル
        self.vectorizer = DictVectorizer()
        self.risk_predictor = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.model_trained = False
        
        # 履歴とモデルをロード
        if history_file and Path(history_file).exists():
            self.load_history(history_file)
        if model_file and Path(model_file).exists():
            self.load_model(model_file)
        
        # 統計
        self.stats = {
            'violations_recorded': 0,
            'patterns_discovered': 0,
            'predictions_made': 0,
            'violations_prevented': 0
        }
    
    def record_violation(
        self,
        violation_type: str,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        details: Dict[str, Any]
    ):
        """制約違反を記録"""
        instance = ViolationInstance(
            violation_type=violation_type,
            time_slot=time_slot,
            class_ref=class_ref,
            details=details
        )
        
        self.violation_history.append(instance)
        self.stats['violations_recorded'] += 1
        
        # パターンを更新
        self._update_patterns(instance)
    
    def _update_patterns(self, instance: ViolationInstance):
        """違反パターンを更新"""
        # 特徴を抽出
        features = self._extract_features(instance)
        pattern_key = self._generate_pattern_key(features)
        
        if pattern_key not in self.patterns:
            # 新しいパターン
            pattern = ViolationPattern(
                pattern_id=pattern_key,
                violation_type=instance.violation_type,
                features=features,
                time_context=self._get_time_context(instance.time_slot),
                day_context=instance.time_slot.day,
                class_context=self._get_class_context(instance.class_ref)
            )
            self.patterns[pattern_key] = pattern
            self.stats['patterns_discovered'] += 1
        else:
            # 既存パターンを更新
            pattern = self.patterns[pattern_key]
            pattern.occurrence_count += 1
            pattern.last_seen = instance.timestamp
    
    def _extract_features(self, instance: ViolationInstance) -> Dict[str, Any]:
        """違反インスタンスから特徴を抽出"""
        features = {
            'violation_type': instance.violation_type,
            'day': instance.time_slot.day,
            'period': instance.time_slot.period,
            'grade': instance.class_ref.grade,
            'class_number': instance.class_ref.class_number,
            'is_morning': instance.time_slot.period <= 3,
            'is_edge_period': instance.time_slot.period in [1, 6],
            'is_monday': instance.time_slot.day == "月",
            'is_friday': instance.time_slot.day == "金"
        }
        
        # 詳細情報を追加
        features.update(instance.details)
        
        return features
    
    def _generate_pattern_key(self, features: Dict[str, Any]) -> str:
        """パターンキーを生成"""
        # 重要な特徴のみを使用
        key_parts = [
            features['violation_type'],
            f"period_{features['period']}",
            f"grade_{features['grade']}"
        ]
        
        if features.get('is_morning'):
            key_parts.append('morning')
        if features.get('is_edge_period'):
            key_parts.append('edge')
            
        return '_'.join(key_parts)
    
    def _get_time_context(self, time_slot: TimeSlot) -> str:
        """時間帯コンテキストを取得"""
        if time_slot.period <= 2:
            return "朝"
        elif time_slot.period <= 4:
            return "昼"
        else:
            return "午後"
    
    def _get_class_context(self, class_ref: ClassReference) -> str:
        """クラスコンテキストを取得"""
        if class_ref.class_number == 5:
            return "5組"
        elif class_ref.class_number >= 6:
            return "交流学級"
        else:
            return "通常学級"
    
    def analyze_patterns(self) -> List[ViolationPattern]:
        """頻出パターンを分析"""
        frequent_patterns = [
            pattern for pattern in self.patterns.values()
            if pattern.occurrence_count >= self.min_pattern_occurrences
        ]
        
        # 発生頻度でソート
        frequent_patterns.sort(key=lambda p: p.occurrence_count, reverse=True)
        
        # 解決策を生成
        for pattern in frequent_patterns:
            pattern.suggested_fixes = self._generate_fixes(pattern)
        
        return frequent_patterns
    
    def _generate_fixes(self, pattern: ViolationPattern) -> List[str]:
        """パターンに対する解決策を生成"""
        fixes = []
        
        if pattern.violation_type == "teacher_conflict":
            fixes.append("該当時間帯の教師割り当てを事前チェック")
            fixes.append("代替教師リストを準備")
            
        elif pattern.violation_type == "daily_duplicate":
            fixes.append("日内重複チェックを強化")
            if pattern.time_context == "午後":
                fixes.append("午後の科目配置を優先的に調整")
                
        elif pattern.violation_type == "exchange_class_sync":
            fixes.append("交流学級と親学級の同期を最初に確保")
            fixes.append("交流学級の自立活動時は親学級を数学/英語に固定")
            
        elif pattern.violation_type == "gym_usage":
            fixes.append("体育館使用スケジュールを事前に作成")
            fixes.append("体育の配置を他科目より先に行う")
        
        return fixes
    
    def train_risk_model(self):
        """リスク予測モデルを訓練"""
        if len(self.violation_history) < 50:
            self.logger.warning("訓練データが不足しています（最低50件必要）")
            return
        
        # 訓練データを準備
        X_data = []
        y_data = []
        
        # 全ての時間スロットとクラスの組み合わせを生成
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                for grade in range(1, 4):
                    for class_num in range(1, 8):
                        time_slot = TimeSlot(day, period)
                        class_ref = ClassReference(grade, class_num)
                        
                        # 特徴を抽出
                        features = {
                            'day_idx': days.index(day),
                            'period': period,
                            'grade': grade,
                            'class_number': class_num,
                            'is_morning': period <= 3,
                            'is_edge_period': period in [1, 6],
                            'is_monday': day == "月",
                            'is_friday': day == "金",
                            'is_5gumi': class_num == 5,
                            'is_exchange': class_num >= 6
                        }
                        
                        # この組み合わせでの違反回数をカウント
                        violation_count = sum(
                            1 for v in self.violation_history
                            if v.time_slot.day == day and 
                            v.time_slot.period == period and
                            v.class_ref.grade == grade and
                            v.class_ref.class_number == class_num
                        )
                        
                        X_data.append(features)
                        y_data.append(1 if violation_count > 0 else 0)
        
        # ベクトル化
        X = self.vectorizer.fit_transform(X_data)
        y = np.array(y_data)
        
        # モデルを訓練
        self.risk_predictor.fit(X, y)
        self.model_trained = True
        
        self.logger.info(f"リスク予測モデルを訓練しました（{len(X_data)}サンプル）")
    
    def predict_high_risk_slots(
        self,
        school: School,
        threshold: float = 0.7
    ) -> List[Tuple[TimeSlot, ClassReference, float]]:
        """高リスクのスロットを予測"""
        if not self.model_trained:
            self.logger.warning("モデルが訓練されていません")
            return []
        
        high_risk_slots = []
        days = ["月", "火", "水", "木", "金"]
        
        for class_obj in school.get_all_classes():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    class_ref = ClassReference(class_obj.grade, class_obj.class_number)
                    
                    # リスクスコアを予測
                    risk_score = self.predict_risk(time_slot, class_ref)
                    
                    if risk_score >= threshold:
                        high_risk_slots.append((time_slot, class_ref, risk_score))
        
        # リスクスコアでソート
        high_risk_slots.sort(key=lambda x: x[2], reverse=True)
        self.stats['predictions_made'] += len(high_risk_slots)
        
        return high_risk_slots
    
    def predict_risk(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> float:
        """特定のスロットのリスクスコアを予測"""
        if not self.model_trained:
            return 0.0
        
        features = {
            'day_idx': ["月", "火", "水", "木", "金"].index(time_slot.day),
            'period': time_slot.period,
            'grade': class_ref.grade,
            'class_number': class_ref.class_number,
            'is_morning': time_slot.period <= 3,
            'is_edge_period': time_slot.period in [1, 6],
            'is_monday': time_slot.day == "月",
            'is_friday': time_slot.day == "金",
            'is_5gumi': class_ref.class_number == 5,
            'is_exchange': class_ref.class_number >= 6
        }
        
        X = self.vectorizer.transform([features])
        
        # 確率を予測
        probabilities = self.risk_predictor.predict_proba(X)[0]
        risk_score = probabilities[1]  # 違反が発生する確率
        
        return risk_score
    
    def generate_preventive_rules(self) -> List[Dict[str, Any]]:
        """予防的ルールを生成"""
        rules = []
        
        # 頻出パターンから規則を生成
        patterns = self.analyze_patterns()
        
        for pattern in patterns[:10]:  # 上位10パターン
            rule = {
                'rule_id': f"prevent_{pattern.pattern_id}",
                'description': f"{pattern.violation_type}の予防",
                'condition': {
                    'time_context': pattern.time_context,
                    'day_context': pattern.day_context,
                    'class_context': pattern.class_context
                },
                'actions': pattern.suggested_fixes,
                'priority': min(100, pattern.occurrence_count * 10),
                'confidence': min(1.0, pattern.occurrence_count / 10.0)
            }
            rules.append(rule)
        
        # 高リスクスロットから規則を生成
        if self.model_trained:
            high_risk = self.predict_high_risk_slots(None, threshold=0.8)
            for time_slot, class_ref, risk_score in high_risk[:5]:
                rule = {
                    'rule_id': f"highrisk_{time_slot.day}{time_slot.period}_{class_ref.grade}{class_ref.class_number}",
                    'description': f"{time_slot.day}曜{time_slot.period}限の{class_ref.grade}-{class_ref.class_number}は要注意",
                    'condition': {
                        'time_slot': (time_slot.day, time_slot.period),
                        'class_ref': (class_ref.grade, class_ref.class_number)
                    },
                    'actions': ["慎重に教師を選択", "事前に制約チェックを強化"],
                    'priority': int(risk_score * 100),
                    'confidence': risk_score
                }
                rules.append(rule)
        
        return rules
    
    def learn(self) -> LearningResult:
        """学習を実行"""
        # パターン分析
        patterns = self.analyze_patterns()
        
        # モデル訓練
        if len(self.violation_history) >= 50:
            self.train_risk_model()
        
        # 高リスクスロット予測
        high_risk_slots = []
        if self.model_trained:
            high_risk_slots = self.predict_high_risk_slots(None, threshold=0.7)
        
        # 予防ルール生成
        preventive_rules = self.generate_preventive_rules()
        
        # 信頼度計算
        confidence = min(1.0, len(self.violation_history) / 100.0)
        
        return LearningResult(
            patterns_found=len(patterns),
            high_risk_slots=high_risk_slots,
            preventive_rules=preventive_rules,
            confidence=confidence
        )
    
    def apply_preventive_measures(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        candidates: List[Any]
    ) -> List[Any]:
        """予防措置を適用"""
        # リスクスコアを確認
        risk_score = self.predict_risk(time_slot, class_ref)
        
        if risk_score > 0.7:
            self.logger.warning(
                f"高リスクスロット: {time_slot.day}{time_slot.period}限 "
                f"{class_ref.grade}-{class_ref.class_number} (リスク: {risk_score:.2f})"
            )
            
            # より慎重な選択を行う
            # 例: 候補を絞り込む、追加チェックを行うなど
            if len(candidates) > 3:
                # 上位3候補のみを返す
                return candidates[:3]
        
        return candidates
    
    def save_history(self, filepath: str):
        """違反履歴を保存"""
        data = {
            'violations': [
                {
                    'type': v.violation_type,
                    'time_slot': {'day': v.time_slot.day, 'period': v.time_slot.period},
                    'class_ref': {'grade': v.class_ref.grade, 'class': v.class_ref.class_number},
                    'details': v.details,
                    'timestamp': v.timestamp.isoformat()
                }
                for v in self.violation_history
            ],
            'patterns': [
                {
                    'id': p.pattern_id,
                    'type': p.violation_type,
                    'features': p.features,
                    'occurrences': p.occurrence_count,
                    'fixes': p.suggested_fixes
                }
                for p in self.patterns.values()
            ],
            'stats': self.stats
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"違反履歴を保存しました: {filepath}")
    
    def load_history(self, filepath: str):
        """違反履歴をロード"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 違反履歴を復元
            self.violation_history = []
            for v_data in data.get('violations', []):
                instance = ViolationInstance(
                    violation_type=v_data['type'],
                    time_slot=TimeSlot(v_data['time_slot']['day'], v_data['time_slot']['period']),
                    class_ref=ClassReference(v_data['class_ref']['grade'], v_data['class_ref']['class']),
                    details=v_data['details'],
                    timestamp=datetime.fromisoformat(v_data['timestamp'])
                )
                self.violation_history.append(instance)
            
            # パターンを復元
            self.patterns = {}
            for p_data in data.get('patterns', []):
                pattern = ViolationPattern(
                    pattern_id=p_data['id'],
                    violation_type=p_data['type'],
                    features=p_data['features'],
                    occurrence_count=p_data['occurrences'],
                    suggested_fixes=p_data.get('fixes', [])
                )
                self.patterns[pattern.pattern_id] = pattern
            
            # 統計を復元
            self.stats.update(data.get('stats', {}))
            
            self.logger.info(f"違反履歴をロードしました: {len(self.violation_history)}件")
            
        except Exception as e:
            self.logger.error(f"履歴のロードに失敗: {e}")
    
    def save_model(self, filepath: str):
        """学習モデルを保存"""
        if not self.model_trained:
            self.logger.warning("保存するモデルがありません")
            return
        
        model_data = {
            'vectorizer': self.vectorizer,
            'risk_predictor': self.risk_predictor,
            'model_trained': self.model_trained
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        self.logger.info(f"学習モデルを保存しました: {filepath}")
    
    def load_model(self, filepath: str):
        """学習モデルをロード"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.vectorizer = model_data['vectorizer']
            self.risk_predictor = model_data['risk_predictor']
            self.model_trained = model_data['model_trained']
            
            self.logger.info("学習モデルをロードしました")
            
        except Exception as e:
            self.logger.error(f"モデルのロードに失敗: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'violations_recorded': self.stats['violations_recorded'],
            'patterns_discovered': self.stats['patterns_discovered'],
            'predictions_made': self.stats['predictions_made'],
            'violations_prevented': self.stats['violations_prevented'],
            'model_trained': self.model_trained,
            'frequent_patterns': len([p for p in self.patterns.values() 
                                    if p.occurrence_count >= self.min_pattern_occurrences]),
            'total_patterns': len(self.patterns),
            'history_size': len(self.violation_history)
        }