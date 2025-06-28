"""修正パターン学習器"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os

from ..data_models import Violation, SwapChain


@dataclass
class SuccessPattern:
    """成功した修正パターン"""
    violation_type: str
    violation_context: Dict[str, any]
    swap_chain: List[Dict[str, any]]  # SwapChainのシリアライズ版
    improvement_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    success_count: int = 1


class PatternLearner:
    """修正パターンを学習"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """初期化
        
        Args:
            data_dir: 学習データを保存するディレクトリ
        """
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(__file__), "learning_data"
        )
        
        # データディレクトリの作成
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 成功パターンのデータベース
        self.success_patterns: Dict[str, List[SuccessPattern]] = {}
        
        # 学習データの読み込み
        self._load_patterns()
    
    def learn_from_success(self, violation: Violation, chain: SwapChain):
        """成功した修正から学習
        
        Args:
            violation: 解決された違反
            chain: 成功した交換連鎖
        """
        # 違反のコンテキストを抽出
        context = self._extract_violation_context(violation)
        
        # 交換連鎖をシリアライズ
        serialized_chain = self._serialize_swap_chain(chain)
        
        # パターンを記録
        pattern = SuccessPattern(
            violation_type=violation.type,
            violation_context=context,
            swap_chain=serialized_chain,
            improvement_score=chain.total_improvement
        )
        
        # 既存のパターンと比較
        if violation.type not in self.success_patterns:
            self.success_patterns[violation.type] = []
        
        # 類似パターンを探す
        similar_pattern = self._find_similar_pattern(pattern)
        
        if similar_pattern:
            # 既存パターンの成功回数を増やす
            similar_pattern.success_count += 1
            similar_pattern.improvement_score = (
                similar_pattern.improvement_score * 0.9 + 
                pattern.improvement_score * 0.1
            )
        else:
            # 新しいパターンとして追加
            self.success_patterns[violation.type].append(pattern)
        
        # 定期的に保存
        if sum(len(patterns) for patterns in self.success_patterns.values()) % 10 == 0:
            self._save_patterns()
    
    def get_recommended_fixes(
        self,
        violation: Violation,
        max_recommendations: int = 5
    ) -> List[Dict[str, any]]:
        """違反に対する推奨修正を取得
        
        Args:
            violation: 違反
            max_recommendations: 最大推奨数
            
        Returns:
            推奨修正のリスト
        """
        if violation.type not in self.success_patterns:
            return []
        
        # 関連パターンを取得
        patterns = self.success_patterns[violation.type]
        
        # コンテキストの類似度でスコアリング
        violation_context = self._extract_violation_context(violation)
        scored_patterns = []
        
        for pattern in patterns:
            similarity = self._calculate_context_similarity(
                violation_context, pattern.violation_context
            )
            score = similarity * pattern.improvement_score * \
                   (1.0 + 0.1 * pattern.success_count)
            
            scored_patterns.append((score, pattern))
        
        # スコアでソート
        scored_patterns.sort(reverse=True, key=lambda x: x[0])
        
        # 上位の推奨を返す
        recommendations = []
        for score, pattern in scored_patterns[:max_recommendations]:
            recommendations.append({
                'pattern': pattern,
                'score': score,
                'swap_chain': pattern.swap_chain
            })
        
        return recommendations
    
    def _extract_violation_context(self, violation: Violation) -> Dict[str, any]:
        """違反のコンテキストを抽出"""
        context = {
            'type': violation.type,
            'severity': violation.severity,
            'day': violation.time_slot.day,
            'period': violation.time_slot.period,
            'class_count': len(violation.class_refs)
        }
        
        if violation.teacher:
            context['has_teacher'] = True
            context['teacher_name'] = violation.teacher.name
        
        if violation.subject:
            context['has_subject'] = True
            context['subject_name'] = violation.subject.name
        
        return context
    
    def _serialize_swap_chain(self, chain: SwapChain) -> List[Dict[str, any]]:
        """交換連鎖をシリアライズ"""
        serialized = []
        
        for swap in chain.swaps:
            serialized.append({
                'source_slot': {
                    'day': swap.source_slot.day,
                    'period': swap.source_slot.period
                },
                'source_class': str(swap.source_class),
                'target_slot': {
                    'day': swap.target_slot.day,
                    'period': swap.target_slot.period
                },
                'target_class': str(swap.target_class),
                'improvement_score': swap.improvement_score
            })
        
        return serialized
    
    def _find_similar_pattern(self, pattern: SuccessPattern) -> Optional[SuccessPattern]:
        """類似パターンを探す"""
        if pattern.violation_type not in self.success_patterns:
            return None
        
        for existing in self.success_patterns[pattern.violation_type]:
            similarity = self._calculate_context_similarity(
                pattern.violation_context,
                existing.violation_context
            )
            
            if similarity > 0.8:  # 80%以上の類似度
                return existing
        
        return None
    
    def _calculate_context_similarity(
        self,
        context1: Dict[str, any],
        context2: Dict[str, any]
    ) -> float:
        """コンテキストの類似度を計算"""
        similarity = 0.0
        weight_sum = 0.0
        
        # 各要素の重みと比較
        weights = {
            'type': 1.0,
            'severity': 0.5,
            'day': 0.3,
            'period': 0.3,
            'class_count': 0.2,
            'has_teacher': 0.2,
            'teacher_name': 0.3,
            'has_subject': 0.2,
            'subject_name': 0.3
        }
        
        for key, weight in weights.items():
            if key in context1 and key in context2:
                if context1[key] == context2[key]:
                    similarity += weight
                weight_sum += weight
        
        return similarity / weight_sum if weight_sum > 0 else 0.0
    
    def _save_patterns(self):
        """パターンを保存"""
        file_path = os.path.join(self.data_dir, "success_patterns.json")
        
        # シリアライズ可能な形式に変換
        data = {}
        for vtype, patterns in self.success_patterns.items():
            data[vtype] = []
            for pattern in patterns:
                data[vtype].append({
                    'violation_context': pattern.violation_context,
                    'swap_chain': pattern.swap_chain,
                    'improvement_score': pattern.improvement_score,
                    'timestamp': pattern.timestamp.isoformat(),
                    'success_count': pattern.success_count
                })
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_patterns(self):
        """パターンを読み込み"""
        file_path = os.path.join(self.data_dir, "success_patterns.json")
        
        if not os.path.exists(file_path):
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.success_patterns = {}
        for vtype, patterns in data.items():
            self.success_patterns[vtype] = []
            for p in patterns:
                pattern = SuccessPattern(
                    violation_type=vtype,
                    violation_context=p['violation_context'],
                    swap_chain=p['swap_chain'],
                    improvement_score=p['improvement_score'],
                    timestamp=datetime.fromisoformat(p['timestamp']),
                    success_count=p['success_count']
                )
                self.success_patterns[vtype].append(pattern)