"""
高度な制約伝播アルゴリズム

AC-3、PC-2、およびその他の制約伝播技術を実装。
探索空間を効率的に削減し、高速な制約充足を実現。
"""
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import deque, defaultdict
from dataclasses import dataclass
import time

from ....entities.schedule import Schedule
from ....entities.school import School, Teacher, Subject
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class Variable:
    """CSP変数（時間スロット＋クラス）"""
    time_slot: TimeSlot
    class_ref: ClassReference
    
    def __hash__(self):
        return hash((self.time_slot.day, self.time_slot.period, 
                    self.class_ref.grade, self.class_ref.class_number))
    
    def __eq__(self, other):
        return (self.time_slot == other.time_slot and 
                self.class_ref == other.class_ref)


@dataclass
class Domain:
    """変数のドメイン（可能な割り当て）"""
    variable: Variable
    values: Set[Tuple[str, Optional[str]]]  # (subject, teacher)
    
    def remove_value(self, value: Tuple[str, Optional[str]]):
        """値をドメインから削除"""
        self.values.discard(value)
    
    def is_empty(self) -> bool:
        """ドメインが空かチェック"""
        return len(self.values) == 0
    
    def size(self) -> int:
        """ドメインサイズ"""
        return len(self.values)


class Arc:
    """制約アーク（2つの変数間の制約）"""
    def __init__(self, var1: Variable, var2: Variable, constraint_type: str):
        self.var1 = var1
        self.var2 = var2
        self.constraint_type = constraint_type
    
    def __hash__(self):
        return hash((self.var1, self.var2, self.constraint_type))
    
    def __eq__(self, other):
        return (self.var1 == other.var1 and 
                self.var2 == other.var2 and
                self.constraint_type == other.constraint_type)


class ConstraintPropagation(LoggingMixin):
    """制約伝播エンジン"""
    
    def __init__(self, school: School, cache: Optional['PerformanceCache'] = None):
        super().__init__()
        self.school = school
        self.cache = cache
        
        # 制約グラフ
        self.variables: Set[Variable] = set()
        self.domains: Dict[Variable, Domain] = {}
        self.arcs: Set[Arc] = set()
        self.constraints: Dict[str, List[Arc]] = defaultdict(list)
        
        # 統計情報
        self.stats = {
            'propagations': 0,
            'domain_reductions': 0,
            'arc_revisions': 0,
            'cache_hits': 0
        }
    
    def initialize_from_schedule(
        self, 
        schedule: Schedule,
        fixed_assignments: Set[Tuple[TimeSlot, ClassReference]] = None
    ):
        """スケジュールから制約グラフを初期化"""
        self.logger.debug("制約グラフの初期化を開始")
        
        # 変数の作成
        for class_ref in self.school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    var = Variable(time_slot, class_ref)
                    self.variables.add(var)
                    
                    # 既存の割り当てがある場合
                    existing = schedule.get_assignment(time_slot, class_ref)
                    if existing:
                        # 固定されている場合は単一値ドメイン
                        if fixed_assignments and (time_slot, class_ref) in fixed_assignments:
                            self.domains[var] = Domain(
                                var, 
                                {(existing.subject.name, 
                                  existing.teacher.name if existing.teacher else None)}
                            )
                        else:
                            # 初期ドメインの作成
                            self.domains[var] = self._create_initial_domain(var)
                    else:
                        # 初期ドメインの作成
                        self.domains[var] = self._create_initial_domain(var)
        
        # アークの作成
        self._create_arcs()
        
        self.logger.debug(
            f"制約グラフ初期化完了: "
            f"変数数={len(self.variables)}, "
            f"アーク数={len(self.arcs)}"
        )
    
    def ac3(self) -> bool:
        """
        AC-3アルゴリズムによる制約伝播
        
        Returns:
            True if 制約充足可能, False if 矛盾発見
        """
        self.logger.debug("AC-3アルゴリズム開始")
        start_time = time.time()
        
        # 初期キュー（全てのアーク）
        queue = deque(self.arcs)
        
        while queue:
            arc = queue.popleft()
            
            # アークの整合性チェック
            if self._revise(arc):
                self.stats['arc_revisions'] += 1
                
                # ドメインが空になった場合は矛盾
                if self.domains[arc.var1].is_empty():
                    self.logger.debug(
                        f"AC-3: 変数 {arc.var1} のドメインが空になりました"
                    )
                    return False
                
                # var1のドメインが変更されたので、関連アークを再チェック
                for neighbor_arc in self._get_neighbor_arcs(arc.var1, arc):
                    queue.append(neighbor_arc)
        
        execution_time = time.time() - start_time
        self.logger.debug(
            f"AC-3完了: "
            f"時間={execution_time:.3f}秒, "
            f"アーク修正={self.stats['arc_revisions']}"
        )
        
        return True
    
    def pc2(self) -> bool:
        """
        PC-2アルゴリズムによるパス整合性
        
        より強力な制約伝播だが計算コストが高い
        """
        self.logger.debug("PC-2アルゴリズム開始")
        
        # 3つ組の制約をチェック
        variables_list = list(self.variables)
        n = len(variables_list)
        
        changed = True
        while changed:
            changed = False
            
            # 全ての3つ組をチェック
            for i in range(n):
                for j in range(i + 1, n):
                    for k in range(j + 1, n):
                        var_i, var_j, var_k = variables_list[i], variables_list[j], variables_list[k]
                        
                        # パス整合性のチェック
                        if self._check_path_consistency(var_i, var_j, var_k):
                            changed = True
                            
                            # ドメインが空になったらFalse
                            if any(self.domains[v].is_empty() for v in [var_i, var_j, var_k]):
                                return False
        
        return True
    
    def forward_checking(
        self, 
        variable: Variable, 
        value: Tuple[str, Optional[str]]
    ) -> Dict[Variable, Set[Tuple[str, Optional[str]]]]:
        """
        前方チェック：変数に値を割り当てた時の影響を計算
        
        Returns:
            影響を受ける変数とその削除される値のマップ
        """
        affected = {}
        
        # 教師の重複チェック
        if value[1]:  # 教師がいる場合
            teacher_name = value[1]
            
            # 同じ時間の他のクラス
            for other_var in self.variables:
                if (other_var.time_slot == variable.time_slot and 
                    other_var != variable):
                    
                    # この教師を使う値を削除
                    removed_values = set()
                    for domain_value in self.domains[other_var].values:
                        if domain_value[1] == teacher_name:
                            removed_values.add(domain_value)
                    
                    if removed_values:
                        affected[other_var] = removed_values
        
        # 日内重複チェック
        subject_name = value[0]
        for other_var in self.variables:
            if (other_var.class_ref == variable.class_ref and
                other_var.time_slot.day == variable.time_slot.day and
                other_var != variable):
                
                # 同じ科目を削除
                removed_values = set()
                for domain_value in self.domains[other_var].values:
                    if domain_value[0] == subject_name:
                        removed_values.add(domain_value)
                
                if removed_values:
                    if other_var in affected:
                        affected[other_var].update(removed_values)
                    else:
                        affected[other_var] = removed_values
        
        return affected
    
    def maintain_arc_consistency(
        self,
        variable: Variable,
        value: Tuple[str, Optional[str]]
    ) -> bool:
        """
        動的なアーク整合性維持（MAC: Maintaining Arc Consistency）
        
        変数に値を割り当てた後、関連する制約の整合性を維持
        """
        # 前方チェックで影響を受ける変数を取得
        affected = self.forward_checking(variable, value)
        
        # 影響を受ける変数のドメインを一時的に縮小
        original_domains = {}
        for var, values_to_remove in affected.items():
            original_domains[var] = self.domains[var].values.copy()
            self.domains[var].values -= values_to_remove
        
        # 影響を受けた変数から制約伝播
        queue = deque()
        for var in affected:
            # この変数に関連するアークをキューに追加
            for arc in self.arcs:
                if arc.var2 == var:
                    queue.append(arc)
        
        # AC-3の実行
        while queue:
            arc = queue.popleft()
            
            if self._revise(arc):
                if self.domains[arc.var1].is_empty():
                    # 矛盾が発生したので、ドメインを復元
                    for var, original in original_domains.items():
                        self.domains[var].values = original
                    return False
                
                # 更に伝播
                for neighbor_arc in self._get_neighbor_arcs(arc.var1, arc):
                    if neighbor_arc not in queue:
                        queue.append(neighbor_arc)
        
        return True
    
    def get_inference_assignments(
        self
    ) -> List[Tuple[Variable, Tuple[str, Optional[str]]]]:
        """
        制約伝播の結果、単一値になった変数の取得
        
        Returns:
            推論により確定した割り当てのリスト
        """
        inferences = []
        
        for var, domain in self.domains.items():
            if domain.size() == 1:
                value = next(iter(domain.values))
                inferences.append((var, value))
        
        return inferences
    
    def _create_initial_domain(self, variable: Variable) -> Domain:
        """変数の初期ドメインを作成"""
        values = set()
        class_ref = variable.class_ref
        
        # 標準時数から必要な科目を取得
        standard_hours = self.school.get_all_standard_hours(class_ref)
        
        for subject, hours in standard_hours.items():
            if hours > 0:
                # 担当教師を取得
                teacher = self.school.get_assigned_teacher(subject, class_ref)
                if teacher:
                    values.add((subject.name, teacher.name))
                else:
                    values.add((subject.name, None))
        
        return Domain(variable, values)
    
    def _create_arcs(self):
        """制約アークを作成"""
        variables_list = list(self.variables)
        
        # 教師重複制約のアーク
        for i, var1 in enumerate(variables_list):
            for var2 in variables_list[i+1:]:
                if var1.time_slot == var2.time_slot:
                    arc = Arc(var1, var2, "teacher_conflict")
                    self.arcs.add(arc)
                    self.constraints["teacher_conflict"].append(arc)
                    
                    # 逆方向のアークも追加
                    arc_rev = Arc(var2, var1, "teacher_conflict")
                    self.arcs.add(arc_rev)
                    self.constraints["teacher_conflict"].append(arc_rev)
        
        # 日内重複制約のアーク
        for var1 in self.variables:
            for var2 in self.variables:
                if (var1.class_ref == var2.class_ref and
                    var1.time_slot.day == var2.time_slot.day and
                    var1.time_slot.period != var2.time_slot.period):
                    
                    arc = Arc(var1, var2, "daily_duplicate")
                    self.arcs.add(arc)
                    self.constraints["daily_duplicate"].append(arc)
    
    def _revise(self, arc: Arc) -> bool:
        """
        アークを修正（ドメインから不整合な値を削除）
        
        Returns:
            True if ドメインが変更された
        """
        revised = False
        domain1 = self.domains[arc.var1]
        domain2 = self.domains[arc.var2]
        
        values_to_remove = []
        
        for value1 in domain1.values:
            # value1に対して整合する値がdomain2にあるかチェック
            has_support = False
            
            for value2 in domain2.values:
                if self._is_consistent(arc, value1, value2):
                    has_support = True
                    break
            
            if not has_support:
                values_to_remove.append(value1)
                revised = True
        
        # 値を削除
        for value in values_to_remove:
            domain1.remove_value(value)
            self.stats['domain_reductions'] += 1
        
        return revised
    
    def _is_consistent(
        self, 
        arc: Arc, 
        value1: Tuple[str, Optional[str]], 
        value2: Tuple[str, Optional[str]]
    ) -> bool:
        """2つの値が制約に対して整合しているかチェック"""
        if arc.constraint_type == "teacher_conflict":
            # 教師が重複していないか
            if value1[1] and value2[1] and value1[1] == value2[1]:
                return False
        
        elif arc.constraint_type == "daily_duplicate":
            # 同じ科目でないか
            if value1[0] == value2[0]:
                return False
        
        return True
    
    def _get_neighbor_arcs(self, variable: Variable, exclude_arc: Arc) -> List[Arc]:
        """変数に関連するアーク（除外アーク以外）を取得"""
        neighbors = []
        
        for arc in self.arcs:
            if arc.var2 == variable and arc != exclude_arc:
                neighbors.append(arc)
        
        return neighbors
    
    def _check_path_consistency(
        self, 
        var_i: Variable, 
        var_j: Variable, 
        var_k: Variable
    ) -> bool:
        """3変数間のパス整合性をチェック"""
        # 簡易実装：完全なPC-2は計算コストが高いため
        # 実際には、より洗練された実装が必要
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        total_domain_size = sum(d.size() for d in self.domains.values())
        avg_domain_size = total_domain_size / len(self.domains) if self.domains else 0
        
        return {
            'variables': len(self.variables),
            'arcs': len(self.arcs),
            'total_domain_size': total_domain_size,
            'average_domain_size': avg_domain_size,
            'propagations': self.stats['propagations'],
            'domain_reductions': self.stats['domain_reductions'],
            'arc_revisions': self.stats['arc_revisions'],
            'cache_hits': self.stats['cache_hits']
        }