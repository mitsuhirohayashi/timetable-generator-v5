"""
高度なヒューリスティクス

変数順序付け、値順序付け、ドメイン削減など、
時間割生成に特化した高度なヒューリスティクスを実装。
"""
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import math

from .constraint_propagation import Variable, Domain
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class HeuristicScore:
    """ヒューリスティックスコア"""
    variable: Variable
    score: float
    components: Dict[str, float]
    
    def __lt__(self, other):
        return self.score < other.score


class AdvancedHeuristics(LoggingMixin):
    """高度なヒューリスティクスエンジン"""
    
    def __init__(self, school: School):
        super().__init__()
        self.school = school
        
        # 重み付けパラメータ
        self.weights = {
            'mrv': 2.0,          # Minimum Remaining Values
            'degree': 1.5,       # Degree heuristic
            'weighted_degree': 1.8,  # Weighted degree
            'temporal': 1.2,     # 時間的制約
            'critical': 2.5,     # クリティカル度
            'balance': 1.0       # バランス
        }
        
        # 統計情報
        self.stats = {
            'variable_selections': 0,
            'value_orderings': 0,
            'heuristic_calculations': 0
        }
    
    def select_variable(
        self,
        unassigned: List[Variable],
        domains: Dict[Variable, Domain],
        assignments: Dict[Variable, Tuple[str, Optional[str]]],
        constraints: Dict[str, List['Arc']] = None
    ) -> Variable:
        """
        変数選択ヒューリスティック（複合）
        
        MRV、Degree、ドメイン/加重度などを組み合わせた高度な選択
        """
        self.stats['variable_selections'] += 1
        
        if len(unassigned) == 1:
            return unassigned[0]
        
        scores = []
        
        for var in unassigned:
            # 各種ヒューリスティックスコアを計算
            score_components = {}
            
            # MRV (Minimum Remaining Values)
            score_components['mrv'] = self._calculate_mrv_score(var, domains)
            
            # Degree heuristic
            score_components['degree'] = self._calculate_degree_score(
                var, unassigned, constraints
            )
            
            # Weighted degree
            score_components['weighted_degree'] = self._calculate_weighted_degree_score(
                var, domains, assignments
            )
            
            # 時間的制約スコア
            score_components['temporal'] = self._calculate_temporal_score(var)
            
            # クリティカル度スコア
            score_components['critical'] = self._calculate_critical_score(
                var, domains, self.school
            )
            
            # バランススコア
            score_components['balance'] = self._calculate_balance_score(
                var, assignments
            )
            
            # 総合スコア計算
            total_score = sum(
                self.weights.get(name, 1.0) * score
                for name, score in score_components.items()
            )
            
            scores.append(HeuristicScore(var, total_score, score_components))
            self.stats['heuristic_calculations'] += 1
        
        # スコアが最も高い変数を選択
        best = max(scores, key=lambda s: s.score)
        
        self.logger.debug(
            f"変数選択: {best.variable}, "
            f"スコア={best.score:.3f}, "
            f"内訳={best.components}"
        )
        
        return best.variable
    
    def order_values(
        self,
        variable: Variable,
        domain: Domain,
        assignments: Dict[Variable, Tuple[str, Optional[str]]],
        constraint_propagation: 'ConstraintPropagation' = None
    ) -> List[Tuple[str, Optional[str]]]:
        """
        値順序付けヒューリスティック（LCV + 追加要素）
        
        制約の少ない値を優先し、さらに時間割固有の要素を考慮
        """
        self.stats['value_orderings'] += 1
        
        value_scores = []
        
        for value in domain.values:
            score_components = {}
            
            # LCV (Least Constraining Value)
            if constraint_propagation:
                score_components['lcv'] = self._calculate_lcv_score(
                    variable, value, constraint_propagation
                )
            else:
                score_components['lcv'] = 0
            
            # 時間帯適性スコア
            score_components['time_fit'] = self._calculate_time_fit_score(
                variable, value
            )
            
            # 教師負荷バランススコア
            score_components['teacher_load'] = self._calculate_teacher_load_score(
                variable, value, assignments
            )
            
            # 科目配置パターンスコア
            score_components['pattern'] = self._calculate_pattern_score(
                variable, value, assignments
            )
            
            # 総合スコア（値が高いほど良い）
            total_score = sum(score_components.values())
            value_scores.append((value, total_score, score_components))
        
        # スコアの高い順にソート
        value_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [v[0] for v in value_scores]
    
    def _calculate_mrv_score(self, variable: Variable, domains: Dict[Variable, Domain]) -> float:
        """MRVスコア計算（ドメインサイズが小さいほど高スコア）"""
        domain_size = domains[variable].size()
        if domain_size == 0:
            return float('inf')  # 最優先
        return 100.0 / domain_size
    
    def _calculate_degree_score(
        self,
        variable: Variable,
        unassigned: List[Variable],
        constraints: Dict[str, List['Arc']] = None
    ) -> float:
        """Degreeスコア計算（制約の多い変数ほど高スコア）"""
        degree = 0
        
        # 他の未割り当て変数との制約数を計算
        for other_var in unassigned:
            if other_var == variable:
                continue
            
            # 同じ時間帯の制約
            if other_var.time_slot == variable.time_slot:
                degree += 2  # 教師重複制約が強い
            
            # 同じクラスの制約
            if other_var.class_ref == variable.class_ref:
                # 同じ日の制約
                if other_var.time_slot.day == variable.time_slot.day:
                    degree += 1  # 日内重複制約
        
        return float(degree)
    
    def _calculate_weighted_degree_score(
        self,
        variable: Variable,
        domains: Dict[Variable, Domain],
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> float:
        """加重度スコア（過去の競合頻度を考慮）"""
        # 簡易実装：ドメインサイズと制約の組み合わせ
        domain_size = domains[variable].size()
        
        # 5組や交流学級は加重を高くする
        weight = 1.0
        if variable.class_ref.class_number == 5:  # 5組
            weight = 2.0
        elif variable.class_ref.class_number in [6, 7]:  # 交流学級
            weight = 1.5
        
        return weight * (10.0 / max(domain_size, 1))
    
    def _calculate_temporal_score(self, variable: Variable) -> float:
        """時間的制約スコア（特定の時間帯の重要度）"""
        time_slot = variable.time_slot
        
        # 月曜1限と金曜6限は制約が厳しい
        if time_slot.day == "月" and time_slot.period == 1:
            return 3.0
        elif time_slot.day == "金" and time_slot.period == 6:
            return 2.5
        
        # 午前中は主要科目の配置が重要
        if time_slot.period <= 2:
            return 1.5
        
        return 1.0
    
    def _calculate_critical_score(
        self,
        variable: Variable,
        domains: Dict[Variable, Domain],
        school: School
    ) -> float:
        """クリティカル度スコア（必須配置の緊急度）"""
        class_ref = variable.class_ref
        domain = domains[variable]
        
        # 残り配置必要数を計算
        critical_subjects = []
        for value in domain.values:
            subject_name = value[0]
            subject = next((s for s in school.get_all_subjects() if s.name == subject_name), None)
            if subject:
                standard_hours = school.get_standard_hours(class_ref, subject)
                if standard_hours > 0:
                    # TODO: 現在の配置数を取得して残り必要数を計算
                    critical_subjects.append(subject_name)
        
        # 必須科目が多いほど高スコア
        return len(critical_subjects) * 0.5
    
    def _calculate_balance_score(
        self,
        variable: Variable,
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> float:
        """バランススコア（曜日・時限の配置バランス）"""
        # この時間帯の配置済み数を計算
        same_slot_count = sum(
            1 for var, _ in assignments.items()
            if var.time_slot == variable.time_slot
        )
        
        # この曜日の配置済み数を計算
        same_day_count = sum(
            1 for var, _ in assignments.items()
            if var.time_slot.day == variable.time_slot.day and
            var.class_ref == variable.class_ref
        )
        
        # バランスが取れているほど高スコア
        total_classes = len(self.school.get_all_classes())
        slot_balance = 1.0 - (same_slot_count / total_classes)
        day_balance = 1.0 - (same_day_count / 6)  # 6時限
        
        return (slot_balance + day_balance) / 2
    
    def _calculate_lcv_score(
        self,
        variable: Variable,
        value: Tuple[str, Optional[str]],
        constraint_propagation: 'ConstraintPropagation'
    ) -> float:
        """LCVスコア（他の変数への制約が少ないほど高スコア）"""
        # 前方チェックで影響を計算
        affected = constraint_propagation.forward_checking(variable, value)
        
        # 削除される値の総数
        total_removed = sum(len(values) for values in affected.values())
        
        # 制約が少ないほど高スコア
        return 100.0 / (total_removed + 1)
    
    def _calculate_time_fit_score(
        self,
        variable: Variable,
        value: Tuple[str, Optional[str]]
    ) -> float:
        """時間帯適性スコア（科目と時間帯の相性）"""
        subject_name = value[0]
        time_slot = variable.time_slot
        
        # 主要科目は午前中が適している
        if subject_name in ["国", "数", "英", "理", "社"]:
            if time_slot.period <= 3:
                return 2.0
            else:
                return 0.5
        
        # 実技科目は午後でも良い
        elif subject_name in ["音", "美", "技", "家", "保"]:
            if time_slot.period >= 3:
                return 1.5
            else:
                return 1.0
        
        return 1.0
    
    def _calculate_teacher_load_score(
        self,
        variable: Variable,
        value: Tuple[str, Optional[str]],
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> float:
        """教師負荷バランススコア"""
        teacher_name = value[1]
        if not teacher_name:
            return 1.0
        
        # この教師の現在の担当コマ数を計算
        teacher_count = sum(
            1 for _, val in assignments.items()
            if val[1] == teacher_name
        )
        
        # この曜日のこの教師の担当コマ数
        day_count = sum(
            1 for var, val in assignments.items()
            if val[1] == teacher_name and var.time_slot.day == variable.time_slot.day
        )
        
        # 負荷が分散しているほど高スコア
        # 1日の担当が多すぎる場合はペナルティ
        if day_count >= 4:
            return 0.3
        elif day_count >= 3:
            return 0.7
        
        # 全体の負荷も考慮
        if teacher_count > 20:  # 週20コマ以上は避ける
            return 0.5
        
        return 1.0
    
    def _calculate_pattern_score(
        self,
        variable: Variable,
        value: Tuple[str, Optional[str]],
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> float:
        """科目配置パターンスコア（良い配置パターンかどうか）"""
        subject_name = value[0]
        class_ref = variable.class_ref
        
        # 同じ科目の連続配置を避ける
        if variable.time_slot.period > 1:
            prev_slot = TimeSlot(variable.time_slot.day, variable.time_slot.period - 1)
            prev_var = Variable(prev_slot, class_ref)
            if prev_var in assignments and assignments[prev_var][0] == subject_name:
                return 0.3  # 連続は避ける
        
        # 同じ科目が1日に偏らないようにする
        same_subject_today = sum(
            1 for var, val in assignments.items()
            if (var.class_ref == class_ref and
                var.time_slot.day == variable.time_slot.day and
                val[0] == subject_name)
        )
        
        if same_subject_today > 0:
            return 0.0  # 既に配置済みなら選ばない
        
        return 1.0
    
    def apply_domain_reduction(
        self,
        domains: Dict[Variable, Domain],
        assignments: Dict[Variable, Tuple[str, Optional[str]]],
        school: School
    ) -> int:
        """
        ドメイン削減ヒューリスティック
        
        Returns:
            削減された値の数
        """
        total_reduced = 0
        
        for var, domain in domains.items():
            if var in assignments:
                continue
            
            values_to_remove = []
            
            for value in domain.values:
                # 明らかに不可能な値を削除
                if self._is_obviously_invalid(var, value, assignments, school):
                    values_to_remove.append(value)
            
            for value in values_to_remove:
                domain.remove_value(value)
                total_reduced += 1
        
        return total_reduced
    
    def _is_obviously_invalid(
        self,
        variable: Variable,
        value: Tuple[str, Optional[str]],
        assignments: Dict[Variable, Tuple[str, Optional[str]]],
        school: School
    ) -> bool:
        """明らかに無効な値かチェック"""
        subject_name, teacher_name = value
        
        # 固定科目を通常スロットに配置しようとしている
        fixed_subjects = {"欠", "YT", "学", "道", "総", "行"}
        if subject_name in fixed_subjects and variable.time_slot.period <= 5:
            # 通常これらは6限に配置
            return True
        
        # 教師不在チェック
        if teacher_name:
            teacher = next((t for t in school.get_all_teachers() if t.name == teacher_name), None)
            if teacher and school.is_teacher_unavailable(
                variable.time_slot.day,
                variable.time_slot.period,
                teacher
            ):
                return True
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'variable_selections': self.stats['variable_selections'],
            'value_orderings': self.stats['value_orderings'],
            'heuristic_calculations': self.stats['heuristic_calculations'],
            'avg_calculations_per_selection': (
                self.stats['heuristic_calculations'] / self.stats['variable_selections']
                if self.stats['variable_selections'] > 0 else 0
            )
        }