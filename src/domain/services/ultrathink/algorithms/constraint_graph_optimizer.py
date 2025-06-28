"""
制約グラフ最適化

制約グラフの構造を最適化し、効率的な制約チェックと伝播を実現。
グラフ分解、クラスタリング、動的管理などの技術を実装。
"""
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import networkx as nx
import numpy as np
from sklearn.cluster import SpectralClustering

from .constraint_propagation import Variable, Arc
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class ConstraintCluster:
    """制約クラスタ"""
    id: int
    variables: Set[Variable]
    internal_arcs: Set[Arc]
    external_arcs: Set[Arc]
    priority: float = 1.0
    
    def size(self) -> int:
        return len(self.variables)
    
    def density(self) -> float:
        """クラスタ密度（内部結合度）"""
        if len(self.variables) <= 1:
            return 0.0
        max_arcs = len(self.variables) * (len(self.variables) - 1) / 2
        return len(self.internal_arcs) / max_arcs if max_arcs > 0 else 0.0


@dataclass 
class GraphDecomposition:
    """グラフ分解結果"""
    clusters: List[ConstraintCluster]
    tree_decomposition: Optional[nx.Graph] = None
    tree_width: int = -1
    
    def get_processing_order(self) -> List[ConstraintCluster]:
        """処理順序を取得（優先度順）"""
        return sorted(self.clusters, key=lambda c: c.priority, reverse=True)


class ConstraintGraphOptimizer(LoggingMixin):
    """制約グラフ最適化エンジン"""
    
    def __init__(self, school: School):
        super().__init__()
        self.school = school
        
        # グラフ構造
        self.graph = nx.Graph()
        self.variable_map: Dict[str, Variable] = {}
        self.arc_map: Dict[Tuple[str, str], Arc] = {}
        
        # クラスタリング結果
        self.decomposition: Optional[GraphDecomposition] = None
        
        # 動的管理
        self.dynamic_constraints: Set[Arc] = set()
        self.constraint_weights: Dict[Arc, float] = {}
        
        # 統計
        self.stats = {
            'graph_builds': 0,
            'decompositions': 0,
            'optimizations': 0,
            'dynamic_updates': 0
        }
    
    def build_constraint_graph(
        self,
        variables: Set[Variable],
        arcs: Set[Arc]
    ):
        """制約グラフを構築"""
        self.logger.debug("制約グラフの構築開始")
        self.stats['graph_builds'] += 1
        
        # グラフをクリア
        self.graph.clear()
        self.variable_map.clear()
        self.arc_map.clear()
        
        # 変数をノードとして追加
        for var in variables:
            var_id = self._get_variable_id(var)
            self.graph.add_node(var_id, variable=var)
            self.variable_map[var_id] = var
        
        # アークをエッジとして追加
        for arc in arcs:
            var1_id = self._get_variable_id(arc.var1)
            var2_id = self._get_variable_id(arc.var2)
            
            # 重みの計算
            weight = self._calculate_arc_weight(arc)
            
            self.graph.add_edge(
                var1_id, var2_id,
                arc=arc,
                weight=weight,
                constraint_type=arc.constraint_type
            )
            
            self.arc_map[(var1_id, var2_id)] = arc
            self.constraint_weights[arc] = weight
        
        self.logger.debug(
            f"制約グラフ構築完了: "
            f"ノード数={self.graph.number_of_nodes()}, "
            f"エッジ数={self.graph.number_of_edges()}"
        )
    
    def optimize_graph_structure(self) -> GraphDecomposition:
        """グラフ構造を最適化"""
        self.logger.debug("グラフ構造の最適化開始")
        self.stats['optimizations'] += 1
        
        # 1. グラフ分解
        decomposition = self._decompose_graph()
        
        # 2. クラスタリング
        clusters = self._cluster_constraints()
        
        # 3. 優先度計算
        self._calculate_cluster_priorities(clusters)
        
        # 4. 木分解（オプション）
        tree_decomposition = None
        tree_width = -1
        
        if self.graph.number_of_nodes() < 100:  # 小規模な場合のみ
            try:
                tree_decomposition, tree_width = self._tree_decomposition()
            except:
                self.logger.warning("木分解に失敗しました")
        
        self.decomposition = GraphDecomposition(
            clusters=clusters,
            tree_decomposition=tree_decomposition,
            tree_width=tree_width
        )
        
        self.logger.debug(
            f"グラフ最適化完了: "
            f"クラスタ数={len(clusters)}, "
            f"木幅={tree_width}"
        )
        
        return self.decomposition
    
    def add_dynamic_constraint(
        self,
        arc: Arc,
        weight: float = 1.0
    ):
        """動的に制約を追加"""
        self.stats['dynamic_updates'] += 1
        
        self.dynamic_constraints.add(arc)
        self.constraint_weights[arc] = weight
        
        # グラフに追加
        var1_id = self._get_variable_id(arc.var1)
        var2_id = self._get_variable_id(arc.var2)
        
        self.graph.add_edge(
            var1_id, var2_id,
            arc=arc,
            weight=weight,
            constraint_type=arc.constraint_type,
            dynamic=True
        )
        
        # クラスタリングの更新が必要な場合
        if self.decomposition and len(self.dynamic_constraints) % 10 == 0:
            self._update_clusters()
    
    def remove_dynamic_constraint(self, arc: Arc):
        """動的に制約を削除"""
        if arc in self.dynamic_constraints:
            self.dynamic_constraints.remove(arc)
            
            var1_id = self._get_variable_id(arc.var1)
            var2_id = self._get_variable_id(arc.var2)
            
            if self.graph.has_edge(var1_id, var2_id):
                # 動的制約のみ削除
                edge_data = self.graph[var1_id][var2_id]
                if edge_data.get('dynamic', False):
                    self.graph.remove_edge(var1_id, var2_id)
    
    def get_constraint_ordering(
        self,
        variable: Optional[Variable] = None
    ) -> List[Arc]:
        """
        制約の処理順序を取得
        
        重要度の高い制約から順に返す
        """
        if variable:
            # 特定の変数に関連する制約
            var_id = self._get_variable_id(variable)
            related_arcs = []
            
            for neighbor in self.graph.neighbors(var_id):
                edge_data = self.graph[var_id][neighbor]
                arc = edge_data['arc']
                weight = edge_data['weight']
                related_arcs.append((arc, weight))
            
            # 重み順にソート
            related_arcs.sort(key=lambda x: x[1], reverse=True)
            return [arc for arc, _ in related_arcs]
        else:
            # 全制約を重み順に
            all_arcs = []
            for u, v, data in self.graph.edges(data=True):
                arc = data['arc']
                weight = data['weight']
                all_arcs.append((arc, weight))
            
            all_arcs.sort(key=lambda x: x[1], reverse=True)
            return [arc for arc, _ in all_arcs]
    
    def find_minimal_conflict_set(
        self,
        conflicting_assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> Set[Arc]:
        """最小競合セットを見つける"""
        conflict_arcs = set()
        
        # 競合している変数ペアを特定
        var_list = list(conflicting_assignments.keys())
        for i, var1 in enumerate(var_list):
            for var2 in var_list[i+1:]:
                var1_id = self._get_variable_id(var1)
                var2_id = self._get_variable_id(var2)
                
                if self.graph.has_edge(var1_id, var2_id):
                    edge_data = self.graph[var1_id][var2_id]
                    arc = edge_data['arc']
                    
                    # この制約が違反されているかチェック
                    val1 = conflicting_assignments[var1]
                    val2 = conflicting_assignments[var2]
                    
                    if self._violates_constraint(arc, val1, val2):
                        conflict_arcs.add(arc)
        
        # 最小セットに削減（簡易実装）
        # TODO: より洗練されたアルゴリズムで最小化
        return conflict_arcs
    
    def _decompose_graph(self) -> List[Set[Variable]]:
        """グラフを連結成分に分解"""
        components = []
        
        for component in nx.connected_components(self.graph):
            variables = set()
            for node_id in component:
                variables.add(self.variable_map[node_id])
            components.append(variables)
        
        return components
    
    def _cluster_constraints(self) -> List[ConstraintCluster]:
        """制約をクラスタリング"""
        self.stats['decompositions'] += 1
        
        if self.graph.number_of_nodes() < 2:
            # ノードが少ない場合は単一クラスタ
            return [self._create_single_cluster()]
        
        # スペクトラルクラスタリング用の隣接行列
        nodes = list(self.graph.nodes())
        n = len(nodes)
        adjacency_matrix = np.zeros((n, n))
        
        node_to_idx = {node: i for i, node in enumerate(nodes)}
        
        for u, v, data in self.graph.edges(data=True):
            i = node_to_idx[u]
            j = node_to_idx[v]
            weight = data['weight']
            adjacency_matrix[i, j] = weight
            adjacency_matrix[j, i] = weight
        
        # クラスタ数を決定（ヒューリスティック）
        n_clusters = min(max(2, n // 20), 10)
        
        # スペクトラルクラスタリング
        try:
            clustering = SpectralClustering(
                n_clusters=n_clusters,
                affinity='precomputed',
                random_state=42
            )
            labels = clustering.fit_predict(adjacency_matrix)
        except:
            # フォールバック：単純な分割
            labels = [i % n_clusters for i in range(n)]
        
        # クラスタを作成
        cluster_vars = defaultdict(set)
        for i, node in enumerate(nodes):
            cluster_vars[labels[i]].add(self.variable_map[node])
        
        clusters = []
        for cluster_id, variables in cluster_vars.items():
            cluster = self._create_cluster(cluster_id, variables)
            clusters.append(cluster)
        
        return clusters
    
    def _create_cluster(
        self,
        cluster_id: int,
        variables: Set[Variable]
    ) -> ConstraintCluster:
        """クラスタを作成"""
        internal_arcs = set()
        external_arcs = set()
        
        var_ids = {self._get_variable_id(v) for v in variables}
        
        for var in variables:
            var_id = self._get_variable_id(var)
            
            for neighbor in self.graph.neighbors(var_id):
                edge_data = self.graph[var_id][neighbor]
                arc = edge_data['arc']
                
                if neighbor in var_ids:
                    internal_arcs.add(arc)
                else:
                    external_arcs.add(arc)
        
        return ConstraintCluster(
            id=cluster_id,
            variables=variables,
            internal_arcs=internal_arcs,
            external_arcs=external_arcs
        )
    
    def _create_single_cluster(self) -> ConstraintCluster:
        """単一クラスタを作成"""
        all_vars = set(self.variable_map.values())
        all_arcs = set()
        
        for u, v, data in self.graph.edges(data=True):
            all_arcs.add(data['arc'])
        
        return ConstraintCluster(
            id=0,
            variables=all_vars,
            internal_arcs=all_arcs,
            external_arcs=set()
        )
    
    def _calculate_cluster_priorities(self, clusters: List[ConstraintCluster]):
        """クラスタの優先度を計算"""
        for cluster in clusters:
            # 優先度の要素
            size_factor = cluster.size() / 100  # 大きいクラスタを優先
            density_factor = cluster.density()  # 密なクラスタを優先
            
            # 特殊クラスの優先度
            special_factor = 0.0
            for var in cluster.variables:
                if var.class_ref.class_number == 5:  # 5組
                    special_factor += 0.3
                elif var.class_ref.class_number in [6, 7]:  # 交流学級
                    special_factor += 0.2
            
            cluster.priority = size_factor + density_factor + special_factor
    
    def _tree_decomposition(self) -> Tuple[nx.Graph, int]:
        """木分解を実行（簡易版）"""
        # NetworkXの木分解を使用
        try:
            decomp, width = nx.algorithms.approximation.treewidth_min_degree(self.graph)
            return decomp, width
        except:
            # フォールバック
            return nx.Graph(), -1
    
    def _update_clusters(self):
        """クラスタを更新"""
        if self.decomposition:
            # 簡易更新：外部アークの再計算のみ
            for cluster in self.decomposition.clusters:
                cluster.external_arcs.clear()
                
                var_ids = {self._get_variable_id(v) for v in cluster.variables}
                
                for var in cluster.variables:
                    var_id = self._get_variable_id(var)
                    
                    for neighbor in self.graph.neighbors(var_id):
                        if neighbor not in var_ids:
                            edge_data = self.graph[var_id][neighbor]
                            cluster.external_arcs.add(edge_data['arc'])
    
    def _get_variable_id(self, variable: Variable) -> str:
        """変数のIDを取得"""
        return f"{variable.time_slot.day}_{variable.time_slot.period}_{variable.class_ref.grade}_{variable.class_ref.class_number}"
    
    def _calculate_arc_weight(self, arc: Arc) -> float:
        """アークの重みを計算"""
        # 制約タイプによる基本重み
        type_weights = {
            "teacher_conflict": 10.0,
            "daily_duplicate": 5.0,
            "exchange_sync": 8.0,
            "grade5_sync": 8.0,
            "jiritsu_parent": 7.0
        }
        
        base_weight = type_weights.get(arc.constraint_type, 1.0)
        
        # 特殊クラスの重み調整
        if arc.var1.class_ref.class_number == 5 or arc.var2.class_ref.class_number == 5:
            base_weight *= 1.5
        
        return base_weight
    
    def _violates_constraint(
        self,
        arc: Arc,
        val1: Tuple[str, Optional[str]],
        val2: Tuple[str, Optional[str]]
    ) -> bool:
        """制約違反をチェック"""
        if arc.constraint_type == "teacher_conflict":
            return val1[1] and val2[1] and val1[1] == val2[1]
        elif arc.constraint_type == "daily_duplicate":
            return val1[0] == val2[0]
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'components': nx.number_connected_components(self.graph),
            'density': nx.density(self.graph),
            'graph_builds': self.stats['graph_builds'],
            'decompositions': self.stats['decompositions'],
            'optimizations': self.stats['optimizations'],
            'dynamic_updates': self.stats['dynamic_updates']
        }
        
        if self.decomposition:
            stats['clusters'] = len(self.decomposition.clusters)
            stats['tree_width'] = self.decomposition.tree_width
            stats['avg_cluster_size'] = np.mean([c.size() for c in self.decomposition.clusters])
            stats['avg_cluster_density'] = np.mean([c.density() for c in self.decomposition.clusters])
        
        return stats