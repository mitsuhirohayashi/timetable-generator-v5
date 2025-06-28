"""スマートCSPソルバーの実装（制約伝播、MRV/LCVヒューリスティック付き）"""
import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import copy

from ....domain.interfaces.advanced_csp_solver import AdvancedCSPSolver, CSPVariable, Domain
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.base import ConstraintValidator
from ....domain.interfaces.csp_configuration import ICSPConfiguration


class SmartCSPSolver(AdvancedCSPSolver):
    """制約伝播とヒューリスティックを使用したスマートCSPソルバー"""
    
    def __init__(self, config: ICSPConfiguration, constraint_validator: ConstraintValidator):
        self.config = config
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
        
        # 統計情報
        self.stats = {
            'nodes_explored': 0,
            'backtracks': 0,
            'constraint_propagations': 0,
            'domain_wipeouts': 0
        }
    
    def solve(self, school: School, initial_schedule: Optional[Schedule] = None) -> Schedule:
        """CSP問題を解く"""
        self.logger.info("スマートCSPソルバーを開始")
        
        # 初期化
        schedule = initial_schedule or Schedule()
        variables = self._initialize_variables(school, schedule)
        
        # バックトラッキング探索
        result = self._backtrack_search(variables, schedule, school)
        
        if result:
            self.logger.info(f"解を発見！ 探索ノード数: {self.stats['nodes_explored']}, "
                           f"バックトラック数: {self.stats['backtracks']}")
        else:
            self.logger.warning("解が見つかりませんでした")
        
        return schedule
    
    def _initialize_variables(self, school: School, schedule: Schedule) -> Dict[Tuple[TimeSlot, ClassReference], CSPVariable]:
        """CSP変数を初期化"""
        variables = {}
        
        for day in self.config.weekdays:
            for period in range(self.config.periods_min, self.config.periods_max + 1):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 既に割り当てがある場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # ロックされている場合もスキップ
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    # ドメインを構築
                    domain = self._build_domain(time_slot, class_ref, school, schedule)
                    
                    # 変数を作成
                    var = CSPVariable(
                        time_slot=time_slot,
                        class_ref=class_ref,
                        domain=domain
                    )
                    variables[(time_slot, class_ref)] = var
        
        self.logger.info(f"CSP変数を{len(variables)}個初期化しました")
        return variables
    
    def _build_domain(self, time_slot: TimeSlot, class_ref: ClassReference, 
                     school: School, schedule: Schedule) -> Domain:
        """変数のドメインを構築"""
        possible_assignments = set()
        
        # 必要な教科を取得
        for subject in school.get_required_subjects(class_ref):
            if subject.is_protected_subject():
                continue
            
            # 必要時数を確認
            required_hours = int(round(school.get_standard_hours(class_ref, subject)))
            placed_hours = sum(
                1 for _, assignment in schedule.get_all_assignments()
                if assignment.class_ref == class_ref and assignment.subject == subject
            )
            
            if placed_hours >= required_hours:
                continue
            
            # 教師を取得
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher:
                possible_assignments.add((subject, teacher))
        
        return Domain(
            time_slot=time_slot,
            class_ref=class_ref,
            possible_assignments=possible_assignments
        )
    
    def _backtrack_search(self, variables: Dict[Tuple[TimeSlot, ClassReference], CSPVariable],
                         schedule: Schedule, school: School) -> bool:
        """バックトラッキング探索"""
        self.stats['nodes_explored'] += 1
        
        # 未割当変数を選択（MRV）
        var = self.select_unassigned_variable(list(variables.values()))
        if not var:
            return True  # すべて割り当て済み
        
        # ドメイン値を順序付け（LCV）
        ordered_values = self.order_domain_values(var, school, schedule)
        
        for subject, teacher in ordered_values:
            # 割り当てを試みる
            assignment = Assignment(var.class_ref, subject, teacher)
            
            # 制約チェック
            if not self.constraint_validator.check_assignment(schedule, school, var.time_slot, assignment):
                continue
            
            try:
                # 割り当て
                schedule.assign(var.time_slot, assignment)
                var.is_assigned = True
                var.assignment = assignment
                
                # ドメインのバックアップ
                domain_backup = self._backup_domains(variables)
                
                # 制約伝播
                if self.propagate_constraints(var, assignment, variables, school):
                    # 再帰的に探索
                    if self._backtrack_search(variables, schedule, school):
                        return True
                
                # バックトラック
                self.stats['backtracks'] += 1
                schedule.remove_assignment(var.time_slot, var.class_ref)
                var.is_assigned = False
                var.assignment = None
                
                # ドメインを復元
                self._restore_domains(variables, domain_backup)
                
            except ValueError:
                # 固定科目保護などで配置できない場合
                continue
        
        return False
    
    def select_unassigned_variable(self, variables: List[CSPVariable]) -> Optional[CSPVariable]:
        """MRVヒューリスティックで未割当変数を選択"""
        unassigned = [v for v in variables if not v.is_assigned]
        
        if not unassigned:
            return None
        
        # ドメインサイズが最小の変数を選択
        return min(unassigned, key=lambda v: v.domain.size())
    
    def order_domain_values(self, variable: CSPVariable, school: School, 
                          schedule: Schedule) -> List[Tuple[Subject, Teacher]]:
        """LCVヒューリスティックでドメイン値を順序付け"""
        values_with_score = []
        
        for subject, teacher in variable.domain.possible_assignments:
            # この値を選んだ場合の制約度を計算
            constraint_score = self._calculate_constraint_score(
                variable, subject, teacher, school, schedule
            )
            values_with_score.append(((subject, teacher), constraint_score))
        
        # 制約度が低い（他への影響が少ない）順にソート
        values_with_score.sort(key=lambda x: x[1])
        
        return [value for value, _ in values_with_score]
    
    def _calculate_constraint_score(self, variable: CSPVariable, subject: Subject, 
                                  teacher: Teacher, school: School, schedule: Schedule) -> float:
        """値の制約度を計算（低いほど良い）"""
        score = 0.0
        
        # 同じ時間の他のクラスへの影響
        for class_ref in school.get_all_classes():
            if class_ref == variable.class_ref:
                continue
            
            # 教師の競合
            existing = schedule.get_assignment(variable.time_slot, class_ref)
            if existing and existing.teacher and existing.teacher.name == teacher.name:
                score += 100  # 教師の重複は高コスト
            
            # 将来の配置可能性への影響
            if self._would_reduce_future_options(variable, subject, teacher, class_ref, school, schedule):
                score += 10
        
        # 日内重複のチェック
        daily_count = sum(
            1 for period in range(1, 7)
            for slot, assignment in schedule.get_all_assignments()
            if (slot.day == variable.time_slot.day and slot.period == period and
                assignment.class_ref == variable.class_ref and assignment.subject == subject)
        )
        if daily_count > 0:
            score += 50  # 日内重複は中コスト
        
        return score
    
    def _would_reduce_future_options(self, variable: CSPVariable, subject: Subject,
                                   teacher: Teacher, other_class: ClassReference,
                                   school: School, schedule: Schedule) -> bool:
        """この配置が他のクラスの将来の選択肢を減らすかどうか"""
        # 簡易的な実装：同じ教師が必要な場合にTrueを返す
        other_subjects = school.get_required_subjects(other_class)
        for other_subject in other_subjects:
            other_teacher = school.get_assigned_teacher(other_subject, other_class)
            if other_teacher and other_teacher.name == teacher.name:
                return True
        return False
    
    def propagate_constraints(self, variable: CSPVariable, assignment: Assignment,
                            variables: Dict[Tuple[TimeSlot, ClassReference], CSPVariable],
                            school: School) -> bool:
        """制約伝播（アークコンシステンシー）"""
        self.stats['constraint_propagations'] += 1
        
        # 影響を受ける変数のキュー
        queue = []
        
        # 同じ時間の他のクラス
        for class_ref in school.get_all_classes():
            if class_ref == variable.class_ref:
                continue
            key = (variable.time_slot, class_ref)
            if key in variables:
                queue.append(variables[key])
        
        # 同じクラスの他の時間
        for day in self.config.weekdays:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if time_slot == variable.time_slot:
                    continue
                key = (time_slot, variable.class_ref)
                if key in variables:
                    queue.append(variables[key])
        
        # 各変数のドメインを更新
        while queue:
            var = queue.pop(0)
            
            # 無効な値を削除
            invalid_values = set()
            for subject, teacher in var.domain.possible_assignments:
                test_assignment = Assignment(var.class_ref, subject, teacher)
                
                # 制約チェック
                if not self._is_consistent_with(test_assignment, var.time_slot, variable, assignment, school):
                    invalid_values.add((subject, teacher))
            
            # ドメインから削除
            if invalid_values:
                var.domain.possible_assignments -= invalid_values
                
                # ドメインが空になった場合は失敗
                if var.domain.is_empty():
                    self.stats['domain_wipeouts'] += 1
                    return False
        
        return True
    
    def _is_consistent_with(self, test_assignment: Assignment, test_slot: TimeSlot,
                          assigned_var: CSPVariable, assigned_value: Assignment,
                          school: School) -> bool:
        """テスト割り当てが既存の割り当てと整合するか"""
        # 教師の重複チェック
        if (test_assignment.teacher and assigned_value.teacher and
            test_assignment.teacher.name == assigned_value.teacher.name and
            test_slot == assigned_var.time_slot):
            # 5組の例外処理
            grade5_classes = {"1年5組", "2年5組", "3年5組"}
            if not (test_assignment.class_ref.full_name in grade5_classes and
                   assigned_value.class_ref.full_name in grade5_classes):
                return False
        
        # 日内重複チェック（同じクラス、同じ日、同じ教科）
        if (test_assignment.class_ref == assigned_value.class_ref and
            test_slot.day == assigned_var.time_slot.day and
            test_assignment.subject.name == assigned_value.subject.name):
            return False
        
        return True
    
    def _backup_domains(self, variables: Dict[Tuple[TimeSlot, ClassReference], CSPVariable]) -> Dict:
        """ドメインのバックアップを作成"""
        backup = {}
        for key, var in variables.items():
            backup[key] = copy.deepcopy(var.domain.possible_assignments)
        return backup
    
    def _restore_domains(self, variables: Dict[Tuple[TimeSlot, ClassReference], CSPVariable], 
                        backup: Dict) -> None:
        """ドメインを復元"""
        for key, var in variables.items():
            if key in backup:
                var.domain.possible_assignments = backup[key]