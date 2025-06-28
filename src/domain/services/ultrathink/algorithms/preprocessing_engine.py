"""
前処理エンジン

制約の簡約化、対称性の破壊、冗長制約の除去など、
問題を解く前の最適化処理を実装。
"""
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict, Counter
import itertools

from .constraint_propagation import Variable, Domain, Arc, ConstraintPropagation
from ....entities.school import School
from ....value_objects.time_slot import TimeSlot, ClassReference
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class SymmetryGroup:
    """対称性グループ"""
    variables: Set[Variable]
    symmetry_type: str  # "time_slot", "class", "teacher", etc.
    breaking_order: List[Variable]  # 対称性破壊の順序


@dataclass
class PreprocessingResult:
    """前処理結果"""
    reduced_variables: int
    reduced_values: int
    removed_constraints: int
    symmetries_broken: int
    implied_assignments: Dict[Variable, Tuple[str, Optional[str]]]
    processing_time: float


class PreprocessingEngine(LoggingMixin):
    """前処理エンジン"""
    
    def __init__(self, school: School):
        super().__init__()
        self.school = school
        
        # 固定科目リスト
        self.fixed_subjects = {
            "欠", "YT", "学", "学活", "総", "総合",
            "道", "道徳", "学総", "行", "行事", "テスト", "技家"
        }
        
        # 統計
        self.stats = {
            'preprocessing_runs': 0,
            'total_reductions': 0,
            'symmetries_detected': 0,
            'implied_assignments': 0
        }
    
    def preprocess(
        self,
        variables: Set[Variable],
        domains: Dict[Variable, Domain],
        arcs: Set[Arc],
        initial_assignments: Dict[Variable, Tuple[str, Optional[str]]] = None
    ) -> PreprocessingResult:
        """
        完全な前処理を実行
        
        Returns:
            前処理結果
        """
        import time
        start_time = time.time()
        
        self.logger.info("前処理開始")
        self.stats['preprocessing_runs'] += 1
        
        initial_var_count = len(variables)
        initial_value_count = sum(d.size() for d in domains.values())
        initial_arc_count = len(arcs)
        
        # 結果を保存
        implied_assignments = initial_assignments or {}
        
        # 1. 単一値ドメインの処理
        self._process_singleton_domains(domains, implied_assignments)
        
        # 2. 明らかに無効な値の削除
        self._remove_invalid_values(domains, implied_assignments)
        
        # 3. 対称性の検出と破壊
        symmetries = self._detect_symmetries(variables, domains)
        self._break_symmetries(symmetries, domains)
        
        # 4. 冗長制約の除去
        arcs = self._remove_redundant_constraints(arcs, domains)
        
        # 5. 必須割り当ての推論
        self._infer_necessary_assignments(variables, domains, implied_assignments)
        
        # 6. ドメインの最終削減
        self._final_domain_reduction(domains, implied_assignments)
        
        # 統計計算
        final_var_count = len([v for v in variables if v not in implied_assignments])
        final_value_count = sum(d.size() for v, d in domains.items() if v not in implied_assignments)
        final_arc_count = len(arcs)
        
        processing_time = time.time() - start_time
        
        result = PreprocessingResult(
            reduced_variables=initial_var_count - final_var_count,
            reduced_values=initial_value_count - final_value_count,
            removed_constraints=initial_arc_count - final_arc_count,
            symmetries_broken=len(symmetries),
            implied_assignments=implied_assignments,
            processing_time=processing_time
        )
        
        self.logger.info(
            f"前処理完了: "
            f"変数削減={result.reduced_variables}, "
            f"値削減={result.reduced_values}, "
            f"制約削減={result.removed_constraints}, "
            f"時間={processing_time:.3f}秒"
        )
        
        return result
    
    def _process_singleton_domains(
        self,
        domains: Dict[Variable, Domain],
        implied_assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ):
        """単一値ドメインを処理"""
        for var, domain in domains.items():
            if var not in implied_assignments and domain.size() == 1:
                value = next(iter(domain.values))
                implied_assignments[var] = value
                self.stats['implied_assignments'] += 1
                
                self.logger.debug(
                    f"単一値ドメイン検出: {var} = {value}"
                )
    
    def _remove_invalid_values(
        self,
        domains: Dict[Variable, Domain],
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ):
        """明らかに無効な値を削除"""
        total_removed = 0
        
        for var, domain in domains.items():
            if var in assignments:
                continue
            
            values_to_remove = []
            
            for value in domain.values:
                subject_name, teacher_name = value
                
                # 固定科目の不適切な配置
                if self._is_invalid_fixed_subject_placement(var, subject_name):
                    values_to_remove.append(value)
                    continue
                
                # 教師不在
                if teacher_name and self._is_teacher_unavailable(var, teacher_name):
                    values_to_remove.append(value)
                    continue
                
                # 必要時数を超える配置
                if self._exceeds_required_hours(var, subject_name, assignments):
                    values_to_remove.append(value)
                    continue
            
            for value in values_to_remove:
                domain.remove_value(value)
                total_removed += 1
        
        self.stats['total_reductions'] += total_removed
        self.logger.debug(f"無効な値を{total_removed}個削除")
    
    def _detect_symmetries(
        self,
        variables: Set[Variable],
        domains: Dict[Variable, Domain]
    ) -> List[SymmetryGroup]:
        """対称性を検出"""
        symmetries = []
        self.stats['symmetries_detected'] = 0
        
        # 時間スロットの対称性
        time_symmetries = self._detect_time_slot_symmetries(variables, domains)
        symmetries.extend(time_symmetries)
        
        # クラスの対称性
        class_symmetries = self._detect_class_symmetries(variables, domains)
        symmetries.extend(class_symmetries)
        
        # 教師の対称性
        teacher_symmetries = self._detect_teacher_symmetries(variables, domains)
        symmetries.extend(teacher_symmetries)
        
        self.stats['symmetries_detected'] = len(symmetries)
        self.logger.debug(f"{len(symmetries)}個の対称性グループを検出")
        
        return symmetries
    
    def _detect_time_slot_symmetries(
        self,
        variables: Set[Variable],
        domains: Dict[Variable, Domain]
    ) -> List[SymmetryGroup]:
        """時間スロットの対称性を検出"""
        symmetries = []
        
        # 同じ曜日の連続する時限で同じドメインを持つ変数を探す
        for day in ["月", "火", "水", "木", "金"]:
            for class_ref in set(v.class_ref for v in variables):
                period_vars = []
                
                for period in range(1, 6):  # 6限は特殊なので除外
                    var = next(
                        (v for v in variables 
                         if v.time_slot.day == day and 
                         v.time_slot.period == period and
                         v.class_ref == class_ref),
                        None
                    )
                    if var:
                        period_vars.append(var)
                
                # 連続する同一ドメインを探す
                i = 0
                while i < len(period_vars) - 1:
                    symmetric_group = [period_vars[i]]
                    j = i + 1
                    
                    while j < len(period_vars):
                        if self._have_same_domain(
                            domains.get(period_vars[i]),
                            domains.get(period_vars[j])
                        ):
                            symmetric_group.append(period_vars[j])
                            j += 1
                        else:
                            break
                    
                    if len(symmetric_group) > 1:
                        symmetries.append(SymmetryGroup(
                            variables=set(symmetric_group),
                            symmetry_type="time_slot",
                            breaking_order=symmetric_group
                        ))
                    
                    i = j if j > i + 1 else i + 1
        
        return symmetries
    
    def _detect_class_symmetries(
        self,
        variables: Set[Variable],
        domains: Dict[Variable, Domain]
    ) -> List[SymmetryGroup]:
        """クラスの対称性を検出"""
        symmetries = []
        
        # 同じ学年の異なるクラスで対称性を探す
        for grade in [1, 2, 3]:
            grade_classes = [
                ClassReference(grade, i) for i in range(1, 4)
                if i != 5  # 5組は特殊
            ]
            
            # 各時間スロットで対称なクラスを探す
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 6):
                    time_slot = TimeSlot(day, period)
                    
                    class_vars = []
                    for class_ref in grade_classes:
                        var = next(
                            (v for v in variables
                             if v.time_slot == time_slot and
                             v.class_ref == class_ref),
                            None
                        )
                        if var:
                            class_vars.append(var)
                    
                    # 同じドメインを持つクラスをグループ化
                    if len(class_vars) > 1:
                        domain_groups = defaultdict(list)
                        for var in class_vars:
                            domain_key = self._get_domain_key(domains.get(var))
                            domain_groups[domain_key].append(var)
                        
                        for group in domain_groups.values():
                            if len(group) > 1:
                                symmetries.append(SymmetryGroup(
                                    variables=set(group),
                                    symmetry_type="class",
                                    breaking_order=sorted(
                                        group,
                                        key=lambda v: v.class_ref.class_number
                                    )
                                ))
        
        return symmetries
    
    def _detect_teacher_symmetries(
        self,
        variables: Set[Variable],
        domains: Dict[Variable, Domain]
    ) -> List[SymmetryGroup]:
        """教師の対称性を検出"""
        # 実装は省略（複雑になるため）
        return []
    
    def _break_symmetries(
        self,
        symmetries: List[SymmetryGroup],
        domains: Dict[Variable, Domain]
    ):
        """対称性を破壊"""
        for symmetry in symmetries:
            if symmetry.symmetry_type == "time_slot":
                # 時間順序制約を追加
                self._add_time_ordering_constraints(symmetry, domains)
            elif symmetry.symmetry_type == "class":
                # クラス順序制約を追加
                self._add_class_ordering_constraints(symmetry, domains)
    
    def _add_time_ordering_constraints(
        self,
        symmetry: SymmetryGroup,
        domains: Dict[Variable, Domain]
    ):
        """時間順序制約を追加"""
        # 最初の変数のドメインを制限
        if symmetry.breaking_order:
            first_var = symmetry.breaking_order[0]
            if first_var in domains:
                domain = domains[first_var]
                # 主要科目を優先
                prioritized_values = [
                    v for v in domain.values
                    if v[0] in ["国", "数", "英", "理", "社"]
                ]
                if prioritized_values:
                    domain.values = set(prioritized_values[:len(prioritized_values)//2])
    
    def _add_class_ordering_constraints(
        self,
        symmetry: SymmetryGroup,
        domains: Dict[Variable, Domain]
    ):
        """クラス順序制約を追加"""
        # 実装は省略
        pass
    
    def _remove_redundant_constraints(
        self,
        arcs: Set[Arc],
        domains: Dict[Variable, Domain]
    ) -> Set[Arc]:
        """冗長制約を除去"""
        non_redundant = set()
        removed_count = 0
        
        for arc in arcs:
            # 空ドメインの変数に関する制約は不要
            if (arc.var1 in domains and domains[arc.var1].is_empty()) or \
               (arc.var2 in domains and domains[arc.var2].is_empty()):
                removed_count += 1
                continue
            
            # 単一値ドメイン同士で矛盾しない制約は不要
            if (arc.var1 in domains and domains[arc.var1].size() == 1 and
                arc.var2 in domains and domains[arc.var2].size() == 1):
                val1 = next(iter(domains[arc.var1].values))
                val2 = next(iter(domains[arc.var2].values))
                
                if not self._values_conflict(arc, val1, val2):
                    removed_count += 1
                    continue
            
            non_redundant.add(arc)
        
        self.logger.debug(f"{removed_count}個の冗長制約を除去")
        return non_redundant
    
    def _infer_necessary_assignments(
        self,
        variables: Set[Variable],
        domains: Dict[Variable, Domain],
        implied_assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ):
        """必須割り当てを推論"""
        # 各クラスの必要時数を計算
        for class_ref in set(v.class_ref for v in variables):
            subject_needs = self._calculate_subject_needs(class_ref, implied_assignments)
            
            # 必要時数と利用可能スロット数が同じ科目を特定
            available_slots = [
                v for v in variables
                if v.class_ref == class_ref and v not in implied_assignments
            ]
            
            for subject_name, needed in subject_needs.items():
                if needed == len(available_slots):
                    # この科目で全スロットを埋める必要がある
                    self.logger.debug(
                        f"{class_ref}の全ての空きスロットに{subject_name}が必要"
                    )
                    
                    # 適切な教師を見つける
                    subject = next(
                        (s for s in self.school.get_all_subjects() if s.name == subject_name),
                        None
                    )
                    if subject:
                        teacher = self.school.get_assigned_teacher(subject, class_ref)
                        teacher_name = teacher.name if teacher else None
                        
                        for var in available_slots:
                            if var in domains:
                                domains[var].values = {(subject_name, teacher_name)}
    
    def _final_domain_reduction(
        self,
        domains: Dict[Variable, Domain],
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ):
        """最終的なドメイン削減"""
        # 割り当て済み変数の影響を反映
        for var, value in assignments.items():
            if value[1]:  # 教師がいる場合
                # 同じ時間の他のクラスから教師を削除
                for other_var, domain in domains.items():
                    if (other_var.time_slot == var.time_slot and
                        other_var != var and
                        other_var not in assignments):
                        
                        values_to_remove = [
                            v for v in domain.values
                            if v[1] == value[1]
                        ]
                        for v in values_to_remove:
                            domain.remove_value(v)
    
    def _is_invalid_fixed_subject_placement(
        self,
        variable: Variable,
        subject_name: str
    ) -> bool:
        """固定科目の不適切な配置かチェック"""
        if subject_name not in self.fixed_subjects:
            return False
        
        # 固定科目の配置ルール
        if subject_name == "欠" and not (
            variable.time_slot.day == "月" and variable.time_slot.period == 6
        ):
            return True
        
        if subject_name == "YT" and variable.time_slot.period != 6:
            return True
        
        return False
    
    def _is_teacher_unavailable(
        self,
        variable: Variable,
        teacher_name: str
    ) -> bool:
        """教師が不在かチェック"""
        teacher = next(
            (t for t in self.school.get_all_teachers() if t.name == teacher_name),
            None
        )
        
        if teacher:
            return self.school.is_teacher_unavailable(
                variable.time_slot.day,
                variable.time_slot.period,
                teacher
            )
        
        return False
    
    def _exceeds_required_hours(
        self,
        variable: Variable,
        subject_name: str,
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> bool:
        """必要時数を超えるかチェック"""
        # 現在の配置数を計算
        current_count = sum(
            1 for var, val in assignments.items()
            if var.class_ref == variable.class_ref and val[0] == subject_name
        )
        
        # 標準時数を取得
        subject = next(
            (s for s in self.school.get_all_subjects() if s.name == subject_name),
            None
        )
        
        if subject:
            standard_hours = self.school.get_standard_hours(variable.class_ref, subject)
            return current_count >= int(standard_hours)
        
        return False
    
    def _have_same_domain(
        self,
        domain1: Optional[Domain],
        domain2: Optional[Domain]
    ) -> bool:
        """2つのドメインが同じかチェック"""
        if not domain1 or not domain2:
            return False
        return domain1.values == domain2.values
    
    def _get_domain_key(self, domain: Optional[Domain]) -> str:
        """ドメインのキーを生成"""
        if not domain:
            return "empty"
        
        values = sorted(list(domain.values))
        return str(values)
    
    def _values_conflict(
        self,
        arc: Arc,
        val1: Tuple[str, Optional[str]],
        val2: Tuple[str, Optional[str]]
    ) -> bool:
        """2つの値が競合するかチェック"""
        if arc.constraint_type == "teacher_conflict":
            return val1[1] and val2[1] and val1[1] == val2[1]
        elif arc.constraint_type == "daily_duplicate":
            return val1[0] == val2[0]
        return False
    
    def _calculate_subject_needs(
        self,
        class_ref: ClassReference,
        assignments: Dict[Variable, Tuple[str, Optional[str]]]
    ) -> Dict[str, int]:
        """クラスの科目別必要時数を計算"""
        needs = {}
        
        # 標準時数を取得
        standard_hours = self.school.get_all_standard_hours(class_ref)
        
        for subject, hours in standard_hours.items():
            if hours > 0 and subject.name not in self.fixed_subjects:
                # 現在の配置数
                current = sum(
                    1 for var, val in assignments.items()
                    if var.class_ref == class_ref and val[0] == subject.name
                )
                
                needed = int(hours) - current
                if needed > 0:
                    needs[subject.name] = needed
        
        return needs
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'preprocessing_runs': self.stats['preprocessing_runs'],
            'total_reductions': self.stats['total_reductions'],
            'symmetries_detected': self.stats['symmetries_detected'],
            'implied_assignments': self.stats['implied_assignments']
        }