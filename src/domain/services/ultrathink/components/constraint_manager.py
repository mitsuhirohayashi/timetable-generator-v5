"""
制約管理システム

制約の効率的な管理と高速な制約チェックを提供。
制約伝播による探索空間の削減も実装。
"""
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import numpy as np

from ....entities.schedule import Schedule
from ....entities.school import School, Teacher, Subject
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


class ConstraintType(Enum):
    """制約タイプ"""
    TEACHER_CONFLICT = "teacher_conflict"
    DAILY_DUPLICATE = "daily_duplicate"
    FIXED_SUBJECT = "fixed_subject"
    EXCHANGE_SYNC = "exchange_sync"
    GRADE5_SYNC = "grade5_sync"
    JIRITSU_PARENT = "jiritsu_parent"
    TEACHER_ABSENCE = "teacher_absence"
    GYM_USAGE = "gym_usage"
    TEST_PERIOD = "test_period"
    STANDARD_HOURS = "standard_hours"


class ConstraintPriority(Enum):
    """制約優先度"""
    CRITICAL = 0  # 絶対に違反できない
    HIGH = 1      # 非常に重要
    MEDIUM = 2    # 重要
    LOW = 3       # 望ましい


@dataclass
class ConstraintViolation:
    """制約違反情報"""
    type: ConstraintType
    priority: ConstraintPriority
    message: str
    time_slot: Optional[TimeSlot] = None
    class_ref: Optional[ClassReference] = None
    details: Dict[str, Any] = None


@dataclass
class ConstraintCheckResult:
    """制約チェック結果"""
    is_valid: bool
    violations: List[ConstraintViolation]
    propagated_constraints: Optional[Set[Tuple[TimeSlot, ClassReference]]] = None


class ConstraintManager(LoggingMixin):
    """制約管理システム"""
    
    def __init__(
        self,
        enable_propagation: bool = True,
        cache: Optional['PerformanceCache'] = None
    ):
        super().__init__()
        self.enable_propagation = enable_propagation
        self.cache = cache
        
        # 制約の優先度マップ
        self.constraint_priorities = {
            ConstraintType.TEACHER_CONFLICT: ConstraintPriority.CRITICAL,
            ConstraintType.FIXED_SUBJECT: ConstraintPriority.CRITICAL,
            ConstraintType.TEST_PERIOD: ConstraintPriority.CRITICAL,
            ConstraintType.JIRITSU_PARENT: ConstraintPriority.HIGH,
            ConstraintType.EXCHANGE_SYNC: ConstraintPriority.HIGH,
            ConstraintType.GRADE5_SYNC: ConstraintPriority.HIGH,
            ConstraintType.TEACHER_ABSENCE: ConstraintPriority.HIGH,
            ConstraintType.DAILY_DUPLICATE: ConstraintPriority.MEDIUM,
            ConstraintType.GYM_USAGE: ConstraintPriority.MEDIUM,
            ConstraintType.STANDARD_HOURS: ConstraintPriority.LOW
        }
        
        # 制約グラフ（制約伝播用）
        self.constraint_graph = defaultdict(set)
        
        # 制約チェック統計
        self.check_stats = {
            'total_checks': 0,
            'cache_hits': 0,
            'violations_found': 0
        }
    
    def check_assignment(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment,
        school: School,
        context: Optional[Dict[str, Any]] = None
    ) -> ConstraintCheckResult:
        """
        割り当ての制約チェック
        
        Args:
            schedule: 現在のスケジュール
            time_slot: 配置時間
            assignment: 配置内容
            school: 学校情報
            context: 追加コンテキスト
            
        Returns:
            ConstraintCheckResult: チェック結果
        """
        self.check_stats['total_checks'] += 1
        
        # キャッシュチェック
        cache_key = self._get_cache_key(time_slot, assignment)
        if self.cache and cache_key:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                self.check_stats['cache_hits'] += 1
                return cached_result
        
        violations = []
        
        # 各制約をチェック（優先度順）
        for constraint_type in sorted(
            ConstraintType,
            key=lambda ct: self.constraint_priorities[ct].value
        ):
            constraint_violations = self._check_constraint(
                constraint_type,
                schedule,
                time_slot,
                assignment,
                school,
                context
            )
            violations.extend(constraint_violations)
            
            # CRITICALな違反があれば即座に終了
            if (constraint_violations and 
                self.constraint_priorities[constraint_type] == ConstraintPriority.CRITICAL):
                break
        
        # 制約伝播
        propagated = None
        if self.enable_propagation and not violations:
            propagated = self._propagate_constraints(
                schedule, time_slot, assignment, school
            )
        
        # 結果作成
        result = ConstraintCheckResult(
            is_valid=len(violations) == 0,
            violations=violations,
            propagated_constraints=propagated
        )
        
        # キャッシュ保存
        if self.cache and cache_key:
            self.cache.set(cache_key, result, ttl=300)
        
        # 統計更新
        if violations:
            self.check_stats['violations_found'] += len(violations)
        
        return result
    
    def check_schedule(
        self,
        schedule: Schedule,
        school: School,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ConstraintViolation]:
        """
        スケジュール全体の制約チェック
        
        Returns:
            List[ConstraintViolation]: 違反リスト
        """
        violations = []
        
        # 全ての割り当てをチェック
        for time_slot, assignment in schedule.get_all_assignments():
            result = self.check_assignment(
                schedule, time_slot, assignment, school, context
            )
            violations.extend(result.violations)
        
        # グローバル制約のチェック
        violations.extend(
            self._check_global_constraints(schedule, school, context)
        )
        
        return violations
    
    def _check_constraint(
        self,
        constraint_type: ConstraintType,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment,
        school: School,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ConstraintViolation]:
        """個別制約のチェック"""
        
        if constraint_type == ConstraintType.TEACHER_CONFLICT:
            return self._check_teacher_conflict(
                schedule, time_slot, assignment, school
            )
        elif constraint_type == ConstraintType.DAILY_DUPLICATE:
            return self._check_daily_duplicate(
                schedule, time_slot, assignment
            )
        elif constraint_type == ConstraintType.FIXED_SUBJECT:
            return self._check_fixed_subject(
                schedule, time_slot, assignment, context
            )
        elif constraint_type == ConstraintType.EXCHANGE_SYNC:
            return self._check_exchange_sync(
                schedule, time_slot, assignment, school
            )
        elif constraint_type == ConstraintType.GRADE5_SYNC:
            return self._check_grade5_sync(
                schedule, time_slot, assignment
            )
        elif constraint_type == ConstraintType.JIRITSU_PARENT:
            return self._check_jiritsu_parent(
                schedule, time_slot, assignment, school
            )
        elif constraint_type == ConstraintType.TEACHER_ABSENCE:
            return self._check_teacher_absence(
                time_slot, assignment, school
            )
        elif constraint_type == ConstraintType.GYM_USAGE:
            return self._check_gym_usage(
                schedule, time_slot, assignment
            )
        elif constraint_type == ConstraintType.TEST_PERIOD:
            return self._check_test_period(
                time_slot, assignment, context
            )
        elif constraint_type == ConstraintType.STANDARD_HOURS:
            return self._check_standard_hours(
                schedule, assignment, school
            )
        
        return []
    
    def _check_teacher_conflict(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment,
        school: School
    ) -> List[ConstraintViolation]:
        """教師重複チェック"""
        violations = []
        
        if not assignment.teacher:
            return violations
        
        # CRITICAL FIX: Test periods should NOT allow teacher duplicates
        # This was causing a massive increase in violations
        # Teachers can supervise multiple classes, but still can't be in two places at once
        
        # 同じ時間の他のクラスをチェック
        for class_ref in school.get_all_classes():
            if class_ref == assignment.class_ref:
                continue
            
            other_assignment = schedule.get_assignment(time_slot, class_ref)
            if (other_assignment and other_assignment.teacher and
                other_assignment.teacher.name == assignment.teacher.name):
                
                violations.append(ConstraintViolation(
                    type=ConstraintType.TEACHER_CONFLICT,
                    priority=self.constraint_priorities[ConstraintType.TEACHER_CONFLICT],
                    message=f"{assignment.teacher.name}先生が{time_slot}に重複",
                    time_slot=time_slot,
                    class_ref=assignment.class_ref,
                    details={
                        'teacher': assignment.teacher.name,
                        'conflicting_class': f"{class_ref.grade}-{class_ref.class_number}"
                    }
                ))
        
        return violations
    
    def _check_daily_duplicate(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> List[ConstraintViolation]:
        """日内重複チェック"""
        violations = []
        
        # 同じ日の他の時限をチェック
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            other_slot = TimeSlot(time_slot.day, period)
            other_assignment = schedule.get_assignment(other_slot, assignment.class_ref)
            
            if (other_assignment and 
                other_assignment.subject.name == assignment.subject.name):
                
                violations.append(ConstraintViolation(
                    type=ConstraintType.DAILY_DUPLICATE,
                    priority=self.constraint_priorities[ConstraintType.DAILY_DUPLICATE],
                    message=f"{assignment.class_ref.grade}-{assignment.class_ref.class_number} "
                           f"{time_slot.day}曜日に{assignment.subject.name}が重複",
                    time_slot=time_slot,
                    class_ref=assignment.class_ref,
                    details={
                        'subject': assignment.subject.name,
                        'existing_period': period
                    }
                ))
        
        return violations
    
    def _check_exchange_sync(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment,
        school: School
    ) -> List[ConstraintViolation]:
        """交流学級同期チェック"""
        violations = []
        
        # 交流学級マッピング
        exchange_mapping = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
        
        # 交流学級の場合
        if assignment.class_ref in exchange_mapping:
            parent_class = exchange_mapping[assignment.class_ref]
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            
            # 自立活動・日生・作業以外は同期が必要
            if assignment.subject.name not in ["自立", "日生", "作業"]:
                if (not parent_assignment or 
                    parent_assignment.subject.name != assignment.subject.name):
                    
                    violations.append(ConstraintViolation(
                        type=ConstraintType.EXCHANGE_SYNC,
                        priority=self.constraint_priorities[ConstraintType.EXCHANGE_SYNC],
                        message=f"交流学級{assignment.class_ref.grade}-{assignment.class_ref.class_number} "
                               f"と親学級の同期違反",
                        time_slot=time_slot,
                        class_ref=assignment.class_ref,
                        details={
                            'parent_class': f"{parent_class.grade}-{parent_class.class_number}",
                            'exchange_subject': assignment.subject.name,
                            'parent_subject': parent_assignment.subject.name if parent_assignment else "なし"
                        }
                    ))
        
        return violations
    
    def _check_jiritsu_parent(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment,
        school: School
    ) -> List[ConstraintViolation]:
        """自立活動時の親学級制約チェック"""
        violations = []
        
        if assignment.subject.name != "自立":
            return violations
        
        # 交流学級マッピング
        exchange_mapping = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
        
        if assignment.class_ref in exchange_mapping:
            parent_class = exchange_mapping[assignment.class_ref]
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            
            if (not parent_assignment or 
                parent_assignment.subject.name not in ["数", "英"]):
                
                violations.append(ConstraintViolation(
                    type=ConstraintType.JIRITSU_PARENT,
                    priority=self.constraint_priorities[ConstraintType.JIRITSU_PARENT],
                    message=f"交流学級{assignment.class_ref.grade}-{assignment.class_ref.class_number} "
                           f"の自立活動時、親学級が数学・英語以外",
                    time_slot=time_slot,
                    class_ref=assignment.class_ref,
                    details={
                        'parent_class': f"{parent_class.grade}-{parent_class.class_number}",
                        'parent_subject': parent_assignment.subject.name if parent_assignment else "なし"
                    }
                ))
        
        return violations
    
    def _propagate_constraints(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment,
        school: School
    ) -> Set[Tuple[TimeSlot, ClassReference]]:
        """制約伝播による影響範囲の特定"""
        affected = set()
        
        # 教師の制約伝播
        if assignment.teacher:
            # 同じ時間の他のクラスは同じ教師を使えない
            for class_ref in school.get_all_classes():
                if class_ref != assignment.class_ref:
                    affected.add((time_slot, class_ref))
        
        # 日内重複の制約伝播
        # 同じ日の他の時間帯で同じ科目は配置できない
        for period in range(1, 7):
            if period != time_slot.period:
                affected.add((TimeSlot(time_slot.day, period), assignment.class_ref))
        
        # 5組の制約伝播
        grade5_classes = {
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        }
        if assignment.class_ref in grade5_classes:
            # 他の5組クラスも同じ科目・教師でなければならない
            for class_ref in grade5_classes:
                if class_ref != assignment.class_ref:
                    affected.add((time_slot, class_ref))
        
        return affected
    
    def _check_global_constraints(
        self,
        schedule: Schedule,
        school: School,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ConstraintViolation]:
        """グローバル制約のチェック（スケジュール全体）"""
        violations = []
        
        # 標準時数のチェック
        for class_ref in school.get_all_classes():
            standard_hours = school.get_all_standard_hours(class_ref)
            
            for subject, expected_hours in standard_hours.items():
                actual_hours = self._count_subject_hours(
                    schedule, class_ref, subject.name
                )
                
                if actual_hours < int(expected_hours):
                    violations.append(ConstraintViolation(
                        type=ConstraintType.STANDARD_HOURS,
                        priority=ConstraintPriority.LOW,
                        message=f"{class_ref.grade}-{class_ref.class_number} "
                               f"{subject.name}が{int(expected_hours) - actual_hours}時間不足",
                        class_ref=class_ref,
                        details={
                            'subject': subject.name,
                            'expected': int(expected_hours),
                            'actual': actual_hours,
                            'shortage': int(expected_hours) - actual_hours
                        }
                    ))
        
        return violations
    
    def _count_subject_hours(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        subject_name: str
    ) -> int:
        """特定クラス・科目の時数をカウント"""
        count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            if (assignment.class_ref == class_ref and
                assignment.subject.name == subject_name):
                count += 1
        return count
    
    def _get_cache_key(
        self,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> Optional[str]:
        """キャッシュキーの生成"""
        if not assignment.teacher:
            return None
        
        return (f"constraint_{time_slot.day}_{time_slot.period}_"
                f"{assignment.class_ref.grade}_{assignment.class_ref.class_number}_"
                f"{assignment.subject.name}_{assignment.teacher.name}")
    
    def _check_fixed_subject(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ConstraintViolation]:
        """固定科目チェック"""
        # コンテキストから固定科目情報を取得
        if not context or 'fixed_subjects' not in context:
            return []
        
        fixed_subjects = context['fixed_subjects']
        if assignment.subject.name in fixed_subjects:
            # 既存の固定科目と異なる場合は違反
            existing = schedule.get_assignment(time_slot, assignment.class_ref)
            if existing and existing.subject.name != assignment.subject.name:
                return [ConstraintViolation(
                    type=ConstraintType.FIXED_SUBJECT,
                    priority=ConstraintPriority.CRITICAL,
                    message=f"固定科目{existing.subject.name}を変更しようとしました",
                    time_slot=time_slot,
                    class_ref=assignment.class_ref
                )]
        
        return []
    
    def _check_grade5_sync(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> List[ConstraintViolation]:
        """5組同期チェック"""
        violations = []
        
        grade5_classes = {
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        }
        
        if assignment.class_ref not in grade5_classes:
            return violations
        
        # 他の5組クラスと同じ科目・教師か確認
        for class_ref in grade5_classes:
            if class_ref == assignment.class_ref:
                continue
            
            other_assignment = schedule.get_assignment(time_slot, class_ref)
            if not other_assignment:
                continue
            
            if (other_assignment.subject.name != assignment.subject.name or
                (other_assignment.teacher and assignment.teacher and
                 other_assignment.teacher.name != assignment.teacher.name)):
                
                violations.append(ConstraintViolation(
                    type=ConstraintType.GRADE5_SYNC,
                    priority=ConstraintPriority.HIGH,
                    message=f"5組の同期違反: {assignment.class_ref}と{class_ref}",
                    time_slot=time_slot,
                    class_ref=assignment.class_ref,
                    details={
                        'other_class': f"{class_ref.grade}-{class_ref.class_number}",
                        'this_subject': assignment.subject.name,
                        'other_subject': other_assignment.subject.name
                    }
                ))
        
        return violations
    
    def _check_teacher_absence(
        self,
        time_slot: TimeSlot,
        assignment: Assignment,
        school: School
    ) -> List[ConstraintViolation]:
        """教師不在チェック"""
        if not assignment.teacher:
            return []
        
        if school.is_teacher_unavailable(
            time_slot.day,
            time_slot.period,
            assignment.teacher
        ):
            return [ConstraintViolation(
                type=ConstraintType.TEACHER_ABSENCE,
                priority=ConstraintPriority.HIGH,
                message=f"{assignment.teacher.name}先生は{time_slot}に不在",
                time_slot=time_slot,
                class_ref=assignment.class_ref
            )]
        
        return []
    
    def _check_gym_usage(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> List[ConstraintViolation]:
        """体育館使用チェック"""
        if assignment.subject.name != "保":
            return []
        
        violations = []
        
        # 5組は3クラス合同なので除外
        grade5_classes = {
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        }
        
        if assignment.class_ref in grade5_classes:
            return violations
        
        # 他のクラスで体育があるか確認
        for time_slot_check, other_assignment in schedule.get_all_assignments():
            if (time_slot_check == time_slot and
                other_assignment.subject.name == "保" and
                other_assignment.class_ref != assignment.class_ref and
                other_assignment.class_ref not in grade5_classes):
                
                violations.append(ConstraintViolation(
                    type=ConstraintType.GYM_USAGE,
                    priority=ConstraintPriority.MEDIUM,
                    message=f"体育館が{time_slot}に重複使用",
                    time_slot=time_slot,
                    class_ref=assignment.class_ref,
                    details={
                        'conflicting_class': f"{other_assignment.class_ref.grade}-{other_assignment.class_ref.class_number}"
                    }
                ))
        
        return violations
    
    def _check_test_period(
        self,
        time_slot: TimeSlot,
        assignment: Assignment,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ConstraintViolation]:
        """テスト期間チェック"""
        if not context or 'test_periods' not in context:
            return []
        
        test_periods = context['test_periods']
        if (time_slot.day, time_slot.period) in test_periods:
            # テスト期間中は保護された科目のみ許可
            protected_subjects = context.get('test_period_subjects', {"テスト", "技家", "行"})
            if assignment.subject.name not in protected_subjects:
                return [ConstraintViolation(
                    type=ConstraintType.TEST_PERIOD,
                    priority=ConstraintPriority.CRITICAL,
                    message=f"テスト期間{time_slot}に通常授業を配置",
                    time_slot=time_slot,
                    class_ref=assignment.class_ref
                )]
        
        return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """制約チェック統計を取得"""
        return {
            'total_checks': self.check_stats['total_checks'],
            'cache_hits': self.check_stats['cache_hits'],
            'cache_hit_rate': (
                self.check_stats['cache_hits'] / self.check_stats['total_checks']
                if self.check_stats['total_checks'] > 0 else 0
            ),
            'violations_found': self.check_stats['violations_found'],
            'average_violations_per_check': (
                self.check_stats['violations_found'] / self.check_stats['total_checks']
                if self.check_stats['total_checks'] > 0 else 0
            )
        }