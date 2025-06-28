"""教師の好みを考慮した配置モジュール

教師の満足度を最大化するように授業を配置します。
"""
import logging
from typing import Dict, List, Optional, Any

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School, Subject
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.assignment import Assignment
from .....domain.value_objects.time_slot import ClassReference
from ..configs.teacher_optimization_config import TeacherOptimizationConfig


class TeacherPreferencePlacement:
    """教師の好みを考慮した配置クラス"""
    
    def __init__(
        self,
        teacher_config: TeacherOptimizationConfig,
        preference_learning_system: Optional[object],
        constraint_validator: object,
        flexible_hours_system: object,
        fixed_subjects: List[str],
        grade5_classes: List[ClassReference],
        exchange_pairs: Dict[ClassReference, ClassReference]
    ):
        self.logger = logging.getLogger(__name__)
        self.teacher_config = teacher_config
        self.preference_learning_system = preference_learning_system
        self.constraint_validator = constraint_validator
        self.flexible_hours_system = flexible_hours_system
        self.fixed_subjects = fixed_subjects
        self.grade5_classes = grade5_classes
        self.exchange_pairs = exchange_pairs
    
    def place_grade5_with_teacher_preference(
        self,
        schedule: Schedule,
        school: School,
        flexible_plans: Dict,
        teacher_context: Optional[Dict],
        calculate_grade5_needs_func: callable
    ):
        """教師の好みを考慮した5組配置"""
        # 5組の担任（金子み先生）の好みを取得
        if self.preference_learning_system:
            teacher_name = "金子み"
            
            # 各時間帯のスコアを計算
            placement_scores = {}
            days = ["月", "火", "水", "木", "金"]
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 既に固定科目がある場合はスキップ
                    existing = schedule.get_assignment(time_slot, self.grade5_classes[0])
                    if existing and existing.subject.name in self.fixed_subjects:
                        continue
                    
                    # 教師の好みスコアを計算
                    score = 0.0
                    for class_ref in self.grade5_classes:
                        class_score = self.preference_learning_system.calculate_preference_score(
                            teacher_name, time_slot, class_ref,
                            {'is_grade5': True, 'simultaneous_classes': 3}
                        )
                        score += class_score
                    
                    placement_scores[(day, period)] = score / 3  # 平均スコア
        
        # スコアの高い時間帯を優先して配置
        if self.teacher_config.enable_teacher_preference and placement_scores:
            sorted_slots = sorted(placement_scores.items(), key=lambda x: x[1], reverse=True)
            
            # 必要な科目を優先度順に配置
            grade5_needs = calculate_grade5_needs_func(flexible_plans)
            for (day, period), score in sorted_slots[:10]:  # 上位10スロット
                time_slot = TimeSlot(day, period)
                
                # 最も必要な科目を選択
                best_subject = None
                best_priority = -1
                
                for subject_name, needs in grade5_needs.items():
                    if needs['ideal'] > 0 and needs['priority'] > best_priority:
                        # この科目が配置可能か確認
                        if self.can_place_grade5_subject(schedule, school, time_slot, subject_name):
                            best_subject = subject_name
                            best_priority = needs['priority']
                
                if best_subject:
                    # 5組に同期配置
                    self.sync_place_grade5(schedule, school, time_slot, best_subject)
                    grade5_needs[best_subject]['ideal'] -= 1
    
    def place_exchange_jiritsu_with_teacher_preference(
        self,
        schedule: Schedule,
        school: School,
        flexible_plans: Dict,
        teacher_context: Optional[Dict]
    ):
        """教師の好みを考慮した交流学級配置"""
        if not self.teacher_config.enable_teacher_preference:
            return
        
        # 各交流学級の自立活動配置
        for exchange_class, parent_class in self.exchange_pairs.items():
            teacher = school.get_homeroom_teacher(exchange_class)
            if not teacher:
                continue
            
            # 教師の好みスコアを計算
            placement_candidates = []
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 親学級が数学か英語か確認
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        # 教師の好みスコアを計算
                        score = self.preference_learning_system.calculate_preference_score(
                            teacher.name, time_slot, exchange_class,
                            {'is_jiritsu': True, 'parent_subject': parent_assignment.subject.name}
                        ) if self.preference_learning_system else 0.5
                        
                        placement_candidates.append((time_slot, score))
            
            # スコアの高い順に配置を試みる
            placement_candidates.sort(key=lambda x: x[1], reverse=True)
            
            needed_hours = flexible_plans.get(exchange_class, {}).get('requirements', {}).get('自立', {}).get('ideal_hours', 0)
            placed = 0
            
            for time_slot, score in placement_candidates:
                if placed >= needed_hours:
                    break
                
                # 配置を試みる
                existing = schedule.get_assignment(time_slot, exchange_class)
                if not existing:
                    assignment = Assignment(
                        exchange_class,
                        Subject("自立"),
                        teacher
                    )
                    try:
                        schedule.assign(time_slot, assignment)
                        placed += 1
                        self.logger.info(
                            f"{exchange_class}の自立活動を{time_slot}に配置"
                            f"（教師満足度スコア: {score:.2f}）"
                        )
                    except:
                        pass
    
    def guarantee_hours_with_teacher_preference(
        self,
        schedule: Schedule,
        school: School,
        followup_data: Optional[Dict[str, Any]],
        teacher_context: Optional[Dict],
        get_placement_context_func: callable
    ) -> Dict:
        """教師の好みを考慮した標準時数保証"""
        # まず通常の標準時数保証を実行
        flexible_results = self.flexible_hours_system.guarantee_flexible_hours(
            schedule, school, followup_data, self.constraint_validator
        )
        
        if not self.teacher_config.enable_teacher_preference:
            return flexible_results
        
        # 教師の好みを考慮した配置の最適化
        optimization_count = 0
        
        for class_ref in school.get_all_classes():
            # 5組は別処理
            if class_ref in self.grade5_classes:
                continue
            
            # クラスの不足科目を確認
            class_data = flexible_results.get('by_class', {}).get(
                f"{class_ref.grade}-{class_ref.class_number}", {}
            )
            
            for subject_name, allocation in class_data.get('subjects', {}).items():
                if allocation['satisfaction'] == "不足":
                    subject = Subject(subject_name)
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    
                    if teacher and self.preference_learning_system:
                        # 空きスロットを教師の好み順にソート
                        empty_slots = self.get_empty_slots(schedule, class_ref)
                        scored_slots = []
                        
                        for time_slot in empty_slots:
                            score = self.preference_learning_system.calculate_preference_score(
                                teacher.name, time_slot, class_ref,
                                get_placement_context_func(schedule, teacher.name, time_slot.day)
                            )
                            scored_slots.append((time_slot, score))
                        
                        # スコアの高い順にソート
                        scored_slots.sort(key=lambda x: x[1], reverse=True)
                        
                        # 不足分を配置
                        needed = allocation['standard'] - allocation['assigned']
                        placed = 0
                        
                        for time_slot, score in scored_slots:
                            if placed >= needed:
                                break
                            
                            # 教師の満足度が閾値以上の場合のみ配置
                            if score >= self.teacher_config.min_teacher_satisfaction:
                                assignment = Assignment(class_ref, subject, teacher)
                                if self.try_assign_with_constraints(schedule, time_slot, assignment):
                                    placed += 1
                                    optimization_count += 1
                                    self.logger.debug(
                                        f"{teacher.name}の{subject_name}を"
                                        f"{time_slot}に配置（満足度: {score:.2f}）"
                                    )
        
        if optimization_count > 0:
            self.logger.info(f"教師の好みを考慮して{optimization_count}件の配置を最適化")
        
        return flexible_results
    
    def can_place_grade5_subject(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        subject_name: str
    ) -> bool:
        """5組に特定の科目を配置可能か確認"""
        # 全ての5組で配置可能か確認
        for class_ref in self.grade5_classes:
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing:
                return False
            
            # 制約チェック
            subject = Subject(subject_name)
            teacher = school.get_assigned_teacher(subject, class_ref)
            if not teacher:
                return False
            
            assignment = Assignment(class_ref, subject, teacher)
            violations = self.constraint_validator.validate_single_assignment(
                schedule, time_slot, assignment, school
            )
            if violations:
                return False
        
        return True
    
    def sync_place_grade5(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        subject_name: str
    ):
        """5組に同期配置"""
        subject = Subject(subject_name)
        
        for class_ref in self.grade5_classes:
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher:
                assignment = Assignment(class_ref, subject, teacher)
                try:
                    schedule.assign(time_slot, assignment)
                except:
                    pass
    
    def get_empty_slots(
        self,
        schedule: Schedule,
        class_ref: ClassReference
    ) -> List[TimeSlot]:
        """クラスの空きスロットを取得"""
        empty_slots = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                if not schedule.get_assignment(time_slot, class_ref):
                    empty_slots.append(time_slot)
        
        return empty_slots
    
    def try_assign_with_constraints(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """制約をチェックしながら配置を試みる"""
        # 制約チェック
        violations = self.constraint_validator.validate_single_assignment(
            schedule, time_slot, assignment, schedule.school if hasattr(schedule, 'school') else None
        )
        
        if not violations:
            try:
                schedule.assign(time_slot, assignment)
                return True
            except:
                pass
        
        return False