"""技術・家庭科（技家）実現可能性制約

技家の物理的な実現可能性を保証する制約：
1. 同一時間の技家授業数に応じた教師配分
2. 1人の教師が担当できる最大クラス数の制限
3. 技術教師と家庭科教師の適切な配分
4. テスト期間中は制約を緩和（ペーパーテストは巡回監督可能）
"""
import logging
from typing import Dict, List, Set, Tuple, Optional
from .base import Constraint, ConstraintPriority, ConstraintType, ConstraintResult
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment, ConstraintViolation
from ..services.core.techome_handler import TechHomeHandler
from ..services.core.test_period_checker import TestPeriodChecker


class TechHomeFeasibilityConstraint(Constraint):
    """技家の実現可能性を保証する制約"""
    
    # 1人の教師が同時に担当できる最大クラス数
    MAX_CLASSES_PER_TEACHER = 3
    
    # 同一時間に技家を実施する場合の必要教師数
    REQUIRED_TEACHERS = {
        1: 1,  # 1クラス → 1人
        2: 1,  # 2クラス → 1人（巡回可能）
        3: 1,  # 3クラス → 1人（限界）
        4: 2,  # 4クラス → 2人必要
        5: 2,  # 5クラス → 2人必要
        6: 2,  # 6クラス → 2人必要
        7: 3,  # 7クラス → 3人必要
    }
    
    def __init__(self, test_period_checker: TestPeriodChecker = None):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="技家実現可能性制約",
            description="技家の物理的な実現可能性を保証"
        )
        self.logger = logging.getLogger(__name__)
        self.handler = TechHomeHandler()
        self.test_period_checker = test_period_checker or TestPeriodChecker()
    
    def check_before_assignment(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """配置前チェック: 技家の配置が可能かどうか判定"""
        # 技家以外の科目は常に許可
        if assignment.subject.name != "技家":
            return True
            
        return self.can_satisfy(
            schedule, school, time_slot, 
            assignment.class_ref, assignment.subject, assignment.teacher
        )
    
    def check(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: Optional[TimeSlot] = None,
        assignment: Optional[Assignment] = None
    ) -> List[ConstraintViolation]:
        """技家配置の実現可能性をチェック"""
        violations = []
        
        if time_slot and assignment:
            # 特定の配置をチェック
            if assignment.subject.name == "技家":
                violations.extend(
                    self._check_single_assignment(schedule, school, time_slot, assignment)
                )
        else:
            # 全体をチェック
            violations.extend(self._check_all_techome(schedule, school))
        
        return violations
    
    def _check_single_assignment(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> List[ConstraintViolation]:
        """単一の技家配置をチェック"""
        violations = []
        
        # テスト期間中は制約を緩和（ペーパーテストは巡回監督可能）
        if self.test_period_checker.is_test_period(time_slot):
            self.logger.debug(f"{time_slot}はテスト期間のため、技家の制約を緩和")
            return violations
        
        # その時間の技家配置を収集
        techome_classes = []
        teacher_assignments: Dict[Teacher, List[ClassReference]] = {}
        
        for cls in school.get_all_classes():
            existing = schedule.get_assignment(time_slot, cls)
            if existing and existing.subject.name == "技家":
                techome_classes.append(cls)
                if existing.teacher:
                    if existing.teacher not in teacher_assignments:
                        teacher_assignments[existing.teacher] = []
                    teacher_assignments[existing.teacher].append(cls)
        
        # 新しい配置も含めて考慮
        if assignment.class_ref not in techome_classes:
            techome_classes.append(assignment.class_ref)
        if assignment.teacher:
            if assignment.teacher not in teacher_assignments:
                teacher_assignments[assignment.teacher] = []
            teacher_assignments[assignment.teacher].append(assignment.class_ref)
        
        # 必要教師数をチェック
        total_classes = len(techome_classes)
        required_teachers = self.REQUIRED_TEACHERS.get(total_classes, 3)
        actual_teachers = len(teacher_assignments)
        
        if actual_teachers < required_teachers:
            violations.append(ConstraintViolation(
                description=(
                    f"技家の教師不足: {time_slot}に{total_classes}クラスの技家があるが、"
                    f"教師は{actual_teachers}人のみ（最低{required_teachers}人必要）"
                ),
                time_slot=time_slot,
                assignment=assignment,
                severity="ERROR"
            ))
        
        # 各教師の担当クラス数をチェック
        for teacher, classes in teacher_assignments.items():
            if len(classes) > self.MAX_CLASSES_PER_TEACHER:
                violations.append(ConstraintViolation(
                    description=(
                        f"技家の過負荷: {teacher.name}先生が{time_slot}に"
                        f"{len(classes)}クラスを担当（最大{self.MAX_CLASSES_PER_TEACHER}クラス）"
                    ),
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="ERROR"
                ))
        
        return violations
    
    def _check_all_techome(
        self, 
        schedule: Schedule, 
        school: School
    ) -> List[ConstraintViolation]:
        """全ての技家配置をチェック"""
        violations = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間中は制約を緩和（ペーパーテストは巡回監督可能）
                if self.test_period_checker.is_test_period(time_slot):
                    self.logger.debug(f"{time_slot}はテスト期間のため、技家の制約を緩和")
                    continue
                
                # その時間の技家配置を収集
                techome_assignments = []
                teacher_counts: Dict[Teacher, int] = {}
                
                for cls in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, cls)
                    if assignment and assignment.subject.name == "技家":
                        techome_assignments.append(assignment)
                        if assignment.teacher:
                            teacher_counts[assignment.teacher] = \
                                teacher_counts.get(assignment.teacher, 0) + 1
                
                if not techome_assignments:
                    continue
                
                # 必要教師数をチェック
                total_classes = len(techome_assignments)
                required_teachers = self.REQUIRED_TEACHERS.get(total_classes, 3)
                actual_teachers = len(teacher_counts)
                
                if actual_teachers < required_teachers:
                    violations.append(ConstraintViolation(
                        description=(
                            f"技家の教師不足: {time_slot}に{total_classes}クラスの技家があるが、"
                            f"教師は{actual_teachers}人のみ（最低{required_teachers}人必要）"
                        ),
                        time_slot=time_slot,
                        assignment=techome_assignments[0],  # 代表として最初の配置を使用
                        severity="ERROR"
                    ))
                
                # 各教師の担当クラス数をチェック
                for teacher, count in teacher_counts.items():
                    if count > self.MAX_CLASSES_PER_TEACHER:
                        # 該当する配置を探す
                        for assignment in techome_assignments:
                            if assignment.teacher == teacher:
                                violations.append(ConstraintViolation(
                                    description=(
                                        f"技家の過負荷: {teacher.name}先生が{time_slot}に"
                                        f"{count}クラスを担当（最大{self.MAX_CLASSES_PER_TEACHER}クラス）"
                                    ),
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                ))
                                break
        
        return violations
    
    def can_satisfy(
        self, 
        schedule: Schedule, 
        school: School, 
        time_slot: TimeSlot,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Optional[Teacher] = None
    ) -> bool:
        """技家の配置が可能かどうか判定"""
        if subject.name != "技家":
            return True
        
        # テスト期間中は制約を緩和（ペーパーテストは巡回監督可能）
        if self.test_period_checker.is_test_period(time_slot):
            return True
        
        # 既存の技家配置を確認
        teacher_counts: Dict[Teacher, int] = {}
        total_techome = 0
        
        for cls in school.get_all_classes():
            if cls == class_ref:
                continue
            assignment = schedule.get_assignment(time_slot, cls)
            if assignment and assignment.subject.name == "技家":
                total_techome += 1
                if assignment.teacher:
                    teacher_counts[assignment.teacher] = \
                        teacher_counts.get(assignment.teacher, 0) + 1
        
        # 新しい配置を含めた場合
        total_techome += 1
        if teacher:
            teacher_counts[teacher] = teacher_counts.get(teacher, 0) + 1
        
        # 必要教師数をチェック
        required_teachers = self.REQUIRED_TEACHERS.get(total_techome, 3)
        if len(teacher_counts) < required_teachers and teacher:
            # 新しい教師が必要だが、提案された教師で足りるか
            if len(teacher_counts) < required_teachers:
                return False
        
        # 教師の過負荷をチェック
        if teacher and teacher_counts.get(teacher, 0) > self.MAX_CLASSES_PER_TEACHER:
            return False
        
        return True
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """全体の技家配置を検証
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            
        Returns:
            制約検証結果
        """
        violations = self._check_all_techome(schedule, school)
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations,
            message=f"技家実現可能性制約: {len(violations)}件の違反" if violations else "技家実現可能性制約: 違反なし"
        )