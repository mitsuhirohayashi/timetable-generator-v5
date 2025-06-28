"""月曜6校時固定制約 - 全クラスの月曜6校時を欠課として固定"""
from ..entities.schedule import Schedule
from ..entities.school import School
from .base import (
    Constraint, ConstraintResult, ConstraintViolation
)
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
from ..entities.school import Subject


class MondaySixthPeriodConstraint(Constraint):
    """月曜6校時固定制約 - QA.txtの6限目ルールに基づいて制約をチェック"""
    
    def __init__(self, sixth_period_rules=None, respect_input=True):
        from .base import ConstraintType, ConstraintPriority
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="月曜6校時固定制約",
            description="6限目ルールに基づいて月曜6校時を制約"
        )
        # 6限目ルール（QA.txtから読み込み）
        # 例: {1: {"月": "欠"}, 2: {"月": "欠"}, 3: {"月": "normal"}}
        self.sixth_period_rules = sixth_period_rules or {}
        # input.csvの内容を尊重するフラグ
        self.respect_input = respect_input
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """配置前チェック：6限目ルールに基づいてチェック"""
        # 月曜6校時の場合
        if time_slot.day == "月" and time_slot.period == 6:
            # input.csvの内容を尊重する場合
            if self.respect_input:
                # 既に何か配置されている場合は、それを保持（変更を許可しない）
                existing = schedule.get_assignment(time_slot, assignment.class_ref)
                if existing and existing.subject.name in {'欠', 'YT', '学', '総', '道', '学総', '行'}:
                    # 固定科目が既にある場合は、同じ科目のみ許可
                    return assignment.subject.name == existing.subject.name
            
            # 6限目ルールが設定されている場合
            if self.sixth_period_rules:
                grade_rules = self.sixth_period_rules.get(assignment.class_ref.grade, {})
                if "月" in grade_rules:
                    rule = grade_rules["月"]
                    if rule == "normal":
                        # 通常授業OK
                        return True
                    elif rule == "欠":
                        # 欠課のみ許可
                        return assignment.subject.name == '欠'
                    elif rule == "YT":
                        # YTのみ許可
                        return assignment.subject.name == 'YT'
            
            # デフォルトルールは適用しない（input.csvを尊重）
            return True
        # それ以外の時間は制約なし
        return True
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """月曜6校時が6限目ルールに従っているか検証"""
        violations = []
        
        # 月曜6校時のTimeSlot
        monday_sixth = TimeSlot("月", 6)  # 月曜6校時
        
        # 全クラスをチェック
        for class_ref in school.get_all_classes():
            expected_subject = None
            
            # 6限目ルールから期待される科目を取得
            if self.sixth_period_rules:
                grade_rules = self.sixth_period_rules.get(class_ref.grade, {})
                if "月" in grade_rules:
                    rule = grade_rules["月"]
                    if rule == "normal":
                        # 通常授業OK - チェック不要
                        continue
                    elif rule == "欠":
                        expected_subject = "欠"
                    elif rule == "YT":
                        expected_subject = "YT"
            
            # ルールがない場合
            if expected_subject is None:
                # input.csvの内容を尊重する場合は検証をスキップ
                if self.respect_input:
                    continue
                # 3年生の通常学級は制約を適用しない
                if class_ref.grade == 3 and class_ref.is_regular_class():
                    continue
                # デフォルトルールは適用しない
                continue
            
            assignment = schedule.get_assignment(monday_sixth, class_ref)
            actual_subject = assignment.subject.name if assignment else "空き"
            
            # 期待される科目と異なる場合は違反
            if actual_subject != expected_subject:
                violation = ConstraintViolation(
                    description=f"月曜6校時固定違反: {class_ref}の月曜6校時は{expected_subject}であるべきですが、{actual_subject}になっています",
                    time_slot=monday_sixth,
                    assignment=assignment,
                    severity="ERROR"
                )
                violations.append(violation)
        
        return ConstraintResult(self.__class__.__name__, violations)