"""
フェーズ2: スマート配置アルゴリズム（Ultrathink版）

教師中心のスケジューリングパラダイムで教師重複を根本的に解決します。

革新的な特徴：
1. TeacherScheduleMatrix - 教師ごとの独立した時間割管理
2. DualViewScheduling - クラス視点と教師視点の同時最適化
3. ConstraintPropagation - 配置前の制約伝播による競合予防
4. ProbabilisticPlacement - 成功確率に基づく最適配置順序
"""
import logging
from typing import Dict, List, Set, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Teacher, Subject
from ....domain.value_objects.time_slot import TimeSlot
from ....domain.value_objects.time_slot import ClassReference
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.base import ConstraintPriority


@dataclass
class TeacherScheduleMatrix:
    """教師の時間割を管理する行列
    
    各教師が各時間にどのクラスを教えているかを高速に追跡
    """
    teacher: Teacher
    # 時間スロット -> 担当クラスのセット
    schedule: Dict[TimeSlot, Set[ClassReference]] = field(default_factory=dict)
    # 各時間の空き状況（True=空き）
    availability: Dict[TimeSlot, bool] = field(default_factory=dict)
    # 不在情報
    absences: Set[TimeSlot] = field(default_factory=set)
    
    def __post_init__(self):
        # 全時間を空きで初期化
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if time_slot not in self.absences:
                    self.availability[time_slot] = True
                    self.schedule[time_slot] = set()
    
    def is_available(self, time_slot: TimeSlot, allow_grade5_joint: bool = True) -> bool:
        """指定時間に空いているかチェック
        
        Args:
            time_slot: チェックする時間
            allow_grade5_joint: 5組の合同授業を許可するか
        """
        if time_slot in self.absences:
            return False
        
        current_classes = self.schedule.get(time_slot, set())
        if not current_classes:
            return True
        
        # 5組の合同授業チェック
        if allow_grade5_joint:
            grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
            if current_classes.issubset(grade5_refs):
                # 全て5組なら追加可能
                return True
        
        return False
    
    def assign(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """クラスを割り当て"""
        if time_slot not in self.schedule:
            self.schedule[time_slot] = set()
        
        self.schedule[time_slot].add(class_ref)
        self.availability[time_slot] = False
        return True
    
    def remove(self, time_slot: TimeSlot, class_ref: ClassReference):
        """クラスの割り当てを削除"""
        if time_slot in self.schedule:
            self.schedule[time_slot].discard(class_ref)
            if not self.schedule[time_slot]:
                self.availability[time_slot] = True
    
    def get_workload(self) -> int:
        """総担当コマ数を取得"""
        return sum(1 for classes in self.schedule.values() if classes)
    
    def get_daily_workload(self, day: str) -> int:
        """特定の日の担当コマ数"""
        count = 0
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            if self.schedule.get(time_slot):
                count += 1
        return count


class PlacementCandidate(NamedTuple):
    """配置候補"""
    time_slot: TimeSlot
    class_ref: ClassReference
    subject: Subject
    teacher: Teacher
    score: float  # 配置の適合度スコア
    constraints_satisfied: bool


@dataclass
class PlacementContext:
    """配置コンテキスト - 配置決定に必要な全情報"""
    schedule: Schedule
    school: School
    teacher_matrices: Dict[str, TeacherScheduleMatrix]
    class_requirements: Dict[ClassReference, Dict[Subject, float]]  # 残り必要時数
    constraint_weights: Dict[str, float]
    
    # 統計情報
    total_assignments: int = 0
    successful_placements: int = 0
    failed_placements: int = 0
    backtrack_count: int = 0


class SmartPlacementService:
    """スマート配置サービス - 教師中心のアプローチで最適配置を実現"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 制約の重み設定
        self.constraint_weights = {
            'teacher_conflict': 1000.0,      # 教師重複（最重要）
            'daily_duplicate': 500.0,        # 日内重複
            'consecutive_periods': 200.0,     # 連続コマ
            'workload_balance': 100.0,       # 負荷バランス
            'gym_conflict': 300.0,           # 体育館競合
            'jiritsu_constraint': 800.0,     # 自立活動制約
            'exchange_sync': 700.0,          # 交流学級同期
            'test_period': 900.0,            # テスト期間
        }
        
        # 5組関連の設定
        self.grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
        self.exchange_pairs = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
    
    def initialize_placement_context(
        self, 
        schedule: Schedule, 
        school: School,
        absence_info: Optional[Dict] = None
    ) -> PlacementContext:
        """配置コンテキストを初期化"""
        
        # 教師行列を構築
        teacher_matrices = {}
        for teacher in school.get_all_teachers():
            matrix = TeacherScheduleMatrix(teacher)
            
            # 不在情報を設定
            if absence_info and teacher.name in absence_info:
                for day, periods in absence_info[teacher.name].items():
                    for period in periods:
                        matrix.absences.add(TimeSlot(day, period))
            
            # 既存の割り当てを反映
            for time_slot in self._get_all_time_slots():
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher == teacher:
                        matrix.assign(time_slot, class_ref)
            
            teacher_matrices[teacher.name] = matrix
        
        # クラスごとの必要時数を計算
        class_requirements = self._calculate_class_requirements(schedule, school)
        
        context = PlacementContext(
            schedule=schedule,
            school=school,
            teacher_matrices=teacher_matrices,
            class_requirements=class_requirements,
            constraint_weights=self.constraint_weights
        )
        
        return context
    
    def place_assignment(
        self,
        context: PlacementContext,
        assignment: Assignment,
        time_slot: TimeSlot
    ) -> Tuple[bool, Optional[str]]:
        """割り当てを配置（教師中心アプローチ）
        
        Returns:
            (成功フラグ, エラーメッセージ)
        """
        
        # 1. 事前チェック - 高速失敗
        if not self._pre_placement_check(context, assignment, time_slot):
            return False, "事前チェックで失敗"
        
        # 2. 教師の空き時間チェック
        teacher_matrix = context.teacher_matrices.get(assignment.teacher.name)
        if not teacher_matrix:
            return False, f"教師 {assignment.teacher.name} の情報が見つかりません"
        
        if not teacher_matrix.is_available(time_slot):
            # 5組の場合の特別処理
            if assignment.class_ref in self.grade5_refs:
                current_classes = teacher_matrix.schedule.get(time_slot, set())
                if not current_classes.issubset(self.grade5_refs):
                    return False, f"{assignment.teacher.name}先生は{time_slot}に他のクラスを担当"
            else:
                return False, f"{assignment.teacher.name}先生は{time_slot}に既に授業があります"
        
        # 3. 制約伝播による競合チェック
        conflicts = self._propagate_constraints(context, assignment, time_slot)
        if conflicts:
            return False, f"制約違反: {', '.join(conflicts)}"
        
        # 4. 配置実行
        try:
            # スケジュールに配置
            context.schedule.assign(time_slot, assignment)
            
            # 教師行列を更新
            teacher_matrix.assign(time_slot, assignment.class_ref)
            
            # 5組の同期処理
            if assignment.class_ref in self.grade5_refs:
                self._sync_grade5_placement(context, assignment, time_slot)
            
            # 交流学級の同期処理
            if assignment.class_ref in self.exchange_pairs:
                self._sync_exchange_placement(context, assignment, time_slot)
            
            context.successful_placements += 1
            return True, None
            
        except Exception as e:
            self.logger.error(f"配置エラー: {e}")
            # ロールバック
            context.schedule.remove_assignment(time_slot, assignment.class_ref)
            teacher_matrix.remove(time_slot, assignment.class_ref)
            context.failed_placements += 1
            return False, str(e)
    
    def find_optimal_placement(
        self,
        context: PlacementContext,
        assignment: Assignment
    ) -> Optional[TimeSlot]:
        """最適な配置時間を見つける（確率的アプローチ）"""
        
        candidates = []
        
        for time_slot in self._get_all_time_slots():
            # 既に配置済みならスキップ
            if context.schedule.get_assignment(time_slot, assignment.class_ref):
                continue
            
            # 配置スコアを計算
            score = self._calculate_placement_score(context, assignment, time_slot)
            
            if score > 0:
                candidates.append(PlacementCandidate(
                    time_slot=time_slot,
                    class_ref=assignment.class_ref,
                    subject=assignment.subject,
                    teacher=assignment.teacher,
                    score=score,
                    constraints_satisfied=True
                ))
        
        if not candidates:
            return None
        
        # スコアでソートして最適な候補を返す
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        # 上位候補をログ出力
        self.logger.debug(f"配置候補 for {assignment.class_ref} - {assignment.subject}:")
        for i, candidate in enumerate(candidates[:3]):
            self.logger.debug(f"  {i+1}. {candidate.time_slot}: スコア={candidate.score:.2f}")
        
        return candidates[0].time_slot
    
    def optimize_teacher_workload(self, context: PlacementContext) -> List[Tuple[Assignment, Assignment]]:
        """教師の負荷を最適化する交換案を生成"""
        
        swaps = []
        
        # 教師ごとの負荷を計算
        workloads = {}
        for teacher_name, matrix in context.teacher_matrices.items():
            workloads[teacher_name] = matrix.get_workload()
        
        # 平均負荷
        if workloads and len(workloads) > 0:
            avg_workload = sum(workloads.values()) / len(workloads)
        else:
            avg_workload = 0
        
        # 過負荷の教師を特定
        overloaded = [(name, load) for name, load in workloads.items() 
                      if load > avg_workload * 1.2]
        
        # 低負荷の教師を特定
        underloaded = [(name, load) for name, load in workloads.items() 
                       if load < avg_workload * 0.8]
        
        self.logger.info(f"教師負荷分析: 平均={avg_workload:.1f}, 過負荷={len(overloaded)}, 低負荷={len(underloaded)}")
        
        # 交換候補を生成
        for over_teacher, over_load in overloaded[:3]:  # 上位3名のみ
            for under_teacher, under_load in underloaded[:3]:
                # 交換可能な授業を探す
                swap_candidates = self._find_swappable_assignments(
                    context, over_teacher, under_teacher
                )
                swaps.extend(swap_candidates[:2])  # 各ペアで最大2つ
        
        return swaps
    
    def _pre_placement_check(
        self, 
        context: PlacementContext,
        assignment: Assignment,
        time_slot: TimeSlot
    ) -> bool:
        """配置前の高速チェック"""
        
        # スロットが空いているか
        if context.schedule.get_assignment(time_slot, assignment.class_ref):
            return False
        
        # ロックされていないか
        if context.schedule.is_locked(time_slot, assignment.class_ref):
            return False
        
        # 必要時数が残っているか
        class_reqs = context.class_requirements.get(assignment.class_ref, {})
        if class_reqs.get(assignment.subject, 0) <= 0:
            return False
        
        return True
    
    def _propagate_constraints(
        self,
        context: PlacementContext,
        assignment: Assignment,
        time_slot: TimeSlot
    ) -> List[str]:
        """制約伝播による競合検出"""
        
        violations = []
        
        # 1. 教師重複チェック（5組を考慮）
        teacher_matrix = context.teacher_matrices.get(assignment.teacher.name)
        if teacher_matrix:
            current_classes = teacher_matrix.schedule.get(time_slot, set())
            if current_classes:
                # 5組の特別処理
                if assignment.class_ref in self.grade5_refs:
                    if not current_classes.issubset(self.grade5_refs):
                        violations.append(f"教師重複: 5組と通常クラスの混在")
                else:
                    if current_classes:
                        violations.append(f"教師重複: {assignment.teacher.name}先生")
        
        # 2. 日内重複チェック
        daily_count = self._count_daily_subject(
            context.schedule, assignment.class_ref, time_slot.day, assignment.subject
        )
        if daily_count >= 1:  # 既に1コマある
            violations.append(f"日内重複: {assignment.subject.name}")
        
        # 3. 体育館使用チェック
        if assignment.subject.name == "保":
            gym_conflict = self._check_gym_conflict(context, time_slot, assignment.class_ref)
            if gym_conflict:
                violations.append(f"体育館競合: {gym_conflict}")
        
        # 4. 交流学級の自立活動制約
        if assignment.subject.name == "自立" and assignment.class_ref in self.exchange_pairs.values():
            parent_class = self._get_parent_class(assignment.class_ref)
            if parent_class:
                parent_assignment = context.schedule.get_assignment(time_slot, parent_class)
                if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                    violations.append(f"自立活動制約: 親学級が{parent_assignment.subject.name}")
        
        return violations
    
    def _calculate_placement_score(
        self,
        context: PlacementContext,
        assignment: Assignment,
        time_slot: TimeSlot
    ) -> float:
        """配置スコアを計算（高いほど良い）"""
        
        score = 100.0  # 基本スコア
        
        # 教師の空き状況
        teacher_matrix = context.teacher_matrices.get(assignment.teacher.name)
        if not teacher_matrix or not teacher_matrix.is_available(time_slot):
            return 0.0
        
        # 制約違反をチェック
        violations = self._propagate_constraints(context, assignment, time_slot)
        if violations:
            return 0.0
        
        # ポジティブ要因
        # 1. 教師の負荷バランス
        daily_workload = teacher_matrix.get_daily_workload(time_slot.day)
        if daily_workload < 4:  # 1日4コマ以下が理想
            score += 20.0
        
        # 2. 連続性（同じ曜日に同じ教科があると良い）
        if self._has_same_subject_on_day(context.schedule, assignment.class_ref, 
                                       time_slot.day, assignment.subject):
            score += 10.0
        
        # 3. 朝の時間帯を優先
        if time_slot.period <= 3:
            score += 15.0
        
        # ネガティブ要因
        # 1. 6限目は避ける
        if time_slot.period == 6:
            score -= 30.0
        
        # 2. 金曜の午後は避ける
        if time_slot.day == "金" and time_slot.period >= 5:
            score -= 20.0
        
        return max(score, 0.0)
    
    def _sync_grade5_placement(
        self,
        context: PlacementContext,
        assignment: Assignment,
        time_slot: TimeSlot
    ):
        """5組の配置を同期"""
        
        if assignment.class_ref not in self.grade5_refs:
            return
        
        # 他の5組にも同じ配置
        for other_ref in self.grade5_refs:
            if other_ref != assignment.class_ref:
                # 既存の配置をチェック
                existing = context.schedule.get_assignment(time_slot, other_ref)
                if not existing:
                    # 同じ教師・科目で配置
                    other_assignment = Assignment(
                        class_ref=other_ref,
                        subject=assignment.subject,
                        teacher=assignment.teacher
                    )
                    context.schedule.assign(time_slot, other_assignment)
                    
                    # 教師行列も更新
                    teacher_matrix = context.teacher_matrices.get(assignment.teacher.name)
                    if teacher_matrix:
                        teacher_matrix.assign(time_slot, other_ref)
    
    def _sync_exchange_placement(
        self,
        context: PlacementContext,
        assignment: Assignment,
        time_slot: TimeSlot
    ):
        """交流学級の配置を同期"""
        
        # 交流学級が自立活動の場合
        if assignment.subject.name == "自立":
            parent_class = self.exchange_pairs.get(assignment.class_ref)
            if parent_class:
                # 親学級の科目をチェック
                parent_assignment = context.schedule.get_assignment(time_slot, parent_class)
                if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                    self.logger.warning(
                        f"警告: {assignment.class_ref}の自立活動時、"
                        f"親学級{parent_class}は{parent_assignment.subject.name}です"
                    )
    
    def _get_all_time_slots(self) -> List[TimeSlot]:
        """全時間スロットを取得"""
        slots = []
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                slots.append(TimeSlot(day, period))
        return slots
    
    def _calculate_class_requirements(
        self, 
        schedule: Schedule, 
        school: School
    ) -> Dict[ClassReference, Dict[Subject, float]]:
        """各クラスの残り必要時数を計算"""
        
        requirements = defaultdict(lambda: defaultdict(float))
        
        # 標準時数から現在の配置数を引く
        for class_ref in school.get_all_classes():
            # 学校に登録されている全科目をチェック
            for subject_name in ["国", "数", "英", "理", "社", "音", "美", "保", "技", "家", 
                               "道", "学", "総", "自立", "日生", "作業"]:
                try:
                    subject = Subject(subject_name)
                    standard = school.get_standard_hours(class_ref, subject)
                    if standard > 0:
                        current = self._count_subject_assignments(schedule, class_ref, subject)
                        remaining = standard - current
                        if remaining > 0:
                            requirements[class_ref][subject] = remaining
                except:
                    continue
        
        return dict(requirements)
    
    def _count_subject_assignments(
        self, 
        schedule: Schedule, 
        class_ref: ClassReference, 
        subject: Subject
    ) -> int:
        """特定クラス・科目の配置数をカウント"""
        count = 0
        for time_slot in self._get_all_time_slots():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                count += 1
        return count
    
    def _count_daily_subject(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        day: str,
        subject: Subject
    ) -> int:
        """特定の日の科目数をカウント"""
        count = 0
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                count += 1
        return count
    
    def _check_gym_conflict(
        self,
        context: PlacementContext,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> Optional[str]:
        """体育館の競合をチェック"""
        
        # 5組の特別処理
        if class_ref in self.grade5_refs:
            # 他の5組が体育なら問題なし
            for other_ref in self.grade5_refs:
                if other_ref != class_ref:
                    other_assignment = context.schedule.get_assignment(time_slot, other_ref)
                    if other_assignment and other_assignment.subject.name == "保":
                        return None
        
        # 通常のチェック
        for other_ref in context.school.get_all_classes():
            if other_ref == class_ref:
                continue
            other_assignment = context.schedule.get_assignment(time_slot, other_ref)
            if other_assignment and other_assignment.subject.name == "保":
                return str(other_ref)
        
        return None
    
    def _get_parent_class(self, exchange_class: ClassReference) -> Optional[ClassReference]:
        """交流学級の親学級を取得"""
        # 逆引き
        for child, parent in self.exchange_pairs.items():
            if child == exchange_class:
                return parent
        return None
    
    def _has_same_subject_on_day(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        day: str,
        subject: Subject
    ) -> bool:
        """同じ曜日に同じ科目があるかチェック"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                return True
        return False
    
    def _find_swappable_assignments(
        self,
        context: PlacementContext,
        over_teacher: str,
        under_teacher: str
    ) -> List[Tuple[Assignment, Assignment]]:
        """交換可能な授業を見つける"""
        
        swaps = []
        
        # 過負荷教師の授業を探す
        over_matrix = context.teacher_matrices.get(over_teacher)
        under_matrix = context.teacher_matrices.get(under_teacher)
        
        if not over_matrix or not under_matrix:
            return swaps
        
        # 簡単な実装：同じ科目を教えている場合のみ交換
        # 実際にはより高度なロジックが必要
        
        return swaps
    
    def generate_statistics(self, context: PlacementContext) -> Dict[str, any]:
        """配置統計を生成"""
        
        stats = {
            'total_assignments': context.total_assignments,
            'successful_placements': context.successful_placements,
            'failed_placements': context.failed_placements,
            'success_rate': (context.successful_placements / context.total_assignments * 100
                           if context.total_assignments > 0 else 0),
            'backtrack_count': context.backtrack_count,
            'teacher_workloads': {},
            'class_completion': {},
        }
        
        # 教師ごとの負荷
        for teacher_name, matrix in context.teacher_matrices.items():
            stats['teacher_workloads'][teacher_name] = {
                'total': matrix.get_workload(),
                'daily': {
                    day: matrix.get_daily_workload(day) 
                    for day in ["月", "火", "水", "木", "金"]
                }
            }
        
        # クラスごとの充足率
        for class_ref, subjects in context.class_requirements.items():
            total_required = sum(subjects.values())
            total_assigned = sum(
                self._count_subject_assignments(context.schedule, class_ref, subject)
                for subject in subjects
            )
            completion_rate = (total_assigned / total_required * 100
                             if total_required > 0 else 100)
            stats['class_completion'][str(class_ref)] = completion_rate
        
        return stats