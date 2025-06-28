"""統一制約検証サービス

配置前の制約チェックを一元化し、一貫性のある検証を提供します。
これにより、各サービスで重複していた制約チェックロジックを排除します。
"""
import logging
from typing import Optional, Set, Dict, List, Tuple
from collections import defaultdict

from ..entities.schedule import Schedule
from ..entities.school import School, Subject, Teacher
from ..value_objects.time_slot import TimeSlot, ClassReference
from ..value_objects.assignment import Assignment
from .exchange_class_service import ExchangeClassService
from ..utils.schedule_utils import ScheduleUtils


class ConstraintValidator:
    """統一制約検証サービス"""
    
    def __init__(self, absence_loader=None):
        """初期化
        
        Args:
            absence_loader: 教師不在情報ローダー
        """
        self.logger = logging.getLogger(__name__)
        self.exchange_service = ExchangeClassService()
        
        # 教師の欠席情報
        self.teacher_absences: Dict[str, Set[Tuple[str, int]]] = {}
        if absence_loader and hasattr(absence_loader, 'teacher_absences'):
            self.teacher_absences = absence_loader.teacher_absences
        
        # 5組クラスの設定
        self._load_grade5_classes()
        
        # テスト期間の設定
        self._load_test_periods()
    
    def _load_grade5_classes(self) -> None:
        """5組クラスを読み込む"""
        import re
        grade5_list = ScheduleUtils.get_grade5_classes()
        self.grade5_classes = set()
        
        for class_str in grade5_list:
            # "1年5組" -> ClassReference(1, 5)
            class_match = re.match(r'(\d+)年(\d+)組', class_str)
            if class_match:
                self.grade5_classes.add(ClassReference(int(class_match.group(1)), int(class_match.group(2))))
    
    def _load_test_periods(self) -> None:
        """テスト期間を読み込む"""
        self.test_periods: Set[Tuple[str, int]] = set()
        try:
            from ...infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
            test_periods_list = followup_parser.parse_test_periods()
            
            for test_period in test_periods_list:
                if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
                    day = test_period.day
                    for period in test_period.periods:
                        self.test_periods.add((day, period))
            
            if self.test_periods:
                self.logger.info(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
        except Exception as e:
            self.logger.warning(f"テスト期間情報の読み込みに失敗: {e}")
    
    def can_place_assignment(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        assignment: Assignment,
        check_level: str = 'strict'
    ) -> Tuple[bool, Optional[str]]:
        """指定された割り当てが配置可能かどうか総合的にチェック
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: 配置する時間枠
            assignment: 配置する割り当て
            check_level: チェックレベル ('strict', 'normal', 'relaxed')
            
        Returns:
            (配置可能か, エラーメッセージ)
        """
        # 基本的なチェック
        if schedule.is_locked(time_slot, assignment.class_ref):
            return False, "このスロットはロックされています"
        
        # 既に割り当てがある場合
        existing = schedule.get_assignment(time_slot, assignment.class_ref)
        if existing:
            return False, "既に割り当てがあります"
        
        # テスト期間チェック
        if self.is_test_period(time_slot):
            return False, "テスト期間です"
        
        # 教師不在チェック
        if not self.check_teacher_availability(assignment.teacher, time_slot):
            return False, f"{assignment.teacher.name}先生は不在です"
        
        # 教師重複チェック（5組の合同授業を考慮）
        conflict_class = self.check_teacher_conflict(schedule, school, time_slot, assignment)
        if conflict_class:
            return False, f"{assignment.teacher.name}先生は{conflict_class}で授業があります"
        
        # 日内重複チェック
        if check_level in ['strict', 'normal']:
            duplicate_count = self.get_daily_subject_count(schedule, assignment.class_ref, time_slot.day, assignment.subject)
            max_allowed = self.get_max_daily_occurrences(assignment.subject, check_level)
            if duplicate_count >= max_allowed:
                return False, f"{assignment.subject.name}は既に{duplicate_count}回配置されています"
        
        # 体育館使用チェック
        if assignment.subject.name == "保":
            gym_class = self.check_gym_conflict(schedule, school, time_slot, assignment.class_ref)
            if gym_class:
                return False, f"体育館は{gym_class}が使用中です"
        
        # 交流学級制約チェック
        if self.exchange_service.is_exchange_class(assignment.class_ref):
            if not self.exchange_service.can_place_subject_for_exchange_class(
                schedule, time_slot, assignment.class_ref, assignment.subject
            ):
                return False, "交流学級の制約に違反します"
        
        # 親学級制約チェック
        if self.exchange_service.is_parent_class(assignment.class_ref):
            if not self.exchange_service.can_place_subject_for_parent_class(
                schedule, time_slot, assignment.class_ref, assignment.subject
            ):
                return False, "親学級の制約に違反します（交流学級が自立活動中）"
        
        # 5組同期チェック
        if assignment.class_ref in self.grade5_classes:
            sync_error = self.check_grade5_sync(schedule, time_slot, assignment)
            if sync_error:
                return False, sync_error
        
        return True, None
    
    def check_teacher_availability(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師が指定された時間に利用可能かチェック"""
        if teacher.name in self.teacher_absences:
            absences = self.teacher_absences[teacher.name]
            return (time_slot.day, time_slot.period) not in absences
        return True
    
    def check_teacher_conflict(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        assignment: Assignment
    ) -> Optional[ClassReference]:
        """教師の重複をチェック（5組の合同授業を考慮）
        
        Returns:
            重複しているクラス（なければNone）
        """
        # 5組の合同授業の場合は特別処理
        if assignment.class_ref in self.grade5_classes:
            # 他の5組で同じ教師が同じ時間に授業している場合はOK
            grade5_with_teacher = []
            for grade5_class in self.grade5_classes:
                existing = schedule.get_assignment(time_slot, grade5_class)
                if existing and existing.teacher == assignment.teacher:
                    grade5_with_teacher.append(grade5_class)
            
            # 全て5組ならOK
            if len(grade5_with_teacher) == len([c for c in grade5_with_teacher if c in self.grade5_classes]):
                return None
        
        # 通常の重複チェック
        for class_ref in school.get_all_classes():
            if class_ref == assignment.class_ref:
                continue
            
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing and existing.teacher == assignment.teacher:
                # 5組同士の場合はOK
                if class_ref in self.grade5_classes and assignment.class_ref in self.grade5_classes:
                    continue
                return class_ref
        
        return None
    
    def get_daily_subject_count(
        self, 
        schedule: Schedule, 
        class_ref: ClassReference, 
        day: str, 
        subject: Subject
    ) -> int:
        """指定された日のクラスにおける科目の出現回数を取得"""
        count = 0
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                count += 1
        return count
    
    def get_max_daily_occurrences(self, subject: Subject, check_level: str) -> int:
        """科目の1日の最大出現回数を取得"""
        if check_level == 'relaxed':
            return 3  # 緩い制限
        elif check_level == 'normal':
            # 主要教科は2回まで許可
            if subject.name in {"算", "国", "理", "社", "英", "数"}:
                return 2
            return 1
        else:  # strict
            return 1
    
    def check_gym_conflict(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        target_class: ClassReference
    ) -> Optional[ClassReference]:
        """体育館の使用競合をチェック
        
        Returns:
            体育館を使用中のクラス（なければNone）
        """
        # テスト期間中は体育館制約なし
        if self.is_test_period(time_slot):
            return None
        
        for class_ref in school.get_all_classes():
            if class_ref == target_class:
                continue
            
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing and existing.subject.name == "保":
                return class_ref
        
        return None
    
    def check_grade5_sync(
        self, 
        schedule: Schedule, 
        time_slot: TimeSlot, 
        assignment: Assignment
    ) -> Optional[str]:
        """5組の同期をチェック
        
        Returns:
            エラーメッセージ（問題なければNone）
        """
        if assignment.class_ref not in self.grade5_classes:
            return None
        
        # 他の5組の割り当てをチェック
        for other_class in self.grade5_classes:
            if other_class == assignment.class_ref:
                continue
            
            existing = schedule.get_assignment(time_slot, other_class)
            if existing and existing.subject != assignment.subject:
                return f"5組同期違反: {other_class}は{existing.subject.name}です"
        
        return None
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたスロットがテスト期間かどうか判定"""
        return (time_slot.day, time_slot.period) in self.test_periods
    
    def check_consecutive_periods(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> bool:
        """連続コマになるかチェック
        
        Returns:
            連続コマになる場合True
        """
        # 前後の時限を確認
        prev_period = time_slot.period - 1
        next_period = time_slot.period + 1
        
        # 前の時限
        if prev_period >= 1:
            prev_slot = TimeSlot(day=time_slot.day, period=prev_period)
            prev_assignment = schedule.get_assignment(prev_slot, class_ref)
            if prev_assignment and prev_assignment.subject == subject:
                return True
        
        # 次の時限
        if next_period <= 6:
            next_slot = TimeSlot(day=time_slot.day, period=next_period)
            next_assignment = schedule.get_assignment(next_slot, class_ref)
            if next_assignment and next_assignment.subject == subject:
                return True
        
        return False
    
    def validate_all_constraints(
        self,
        schedule: Schedule,
        school: School
    ) -> List[Dict]:
        """スケジュール全体の制約違反を検証
        
        Returns:
            違反情報のリスト
        """
        violations = []
        
        # 交流学級同期違反
        exchange_violations = self.exchange_service.get_exchange_violations(schedule)
        violations.extend(exchange_violations)
        
        # 日内重複違反
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subject_counts = defaultdict(int)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subject_counts[assignment.subject.name] += 1
                
                for subject_name, count in subject_counts.items():
                    if subject_name in ScheduleUtils.FIXED_SUBJECTS:
                        continue
                    
                    max_allowed = 1
                    if subject_name in {"算", "国", "理", "社", "英", "数"}:
                        max_allowed = 2
                    
                    if count > max_allowed:
                        violations.append({
                            'type': 'daily_duplicate',
                            'class_ref': class_ref,
                            'day': day,
                            'subject': subject_name,
                            'count': count,
                            'message': f"{class_ref}の{day}曜日に{subject_name}が{count}回配置されています"
                        })
        
        # 教師不在違反
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and not self.check_teacher_availability(assignment.teacher, time_slot):
                        violations.append({
                            'type': 'teacher_absence',
                            'class_ref': class_ref,
                            'time_slot': time_slot,
                            'teacher': assignment.teacher.name,
                            'message': f"{assignment.teacher.name}先生が不在の{time_slot}に{class_ref}で授業が配置されています"
                        })
        
        return violations