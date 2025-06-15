"""統合制約エンジン - すべての制約を一元管理"""
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class ConstraintPriority(Enum):
    """制約の優先度"""
    CRITICAL = auto()  # 絶対に違反してはいけない
    HIGH = auto()      # 非常に重要
    MEDIUM = auto()    # 重要
    LOW = auto()       # 望ましい
    

class ViolationType(Enum):
    """違反の種類"""
    TEACHER_CONFLICT = auto()
    GYM_USAGE = auto()
    JIRITSU_ACTIVITY = auto()
    EXCHANGE_CLASS_SYNC = auto()
    FIXED_PERIOD = auto()
    DAILY_DUPLICATE = auto()
    FORBIDDEN_PLACEMENT = auto()
    MEETING_CONFLICT = auto()
    

@dataclass
class Violation:
    """制約違反"""
    type: ViolationType
    priority: ConstraintPriority
    description: str
    location: Dict[str, any]  # time_slot, class_ref, etc.
    details: Dict[str, any] = field(default_factory=dict)
    fixable: bool = True
    suggested_fix: Optional[str] = None


@dataclass
class Assignment:
    """授業割り当て"""
    time_slot: 'TimeSlot'
    class_ref: 'ClassReference'
    subject: 'Subject'
    teacher: Optional['Teacher'] = None


class Constraint(ABC):
    """制約の基底クラス"""
    
    def __init__(self, priority: ConstraintPriority):
        self.priority = priority
    
    @abstractmethod
    def check(self, assignment: Assignment, timetable: 'Timetable') -> Optional[Violation]:
        """制約をチェック"""
        pass
    
    @abstractmethod
    def can_fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        """違反が修正可能かチェック"""
        pass
    
    @abstractmethod
    def fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        """違反を修正"""
        pass


class TeacherConflictConstraint(Constraint):
    """教員重複制約"""
    
    def __init__(self):
        super().__init__(ConstraintPriority.CRITICAL)
    
    def check(self, assignment: Assignment, timetable: 'Timetable') -> Optional[Violation]:
        if not assignment.teacher:
            return None
            
        # 同じ時間に同じ教員が他のクラスで授業していないかチェック
        for other_assignment in timetable.get_assignments_at(assignment.time_slot):
            if (other_assignment.teacher == assignment.teacher and 
                other_assignment.class_ref != assignment.class_ref):
                return Violation(
                    type=ViolationType.TEACHER_CONFLICT,
                    priority=self.priority,
                    description=f"{assignment.teacher.name}が同時刻に複数クラスで授業",
                    location={
                        'time_slot': assignment.time_slot,
                        'classes': [assignment.class_ref, other_assignment.class_ref]
                    },
                    details={'teacher': assignment.teacher.name}
                )
        return None
    
    def can_fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        # 教員の空き時間があれば修正可能
        return True
    
    def fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        # 実装省略
        return False


class GymUsageConstraint(Constraint):
    """体育館使用制約 - 同時に1クラスのみ"""
    
    def __init__(self):
        super().__init__(ConstraintPriority.HIGH)
    
    def check(self, assignment: Assignment, timetable: 'Timetable') -> Optional[Violation]:
        if assignment.subject.name != "保":
            return None
            
        # 同じ時間に体育をしている他のクラスを数える
        pe_classes = []
        for other_assignment in timetable.get_assignments_at(assignment.time_slot):
            if other_assignment.subject.name == "保":
                pe_classes.append(other_assignment.class_ref)
        
        if len(pe_classes) > 1:
            return Violation(
                type=ViolationType.GYM_USAGE,
                priority=self.priority,
                description=f"{len(pe_classes)}クラスが同時に体育",
                location={'time_slot': assignment.time_slot},
                details={'classes': pe_classes}
            )
        return None
    
    def can_fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        # 体育の移動先があれば修正可能
        return True
    
    def fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        # 実装省略
        return False


class JiritsuActivityConstraint(Constraint):
    """自立活動制約 - 5組の自立活動時、他クラスは数学または英語"""
    
    def __init__(self):
        super().__init__(ConstraintPriority.HIGH)
        self.grade5_classes = {
            (1, 5): [(1, 1), (1, 2), (1, 3), (1, 4)],
            (2, 5): [(2, 1), (2, 2), (2, 3), (2, 4)],
            (3, 5): [(3, 1), (3, 2), (3, 3), (3, 4)]
        }
    
    def check(self, assignment: Assignment, timetable: 'Timetable') -> Optional[Violation]:
        # 5組の自立活動かチェック
        if (assignment.class_ref.grade, assignment.class_ref.number) not in self.grade5_classes:
            return None
        if assignment.subject.name != "自立":
            return None
            
        # 同学年の他クラスをチェック
        violations = []
        grade = assignment.class_ref.grade
        other_classes = self.grade5_classes[(grade, 5)]
        
        for other_grade, other_num in other_classes:
            other_class = ClassReference(other_grade, other_num)
            other_assignment = timetable.get_assignment(assignment.time_slot, other_class)
            
            if other_assignment and other_assignment.subject.name not in ["数", "英"]:
                violations.append({
                    'class': other_class,
                    'subject': other_assignment.subject.name
                })
        
        if violations:
            return Violation(
                type=ViolationType.JIRITSU_ACTIVITY,
                priority=self.priority,
                description=f"{len(violations)}クラスが数学・英語以外",
                location={
                    'time_slot': assignment.time_slot,
                    'grade5_class': assignment.class_ref
                },
                details={'violations': violations}
            )
        return None
    
    def can_fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        # 数学または英語と交換可能なら修正可能
        return True
    
    def fix(self, violation: Violation, timetable: 'Timetable') -> bool:
        # 実装省略
        return False


class ConstraintEngine:
    """統合制約エンジン"""
    
    def __init__(self):
        self.constraints: List[Constraint] = []
        self._initialize_constraints()
    
    def _initialize_constraints(self):
        """標準制約を初期化"""
        self.constraints.extend([
            TeacherConflictConstraint(),
            GymUsageConstraint(),
            JiritsuActivityConstraint(),
            # 他の制約も追加...
        ])
    
    def add_constraint(self, constraint: Constraint):
        """制約を追加"""
        self.constraints.append(constraint)
    
    def check_assignment(self, assignment: Assignment, timetable: 'Timetable') -> List[Violation]:
        """割り当てに対するすべての制約をチェック"""
        violations = []
        for constraint in self.constraints:
            violation = constraint.check(assignment, timetable)
            if violation:
                violations.append(violation)
        return violations
    
    def check_all(self, timetable: 'Timetable') -> List[Violation]:
        """時間割全体の制約をチェック"""
        violations = []
        for assignment in timetable.get_all_assignments():
            violations.extend(self.check_assignment(assignment, timetable))
        return self._deduplicate_violations(violations)
    
    def fix_violations(self, violations: List[Violation], timetable: 'Timetable') -> Dict[str, any]:
        """違反を修正"""
        results = {
            'total': len(violations),
            'fixed': 0,
            'failed': 0,
            'details': []
        }
        
        # 優先度順にソート
        sorted_violations = sorted(violations, 
                                 key=lambda v: (v.priority.value, v.type.value))
        
        for violation in sorted_violations:
            # 該当する制約を見つける
            for constraint in self.constraints:
                if self._can_handle_violation(constraint, violation):
                    if constraint.can_fix(violation, timetable):
                        if constraint.fix(violation, timetable):
                            results['fixed'] += 1
                            results['details'].append({
                                'violation': violation,
                                'status': 'fixed'
                            })
                        else:
                            results['failed'] += 1
                            results['details'].append({
                                'violation': violation,
                                'status': 'failed'
                            })
                    break
        
        return results
    
    def _can_handle_violation(self, constraint: Constraint, violation: Violation) -> bool:
        """制約が違反を処理できるかチェック"""
        # 制約のタイプと違反のタイプをマッチング
        constraint_type_map = {
            TeacherConflictConstraint: ViolationType.TEACHER_CONFLICT,
            GymUsageConstraint: ViolationType.GYM_USAGE,
            JiritsuActivityConstraint: ViolationType.JIRITSU_ACTIVITY,
        }
        
        expected_type = constraint_type_map.get(type(constraint))
        return expected_type == violation.type
    
    def _deduplicate_violations(self, violations: List[Violation]) -> List[Violation]:
        """重複する違反を削除"""
        seen = set()
        unique_violations = []
        
        for violation in violations:
            # 違反の一意キーを作成
            key = (
                violation.type,
                frozenset(violation.location.items()),
                violation.description
            )
            
            if key not in seen:
                seen.add(key)
                unique_violations.append(violation)
        
        return unique_violations