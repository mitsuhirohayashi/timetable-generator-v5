"""
スマートバックトラッキングアルゴリズム

バックジャンピング、学習、動的バックトラッキングなど、
高度なバックトラッキング技術を実装。
"""
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import time

from .constraint_propagation import Variable, Domain, ConstraintPropagation
from ....entities.schedule import Schedule
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class AssignmentNode:
    """探索木のノード"""
    variable: Variable
    value: Tuple[str, Optional[str]]
    depth: int
    parent: Optional['AssignmentNode'] = None
    children: List['AssignmentNode'] = field(default_factory=list)
    conflict_set: Set[Variable] = field(default_factory=set)
    
    def add_conflict(self, variable: Variable):
        """競合変数を追加"""
        self.conflict_set.add(variable)
    
    def get_earliest_conflict_depth(self) -> int:
        """最も早い競合の深さを取得"""
        if not self.conflict_set:
            return 0
        
        # 競合セット内の変数の最小深さを探す
        min_depth = self.depth
        current = self.parent
        depth = self.depth - 1
        
        while current and depth >= 0:
            if current.variable in self.conflict_set:
                min_depth = min(min_depth, depth)
            current = current.parent
            depth -= 1
        
        return min_depth


@dataclass
class NoGood:
    """学習した制約（no-good）"""
    assignments: Set[Tuple[Variable, Tuple[str, Optional[str]]]]
    
    def __hash__(self):
        return hash(frozenset(self.assignments))
    
    def __eq__(self, other):
        return self.assignments == other.assignments
    
    def is_violated_by(self, current_assignments: Dict[Variable, Tuple[str, Optional[str]]]) -> bool:
        """現在の割り当てがこのno-goodに違反するかチェック"""
        for var, val in self.assignments:
            if var in current_assignments and current_assignments[var] == val:
                continue
            else:
                return False
        return True


class SmartBacktracking(LoggingMixin):
    """スマートバックトラッキングエンジン"""
    
    def __init__(
        self, 
        school: School,
        constraint_propagation: ConstraintPropagation,
        enable_learning: bool = True,
        max_nogoods: int = 1000
    ):
        super().__init__()
        self.school = school
        self.constraint_prop = constraint_propagation
        self.enable_learning = enable_learning
        self.max_nogoods = max_nogoods
        
        # 探索状態
        self.assignments: Dict[Variable, Tuple[str, Optional[str]]] = {}
        self.search_tree_root: Optional[AssignmentNode] = None
        self.current_node: Optional[AssignmentNode] = None
        
        # 学習
        self.nogoods: Set[NoGood] = set()
        self.nogood_index: Dict[Variable, Set[NoGood]] = defaultdict(set)
        
        # 統計
        self.stats = {
            'backtracks': 0,
            'backjumps': 0,
            'nogoods_learned': 0,
            'conflicts_detected': 0,
            'nodes_explored': 0
        }
    
    def search(
        self,
        initial_assignments: Dict[Variable, Tuple[str, Optional[str]]] = None,
        time_limit: float = 300
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """
        スマートバックトラッキング探索
        
        Returns:
            解が見つかった場合は割り当て辞書、見つからない場合はNone
        """
        self.logger.info("スマートバックトラッキング探索開始")
        start_time = time.time()
        
        # 初期化
        self.assignments = initial_assignments or {}
        self.search_tree_root = None
        self.current_node = None
        
        # 変数順序を決定
        unassigned = self._get_unassigned_variables()
        
        # 探索開始
        result = self._backtrack(unassigned, start_time, time_limit)
        
        # 統計ログ
        self.logger.info(
            f"探索完了: "
            f"ノード数={self.stats['nodes_explored']}, "
            f"バックトラック={self.stats['backtracks']}, "
            f"バックジャンプ={self.stats['backjumps']}, "
            f"学習制約={self.stats['nogoods_learned']}"
        )
        
        return result
    
    def _backtrack(
        self,
        unassigned: List[Variable],
        start_time: float,
        time_limit: float
    ) -> Optional[Dict[Variable, Tuple[str, Optional[str]]]]:
        """再帰的バックトラッキング"""
        # 時間制限チェック
        if time.time() - start_time > time_limit:
            self.logger.warning("時間制限に達しました")
            return None
        
        # 完全割り当てチェック
        if not unassigned:
            return self.assignments.copy()
        
        # 変数選択（MRVヒューリスティック）
        var = self._select_variable(unassigned)
        remaining = [v for v in unassigned if v != var]
        
        # 値順序付け（LCVヒューリスティック）
        values = self._order_values(var)
        
        for value in values:
            self.stats['nodes_explored'] += 1
            
            # no-goodチェック
            if self._violates_nogood(var, value):
                continue
            
            # 割り当て試行
            self.assignments[var] = value
            
            # ノード作成
            node = AssignmentNode(
                variable=var,
                value=value,
                depth=len(self.assignments),
                parent=self.current_node
            )
            
            if self.current_node:
                self.current_node.children.append(node)
            else:
                self.search_tree_root = node
            
            self.current_node = node
            
            # 制約チェックと伝播
            inference_result = self._inference(var, value)
            
            if inference_result is not None:
                # 推論による割り当てを追加
                original_assignments = {}
                for inf_var, inf_val in inference_result:
                    if inf_var not in self.assignments:
                        original_assignments[inf_var] = None
                        self.assignments[inf_var] = inf_val
                        remaining = [v for v in remaining if v != inf_var]
                
                # 再帰的探索
                result = self._backtrack(remaining, start_time, time_limit)
                
                if result is not None:
                    return result
                
                # 推論による割り当てを削除
                for inf_var in original_assignments:
                    if original_assignments[inf_var] is None:
                        del self.assignments[inf_var]
                        remaining.append(inf_var)
            else:
                # 競合を記録
                self.stats['conflicts_detected'] += 1
                self._analyze_conflict(node)
            
            # バックトラック
            del self.assignments[var]
            self.current_node = node.parent
        
        # バックジャンピングの判定
        if self.current_node and self.current_node.conflict_set:
            jump_depth = self.current_node.get_earliest_conflict_depth()
            if jump_depth < len(self.assignments):
                self.stats['backjumps'] += 1
                # より早い深さまでジャンプ
                self._backjump_to_depth(jump_depth)
        else:
            self.stats['backtracks'] += 1
        
        return None
    
    def _select_variable(self, unassigned: List[Variable]) -> Variable:
        """
        変数選択ヒューリスティック（MRV: Minimum Remaining Values）
        
        最も制約の厳しい変数を選択
        """
        min_domain_size = float('inf')
        best_var = unassigned[0]
        
        for var in unassigned:
            domain = self.constraint_prop.domains[var]
            
            # 現在の割り当てと整合する値の数を計算
            valid_values = 0
            for value in domain.values:
                if not self._violates_constraints(var, value):
                    valid_values += 1
            
            if valid_values < min_domain_size:
                min_domain_size = valid_values
                best_var = var
                
                # ドメインが空の場合は即座に返す
                if valid_values == 0:
                    break
        
        return best_var
    
    def _order_values(self, variable: Variable) -> List[Tuple[str, Optional[str]]]:
        """
        値順序付けヒューリスティック（LCV: Least Constraining Value）
        
        他の変数への制約が最も少ない値を優先
        """
        domain = self.constraint_prop.domains[variable]
        value_scores = []
        
        for value in domain.values:
            # この値を選んだ場合の影響を計算
            constraints_count = 0
            
            # 前方チェックで影響を受ける変数を取得
            affected = self.constraint_prop.forward_checking(variable, value)
            
            for affected_var, removed_values in affected.items():
                constraints_count += len(removed_values)
            
            value_scores.append((value, constraints_count))
        
        # 制約が少ない順にソート
        value_scores.sort(key=lambda x: x[1])
        
        return [v[0] for v in value_scores]
    
    def _inference(
        self, 
        variable: Variable, 
        value: Tuple[str, Optional[str]]
    ) -> Optional[List[Tuple[Variable, Tuple[str, Optional[str]]]]]:
        """
        制約伝播による推論
        
        Returns:
            推論された割り当てのリスト、矛盾が見つかった場合はNone
        """
        # MACによる制約維持
        if not self.constraint_prop.maintain_arc_consistency(variable, value):
            return None
        
        # 推論された割り当てを取得
        inferences = self.constraint_prop.get_inference_assignments()
        
        # 現在の割り当てと矛盾しないかチェック
        for inf_var, inf_val in inferences:
            if inf_var in self.assignments and self.assignments[inf_var] != inf_val:
                return None
        
        return inferences
    
    def _violates_constraints(
        self, 
        variable: Variable, 
        value: Tuple[str, Optional[str]]
    ) -> bool:
        """制約違反をチェック"""
        # 教師重複チェック
        if value[1]:  # 教師がいる場合
            for other_var, other_val in self.assignments.items():
                if (other_var.time_slot == variable.time_slot and
                    other_val[1] == value[1]):
                    return True
        
        # 日内重複チェック
        for other_var, other_val in self.assignments.items():
            if (other_var.class_ref == variable.class_ref and
                other_var.time_slot.day == variable.time_slot.day and
                other_val[0] == value[0]):
                return True
        
        return False
    
    def _violates_nogood(
        self, 
        variable: Variable, 
        value: Tuple[str, Optional[str]]
    ) -> bool:
        """no-good違反をチェック"""
        if not self.enable_learning:
            return False
        
        # この変数に関連するno-goodをチェック
        for nogood in self.nogood_index[variable]:
            # 現在の割り当て＋新しい割り当てを作成
            test_assignments = self.assignments.copy()
            test_assignments[variable] = value
            
            if nogood.is_violated_by(test_assignments):
                return True
        
        return False
    
    def _analyze_conflict(self, node: AssignmentNode):
        """競合分析と学習"""
        if not self.enable_learning:
            return
        
        # 競合セットの構築
        conflict_vars = set()
        
        # 現在の割り当てで競合している変数を特定
        for var, val in self.assignments.items():
            if self._violates_constraints(node.variable, node.value):
                conflict_vars.add(var)
        
        node.conflict_set = conflict_vars
        
        # no-goodの学習
        if len(conflict_vars) > 0 and len(self.nogoods) < self.max_nogoods:
            # 最小競合セットを作成
            nogood_assignments = set()
            nogood_assignments.add((node.variable, node.value))
            
            for var in conflict_vars:
                if var in self.assignments:
                    nogood_assignments.add((var, self.assignments[var]))
            
            nogood = NoGood(nogood_assignments)
            
            if nogood not in self.nogoods:
                self.nogoods.add(nogood)
                self.stats['nogoods_learned'] += 1
                
                # インデックスに追加
                for var, _ in nogood.assignments:
                    self.nogood_index[var].add(nogood)
    
    def _backjump_to_depth(self, target_depth: int):
        """指定された深さまでバックジャンプ"""
        while len(self.assignments) > target_depth:
            # 最後の割り当てを削除
            if self.current_node and self.current_node.parent:
                var_to_remove = self.current_node.variable
                if var_to_remove in self.assignments:
                    del self.assignments[var_to_remove]
                self.current_node = self.current_node.parent
    
    def _get_unassigned_variables(self) -> List[Variable]:
        """未割り当て変数のリストを取得"""
        return [
            var for var in self.constraint_prop.variables
            if var not in self.assignments
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'nodes_explored': self.stats['nodes_explored'],
            'backtracks': self.stats['backtracks'],
            'backjumps': self.stats['backjumps'],
            'backjump_ratio': (
                self.stats['backjumps'] / 
                (self.stats['backtracks'] + self.stats['backjumps'])
                if self.stats['backtracks'] + self.stats['backjumps'] > 0 else 0
            ),
            'nogoods_learned': self.stats['nogoods_learned'],
            'conflicts_detected': self.stats['conflicts_detected'],
            'current_depth': len(self.assignments),
            'total_variables': len(self.constraint_prop.variables)
        }