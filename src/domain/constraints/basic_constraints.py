"""基本的な制約の実装"""
from typing import List, Dict, Set
from collections import defaultdict

from .base import HardConstraint, SoftConstraint, ConstraintResult, ConstraintPriority
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, Teacher
from ..value_objects.assignment import ConstraintViolation
from ..constants import WEEKDAYS, PERIODS, FIXED_SUBJECTS


class TeacherConflictConstraint(HardConstraint):
    """教員重複制約：同じ時間に同じ教員が複数の場所にいることを防ぐ"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教員重複制約",
            description="同じ時間に同じ教員が複数のクラスを担当することを防ぐ"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：この時間に教員が利用可能かチェック"""
        if not assignment.has_teacher():
            return True
        
        # 欠課は複数クラスで同時に発生しても問題ない
        if assignment.teacher.name == "欠課":
            return True
        
        # YT担当は全クラス同時実施のため複数クラスで同時に発生しても問題ない
        if assignment.teacher.name == "YT担当":
            return True
        
        # 道担当（道徳）も全クラス同時実施のため複数クラスで同時に発生しても問題ない
        if assignment.teacher.name == "道担当":
            return True
        
        # 5組（1-5, 2-5, 3-5）の教師は同時に複数の5組クラスを担当可能
        # ClassValidatorから5組チームティーチング教師を取得
        from ..value_objects.class_validator import ClassValidator
        class_validator = ClassValidator()
        grade5_tt_teachers = class_validator.get_grade5_team_teaching_teachers()
        
        if (assignment.class_ref.class_number == 5 and
            assignment.teacher.name in grade5_tt_teachers):
            # この時間の他の5組クラスの割り当てをチェック
            assignments = schedule.get_assignments_by_time_slot(time_slot)
            for existing_assignment in assignments:
                if (existing_assignment.has_teacher() and 
                    existing_assignment.teacher == assignment.teacher and
                    existing_assignment.class_ref != assignment.class_ref and
                    existing_assignment.class_ref.class_number != 5):
                    # 5組以外のクラスとの重複は不可
                    return False
            return True  # 5組同士の重複は許可
        
        # この時間の全ての割り当てをチェック
        assignments = schedule.get_assignments_by_time_slot(time_slot)
        for existing_assignment in assignments:
            if (existing_assignment.has_teacher() and 
                existing_assignment.teacher == assignment.teacher and
                existing_assignment.class_ref != assignment.class_ref):
                return False  # 既に他のクラスでこの教員が授業中
        
        return True
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        # 各時間枠で教員の重複をチェック
        for day in WEEKDAYS:
            for period in PERIODS:
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                # 教員ごとの割り当てをグループ化
                teacher_assignments = defaultdict(list)
                for assignment in assignments:
                    if assignment.has_teacher():
                        teacher_assignments[assignment.teacher].append(assignment)
                
                # 重複をチェック
                for teacher, teacher_assignments_list in teacher_assignments.items():
                    # 欠課は複数クラスで同時に発生しても問題ない
                    if teacher.name == "欠課":
                        continue
                    
                    # YT担当は全クラス同時実施のため複数クラスで同時に発生しても問題ない
                    if teacher.name == "YT担当":
                        continue
                    
                    # 道担当（道徳）も全クラス同時実施のため複数クラスで同時に発生しても問題ない
                    if teacher.name == "道担当":
                        continue
                    
                    # 5組の教師が複数の5組クラスを担当している場合は許可
                    # ClassValidatorから5組チームティーチング教師を取得
                    from ..value_objects.class_validator import ClassValidator
                    class_validator = ClassValidator()
                    grade5_tt_teachers = class_validator.get_grade5_team_teaching_teachers()
                    
                    if teacher.name in grade5_tt_teachers:
                        # 5組以外のクラスが含まれているかチェック
                        non_grade5_classes = [a for a in teacher_assignments_list 
                                            if a.class_ref.class_number != 5]
                        if len(non_grade5_classes) == 0:
                            # 全て5組クラスなら問題なし
                            continue
                        elif len(non_grade5_classes) > 0 and len(teacher_assignments_list) > 1:
                            # 5組の国語の特殊ケースをチェック
                            grade5_kokugo_assignments = [a for a in teacher_assignments_list 
                                                       if a.class_ref.class_number == 5 and a.subject.name == "国"]
                            
                            if teacher.name in ["寺田", "金子み"]:
                                # 5組の国語の特殊ケース
                                # 寺田先生または金子み先生が5組の国語を担当している場合
                                grade5_kokugo_count = len(grade5_kokugo_assignments)
                                if grade5_kokugo_count > 0:
                                    # 5組の国語を担当している
                                    # 他のクラスも全て国語なら問題なし（例：寺田先生が2-1国語と5組国語を同時に担当）
                                    non_grade5_kokugo = [a for a in non_grade5_classes if a.subject.name == "国"]
                                    if len(non_grade5_classes) == len(non_grade5_kokugo):
                                        # 5組以外も全て国語の授業
                                        continue
                            
                            # それ以外の場合は違反
                            for assignment in teacher_assignments_list:
                                violation = ConstraintViolation(
                                    description=f"教員{teacher}が5組と他クラスで同時刻に授業: {[a.class_ref for a in teacher_assignments_list]}",
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
                            continue
                        
                    if len(teacher_assignments_list) > 1:
                        for assignment in teacher_assignments_list:
                            violation = ConstraintViolation(
                                description=f"教員{teacher}が同時刻に複数クラスを担当: {[a.class_ref for a in teacher_assignments_list]}",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"教員重複チェック完了: {len(violations)}件の違反"
        )


class TeacherAvailabilityConstraint(HardConstraint):
    """教員利用可能性制約：教員の不在時間への割り当てを防ぐ"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教員利用可能性制約", 
            description="教員の不在時間（年休・外勤・出張）への割り当てを防ぐ"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：教員が利用可能かチェック"""
        if not assignment.has_teacher():
            return True
        
        unavailable_teachers = school.get_unavailable_teachers(time_slot.day, time_slot.period)
        return assignment.teacher not in unavailable_teachers
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for day in WEEKDAYS:
            for period in PERIODS:
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                unavailable_teachers = school.get_unavailable_teachers(day, period)
                
                for assignment in assignments:
                    if assignment.has_teacher() and assignment.teacher in unavailable_teachers:
                        violation = ConstraintViolation(
                            description=f"不在の教員{assignment.teacher}に授業が割り当てられています",
                            time_slot=time_slot,
                            assignment=assignment,
                            severity="ERROR"
                        )
                        violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"教員利用可能性チェック完了: {len(violations)}件の違反"
        )


class ExchangeClassConstraint(HardConstraint):
    """交流学級制約：6組・7組が自立活動の時、親学級は数学か英語である必要がある"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.HIGH,
            name="交流学級制約",
            description="交流学級の自立活動時間に親学級が適切な教科を実施することを保証"
        )
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for day in WEEKDAYS:
            for period in PERIODS:
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                # 交流学級で自立活動を実施している場合をチェック
                for assignment in assignments:
                    if (assignment.class_ref.is_exchange_class() and 
                        assignment.subject.name == "自立"):
                        
                        # 親学級の授業をチェック
                        parent_class = assignment.class_ref.get_parent_class()
                        parent_assignment = schedule.get_assignment(time_slot, parent_class)
                        
                        if parent_assignment:
                            if parent_assignment.subject.name not in ["数", "英"]:
                                violation = ConstraintViolation(
                                    description=f"交流学級{assignment.class_ref}が自立活動中、親学級{parent_class}は{parent_assignment.subject}を実施中（数学か英語である必要）",
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
                        else:
                            violation = ConstraintViolation(
                                description=f"交流学級{assignment.class_ref}が自立活動中、親学級{parent_class}に授業が設定されていません",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"交流学級制約チェック完了: {len(violations)}件の違反"
        )


class DailySubjectDuplicateConstraint(HardConstraint):
    """日内重複制約：同じ日に同じ教科が重複することを完全に防ぐ"""
    
    def __init__(self, max_daily_occurrences: int = 1):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,  # 最高優先度
            name="日内重複制約",
            description="同じ日に同じ教科が2回以上実施されることを完全に防ぐ"
        )
        self.max_daily_occurrences = max_daily_occurrences
        # 保護された教科（これらは重複可能）
        self.protected_subjects = FIXED_SUBJECTS
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：この教科が既に同じ日に配置されていないかチェック"""
        # 保護された教科は制限なし
        if assignment.subject.name in self.protected_subjects:
            return True
        
        # 同じ日の同じクラスの授業をチェック
        same_day_count = 0
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            check_slot = TimeSlot(time_slot.day, period)
            existing_assignment = schedule.get_assignment(check_slot, assignment.class_ref)
            
            if (existing_assignment and 
                existing_assignment.subject.name == assignment.subject.name):
                same_day_count += 1
        
        # 1回でも既に配置されていたら配置不可
        return same_day_count < self.max_daily_occurrences
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subjects = schedule.get_daily_subjects(class_ref, day)
                subject_count = defaultdict(int)
                subject_periods = defaultdict(list)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject:
                        subject_count[assignment.subject.name] += 1
                        subject_periods[assignment.subject.name].append(period)
                
                # 重複をチェック（2回以上は完全禁止）
                for subject_name, count in subject_count.items():
                    if count > self.max_daily_occurrences:
                        # 保護された教科はスキップ
                        if subject_name in self.protected_subjects:
                            continue
                        
                        # 2回目以降の違反を記録
                        periods_str = ", ".join([f"{p}時限" for p in subject_periods[subject_name]])
                        
                        for i, period in enumerate(subject_periods[subject_name]):
                            if i >= self.max_daily_occurrences:  # 2回目以降
                                time_slot = TimeSlot(day, period)
                                assignment = schedule.get_assignment(time_slot, class_ref)
                                if assignment:
                                    violation = ConstraintViolation(
                                        description=f"{class_ref}の{day}曜日に{subject_name}が"
                                                   f"{count}回配置されています（{periods_str}）。"
                                                   f"日内重複は完全に禁止されています。",
                                        time_slot=time_slot,
                                        assignment=assignment,
                                        severity="CRITICAL"  # ERRORからCRITICALに変更
                                    )
                                    violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"日内重複チェック完了: {len(violations)}件の過度な重複"
        )


class StandardHoursConstraint(SoftConstraint):
    """標準時数制約：各教科の週当たり時数が標準に合致することを確認"""
    
    def __init__(self, tolerance: float = 0.5):
        super().__init__(
            priority=ConstraintPriority.MEDIUM,
            name="標準時数制約",
            description="各教科の週当たり時数が標準時数に合致することを確認"
        )
        self.tolerance = tolerance  # 許容誤差
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for class_ref in school.get_all_classes():
            required_subjects = school.get_required_subjects(class_ref)
            
            for subject in required_subjects:
                required_hours = school.get_standard_hours(class_ref, subject)
                actual_hours = schedule.count_subject_hours(class_ref, subject)
                
                difference = abs(actual_hours - required_hours)
                if difference > self.tolerance:
                    # 代表的な時間枠を取得（最初の割り当て）
                    assignments = schedule.get_assignments_by_class(class_ref)
                    representative_time_slot = None
                    representative_assignment = None
                    
                    for ts, assignment in assignments:
                        if assignment.subject == subject:
                            representative_time_slot = ts
                            representative_assignment = assignment
                            break
                    
                    if representative_time_slot and representative_assignment:
                        violation = ConstraintViolation(
                            description=f"{class_ref}の{subject}: 標準{required_hours}時間 vs 実際{actual_hours}時間（差分: {difference}）",
                            time_slot=representative_time_slot,
                            assignment=representative_assignment,
                            severity="WARNING"
                        )
                        violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"標準時数チェック完了: {len(violations)}件の違反"
        )