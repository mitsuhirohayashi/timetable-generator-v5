"""会議ロック制約 - 会議時間は該当教員の授業を禁止"""
from typing import List, Dict, Set, Tuple
from pathlib import Path
from .base import Constraint, ConstraintResult, ConstraintType, ConstraintPriority, ConstraintViolation
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot


class MeetingLockConstraint(Constraint):
    """会議ロック制約 - 会議・委員会の時間は該当メンバーの授業を禁止"""
    
    def __init__(self):
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.CRITICAL,
            name="会議ロック制約",
            description="会議時間は該当教員の授業を禁止"
        )
        # 会議と参加メンバーの定義を設定ファイルから読み込む
        try:
            from ...infrastructure.repositories.config_repository import ConfigRepository
            config_repo = ConfigRepository()
            self.meetings = config_repo.load_meeting_info()
        except:
            # フォールバック - 正しい会議時間を設定
            self.meetings = {
                # (曜日, 校時): (会議名, [参加教員リスト])
                ("火", 4): ("HF", []),     # HF会議 - 火曜4校時 - 全教員参加
                ("火", 3): ("企画", []),   # 企画会議 - 火曜3校時 - 全教員参加
                ("水", 2): ("特会", []),   # 特別活動会議 - 水曜2校時 - 全教員参加
                ("木", 3): ("生指", []),   # 生活指導 - 木曜3校時 - 全教員参加
            }
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """会議時間に該当教員が授業していないか検証"""
        violations = []
        
        # 各会議時間をチェック
        for (day, period), (meeting_name, members) in self.meetings.items():
            time_slot = TimeSlot(day, period)
            assignments = schedule.get_assignments_by_time_slot(time_slot)
            
            for assignment in assignments:
                # 会議時間中でも特別な教科は許可
                if assignment.subject and assignment.subject.name in ["欠", "行", "YT", "道", "学", "学総", "総"]:
                    continue
                
                # 教員がいない場合はスキップ
                if not assignment.teacher:
                    continue
                
                # メンバーリストが空の場合は全教員参加として扱わない（特定のメンバーのみ）
                if members:
                    # 教員名から「先生」を除いてチェック
                    teacher_name = assignment.teacher.name.replace("先生", "")
                    if teacher_name in members:
                        violation = ConstraintViolation(
                            description=f"会議ロック違反: {day}曜{period}校時は{meeting_name}のため{assignment.teacher.name}は授業配置不可",
                            time_slot=time_slot,
                            assignment=assignment,
                            severity="ERROR"
                        )
                        violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"会議ロックチェック完了: {len(violations)}件の違反"
        )