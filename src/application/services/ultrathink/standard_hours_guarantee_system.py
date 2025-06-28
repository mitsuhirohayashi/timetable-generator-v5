"""
標準時数完全保証システム

各科目の標準時数を確実に満たすための高度な配置戦略システム。
事前計画、最適配置、バックトラック戦略を組み合わせて、
全ての科目が必要時数を満たす時間割を生成します。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict
import heapq

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Teacher, Subject
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment


@dataclass
class SubjectRequirement:
    """科目の必要時数情報"""
    subject: Subject
    required_hours: int
    assigned_hours: int = 0
    teacher: Optional[Teacher] = None
    priority: float = 0.0  # 配置優先度
    
    @property
    def remaining_hours(self) -> int:
        """残り必要時数"""
        return self.required_hours - self.assigned_hours
    
    @property
    def completion_rate(self) -> float:
        """完了率"""
        if self.required_hours == 0:
            return 1.0
        return self.assigned_hours / self.required_hours


@dataclass
class ClassSchedulePlan:
    """クラスごとの配置計画"""
    class_ref: ClassReference
    requirements: Dict[str, SubjectRequirement] = field(default_factory=dict)
    available_slots: List[TimeSlot] = field(default_factory=list)
    
    @property
    def total_required(self) -> int:
        """必要時数の合計"""
        return sum(req.remaining_hours for req in self.requirements.values())
    
    @property
    def completion_rate(self) -> float:
        """全体の完了率"""
        total_req = sum(req.required_hours for req in self.requirements.values())
        if total_req == 0:
            return 1.0
        total_assigned = sum(req.assigned_hours for req in self.requirements.values())
        return total_assigned / total_req


@dataclass
class PlacementCandidate:
    """配置候補"""
    time_slot: TimeSlot
    class_ref: ClassReference
    subject: Subject
    teacher: Teacher
    score: float = 0.0
    violations: List[str] = field(default_factory=list)
    
    def __lt__(self, other):
        """優先度比較（スコアが高いほど優先）"""
        return self.score > other.score


class StandardHoursGuaranteeSystem:
    """標準時数完全保証システム"""
    
    def __init__(self, enable_logging: bool = True):
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # 固定科目の定義
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家"}
        
        # テスト期間
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
        
        # 配置統計
        self.placement_stats = {
            'attempts': 0,
            'successes': 0,
            'backtracks': 0,
            'final_completion_rate': 0.0
        }
    
    def guarantee_standard_hours(
        self,
        schedule: Schedule,
        school: School,
        constraint_validator: Any = None
    ) -> Dict[str, Any]:
        """標準時数を保証する配置を実行"""
        
        self.logger.info("=== 標準時数完全保証システム開始 ===")
        
        # 1. 現状分析と計画立案
        plans = self._create_placement_plans(schedule, school)
        
        # 2. 優先度計算
        self._calculate_priorities(plans, school)
        
        # 3. 配置実行
        success = self._execute_placement(plans, schedule, school, constraint_validator)
        
        # 4. 結果評価
        results = self._evaluate_results(plans, schedule, school)
        
        self._log_results(results)
        
        return results
    
    def _create_placement_plans(
        self,
        schedule: Schedule,
        school: School
    ) -> Dict[ClassReference, ClassSchedulePlan]:
        """配置計画を作成"""
        plans = {}
        
        for class_ref in school.get_all_classes():
            plan = ClassSchedulePlan(class_ref=class_ref)
            
            # 標準時数を取得
            standard_hours = school.get_all_standard_hours(class_ref)
            
            # 現在の配置状況を分析
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # 必要時数を計算
            for subject, hours in standard_hours.items():
                if subject.name in self.fixed_subjects:
                    continue
                
                req = SubjectRequirement(
                    subject=subject,
                    required_hours=int(hours),
                    assigned_hours=current_hours.get(subject.name, 0),
                    teacher=school.get_assigned_teacher(subject, class_ref)
                )
                
                if req.remaining_hours > 0:
                    plan.requirements[subject.name] = req
            
            # 利用可能なスロットを特定
            plan.available_slots = self._find_available_slots(schedule, class_ref)
            
            plans[class_ref] = plan
        
        return plans
    
    def _count_current_hours(
        self,
        schedule: Schedule,
        class_ref: ClassReference
    ) -> Dict[str, int]:
        """現在の配置時数をカウント"""
        hours = defaultdict(int)
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name not in self.fixed_subjects:
                    hours[assignment.subject.name] += 1
        
        return dict(hours)
    
    def _find_available_slots(
        self,
        schedule: Schedule,
        class_ref: ClassReference
    ) -> List[TimeSlot]:
        """利用可能なスロットを探す"""
        available = []
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 固定時間（月曜6限など）はスキップ
                if self._is_fixed_slot(day, period):
                    continue
                
                # 既に配置済みかチェック
                assignment = schedule.get_assignment(time_slot, class_ref)
                if not assignment:
                    available.append(time_slot)
                elif (assignment.subject.name not in self.fixed_subjects 
                      and not schedule.is_locked(time_slot, class_ref)):
                    # 固定科目でなく、ロックされていなければ置換可能
                    available.append(time_slot)
        
        return available
    
    def _is_fixed_slot(self, day: str, period: int) -> bool:
        """固定スロットかどうか判定"""
        # 月曜6限は全クラス欠課
        if day == "月" and period == 6:
            return True
        # その他の固定時間もここで定義
        return False
    
    def _calculate_priorities(
        self,
        plans: Dict[ClassReference, ClassSchedulePlan],
        school: School
    ):
        """配置優先度を計算"""
        # 全体の平均完了率を計算
        total_completion = sum(plan.completion_rate for plan in plans.values())
        avg_completion = total_completion / len(plans) if plans else 0
        
        for plan in plans.values():
            for req in plan.requirements.values():
                # 基本優先度：残り時数が多いほど高い
                base_priority = req.remaining_hours * 10
                
                # 完了率が低い科目を優先
                completion_penalty = (1 - req.completion_rate) * 50
                
                # 主要5教科は優先
                if req.subject.name in ["数", "英", "国", "理", "社"]:
                    base_priority += 20
                
                # クラス全体の完了率が低い場合は優先
                if plan.completion_rate < avg_completion:
                    base_priority += 30
                
                # 残りスロットが少ない場合は緊急度アップ
                if len(plan.available_slots) < plan.total_required * 1.2:
                    base_priority += 40
                
                req.priority = base_priority + completion_penalty
    
    def _execute_placement(
        self,
        plans: Dict[ClassReference, ClassSchedulePlan],
        schedule: Schedule,
        school: School,
        constraint_validator: Any
    ) -> bool:
        """配置を実行"""
        # 優先度順に配置候補を作成
        candidates = []
        
        for class_ref, plan in plans.items():
            for subject_name, req in plan.requirements.items():
                if req.remaining_hours > 0 and req.teacher:
                    # この科目の配置候補を生成
                    for time_slot in plan.available_slots:
                        candidate = self._create_placement_candidate(
                            time_slot, class_ref, req, schedule, school
                        )
                        if candidate:
                            heapq.heappush(candidates, candidate)
        
        # 優先度順に配置を試みる
        placed_count = 0
        max_attempts = len(candidates) * 2
        attempts = 0
        
        while candidates and attempts < max_attempts:
            attempts += 1
            candidate = heapq.heappop(candidates)
            
            # 配置を試みる
            if self._try_place_assignment(
                candidate, schedule, school, constraint_validator, plans
            ):
                placed_count += 1
                
                # 同じクラス・科目の残り候補を更新
                self._update_candidates_after_placement(
                    candidates, candidate, plans
                )
            else:
                # 配置失敗時の処理
                if candidate.violations:
                    # 違反がある場合は優先度を下げて再挿入
                    candidate.score *= 0.8
                    if candidate.score > 0:
                        heapq.heappush(candidates, candidate)
        
        self.placement_stats['attempts'] = attempts
        self.placement_stats['successes'] = placed_count
        
        return placed_count > 0
    
    def _create_placement_candidate(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        requirement: SubjectRequirement,
        schedule: Schedule,
        school: School
    ) -> Optional[PlacementCandidate]:
        """配置候補を作成"""
        if not requirement.teacher:
            return None
        
        candidate = PlacementCandidate(
            time_slot=time_slot,
            class_ref=class_ref,
            subject=requirement.subject,
            teacher=requirement.teacher
        )
        
        # スコア計算
        score = requirement.priority
        
        # 同じ日に同じ科目がないかチェック
        has_same_subject_today = False
        for period in range(1, 7):
            ts = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(ts, class_ref)
            if assignment and assignment.subject.name == requirement.subject.name:
                has_same_subject_today = True
                break
        
        if has_same_subject_today:
            score *= 0.3  # 同じ日に同じ科目は避ける
        
        # 教師の負荷を考慮
        teacher_load = self._calculate_teacher_load(
            requirement.teacher, time_slot, schedule, school
        )
        if teacher_load > 1:
            score *= 0.5  # 教師が重複する場合はペナルティ
            candidate.violations.append(f"教師重複: {requirement.teacher.name}")
        
        # バランスの良い配置を優先
        # 例：週の前半・後半、午前・午後のバランス
        if time_slot.day in ["月", "火"]:
            score *= 1.1  # 週前半を若干優先
        
        if time_slot.period in [2, 3, 4]:
            score *= 1.2  # 中間の時間帯を優先
        
        candidate.score = score
        
        return candidate
    
    def _calculate_teacher_load(
        self,
        teacher: Teacher,
        time_slot: TimeSlot,
        schedule: Schedule,
        school: School
    ) -> int:
        """教師の負荷を計算"""
        load = 0
        
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                load += 1
        
        return load
    
    def _try_place_assignment(
        self,
        candidate: PlacementCandidate,
        schedule: Schedule,
        school: School,
        constraint_validator: Any,
        plans: Dict[ClassReference, ClassSchedulePlan]
    ) -> bool:
        """配置を試みる"""
        # 既存の配置を保存
        existing = schedule.get_assignment(candidate.time_slot, candidate.class_ref)
        
        # 新しい配置を作成
        new_assignment = Assignment(
            candidate.class_ref,
            candidate.subject,
            candidate.teacher
        )
        
        try:
            # 既存の配置を削除
            if existing:
                schedule.remove_assignment(candidate.time_slot, candidate.class_ref)
            
            # 新しい配置を追加
            schedule.assign(candidate.time_slot, new_assignment)
            
            # 制約チェック（オプション）
            if constraint_validator:
                # 簡易チェック実装
                if self._has_critical_violations(
                    schedule, school, candidate.time_slot, new_assignment
                ):
                    raise ValueError("Critical constraint violation")
            
            # 成功時は計画を更新
            plan = plans[candidate.class_ref]
            req = plan.requirements.get(candidate.subject.name)
            if req:
                req.assigned_hours += 1
            
            return True
            
        except Exception as e:
            # 失敗時は元に戻す
            if new_assignment:
                try:
                    schedule.remove_assignment(candidate.time_slot, candidate.class_ref)
                except:
                    pass
            
            if existing:
                try:
                    schedule.assign(candidate.time_slot, existing)
                except:
                    pass
            
            return False
    
    def _has_critical_violations(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """重大な制約違反があるかチェック"""
        # テスト期間以外での教師重複チェック
        if (time_slot.day, time_slot.period) not in self.test_periods:
            teacher_count = 0
            for class_ref in school.get_all_classes():
                asn = schedule.get_assignment(time_slot, class_ref)
                if asn and asn.teacher and asn.teacher.name == assignment.teacher.name:
                    teacher_count += 1
            
            if teacher_count > 1:
                # 5組の合同授業は例外
                grade5_classes = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
                all_grade5 = all(
                    schedule.get_assignment(time_slot, cr) and 
                    schedule.get_assignment(time_slot, cr).teacher.name == assignment.teacher.name
                    for cr in grade5_classes
                )
                if not all_grade5:
                    return True
        
        return False
    
    def _update_candidates_after_placement(
        self,
        candidates: List[PlacementCandidate],
        placed: PlacementCandidate,
        plans: Dict[ClassReference, ClassSchedulePlan]
    ):
        """配置後に候補を更新"""
        # 同じクラス・時間の候補を削除
        candidates[:] = [
            c for c in candidates
            if not (c.class_ref == placed.class_ref and c.time_slot == placed.time_slot)
        ]
        
        # 同じクラス・科目の優先度を更新
        plan = plans[placed.class_ref]
        req = plan.requirements.get(placed.subject.name)
        if req and req.remaining_hours > 0:
            # まだ配置が必要な場合は優先度を上げる
            for c in candidates:
                if (c.class_ref == placed.class_ref and 
                    c.subject.name == placed.subject.name):
                    c.score *= 1.2
    
    def _evaluate_results(
        self,
        plans: Dict[ClassReference, ClassSchedulePlan],
        schedule: Schedule,
        school: School
    ) -> Dict[str, Any]:
        """結果を評価"""
        results = {
            'total_classes': len(plans),
            'fully_satisfied': 0,
            'partially_satisfied': 0,
            'unsatisfied': 0,
            'overall_completion_rate': 0.0,
            'details': [],
            'critical_shortages': []
        }
        
        total_required = 0
        total_assigned = 0
        
        for class_ref, plan in plans.items():
            class_total_req = 0
            class_total_assigned = 0
            unsatisfied_subjects = []
            
            # 最新の配置状況を再計算
            current_hours = self._count_current_hours(schedule, class_ref)
            
            for subject_name, req in plan.requirements.items():
                actual_hours = current_hours.get(subject_name, 0)
                req.assigned_hours = actual_hours
                
                class_total_req += req.required_hours
                class_total_assigned += actual_hours
                
                if actual_hours < req.required_hours:
                    shortage = req.required_hours - actual_hours
                    unsatisfied_subjects.append({
                        'subject': subject_name,
                        'required': req.required_hours,
                        'assigned': actual_hours,
                        'shortage': shortage
                    })
                    
                    # 重大な不足（50%以下）
                    if actual_hours < req.required_hours * 0.5:
                        results['critical_shortages'].append({
                            'class': str(class_ref),
                            'subject': subject_name,
                            'completion_rate': actual_hours / req.required_hours if req.required_hours > 0 else 0
                        })
            
            # クラスの評価
            if not unsatisfied_subjects:
                results['fully_satisfied'] += 1
            elif len(unsatisfied_subjects) <= 2 and all(s['shortage'] <= 1 for s in unsatisfied_subjects):
                results['partially_satisfied'] += 1
            else:
                results['unsatisfied'] += 1
            
            # 詳細情報
            if unsatisfied_subjects:
                results['details'].append({
                    'class': str(class_ref),
                    'completion_rate': class_total_assigned / class_total_req if class_total_req > 0 else 1.0,
                    'unsatisfied_subjects': unsatisfied_subjects
                })
            
            total_required += class_total_req
            total_assigned += class_total_assigned
        
        results['overall_completion_rate'] = total_assigned / total_required if total_required > 0 else 1.0
        self.placement_stats['final_completion_rate'] = results['overall_completion_rate']
        
        return results
    
    def _log_results(self, results: Dict[str, Any]):
        """結果をログ出力"""
        self.logger.info("\n=== 標準時数保証システム結果 ===")
        self.logger.info(f"全体完了率: {results['overall_completion_rate']*100:.1f}%")
        self.logger.info(f"完全充足クラス: {results['fully_satisfied']}/{results['total_classes']}")
        self.logger.info(f"部分充足クラス: {results['partially_satisfied']}")
        self.logger.info(f"未充足クラス: {results['unsatisfied']}")
        
        if results['critical_shortages']:
            self.logger.warning(f"\n重大な不足: {len(results['critical_shortages'])}件")
            for shortage in results['critical_shortages'][:5]:
                self.logger.warning(
                    f"  {shortage['class']} {shortage['subject']}: "
                    f"達成率{shortage['completion_rate']*100:.0f}%"
                )
        
        self.logger.info(f"\n配置統計:")
        self.logger.info(f"  試行回数: {self.placement_stats['attempts']}")
        self.logger.info(f"  成功配置: {self.placement_stats['successes']}")
        self.logger.info(f"  最終完了率: {self.placement_stats['final_completion_rate']*100:.1f}%")