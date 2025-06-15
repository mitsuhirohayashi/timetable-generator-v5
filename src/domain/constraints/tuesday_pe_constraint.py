"""火曜日体育複数クラス実施制約 - 火曜日1-3校時に複数の体育授業を同時実施することを推奨"""
from typing import List, Dict
from collections import defaultdict

from .base import (
    SoftConstraint, ConstraintResult, ConstraintPriority, ConstraintViolation
)
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, Subject
from ..value_objects.assignment import Assignment


class TuesdayPEMultipleConstraint(SoftConstraint):
    """火曜日体育複数クラス実施制約 - 火曜日の1-3校時に複数の体育授業を同時実施することを推奨"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.MEDIUM,
            name="火曜日体育複数クラス実施制約",
            description="火曜日の1-3校時に体育授業を複数クラスで同時実施することを推奨"
        )
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """火曜日1-3校時の体育授業の同時実施状況を検証し、推奨スコアを計算"""
        violations = []
        
        # 火曜日の1-3校時をチェック
        pe_subject = Subject("保")
        tuesday_morning_slots = [
            TimeSlot("火", 1),
            TimeSlot("火", 2),
            TimeSlot("火", 3)
        ]
        
        # 各時間枠での体育授業数をカウント
        pe_counts: Dict[TimeSlot, int] = {}
        pe_assignments: Dict[TimeSlot, List[Assignment]] = defaultdict(list)
        
        for time_slot in tuesday_morning_slots:
            assignments = schedule.get_assignments_by_time_slot(time_slot)
            pe_count = 0
            
            for assignment in assignments:
                if assignment.subject == pe_subject:
                    pe_count += 1
                    pe_assignments[time_slot].append(assignment)
            
            pe_counts[time_slot] = pe_count
        
        # 単独実施の体育授業を違反として記録（ソフト制約なのでWARNING）
        for time_slot, count in pe_counts.items():
            if count == 1:
                # 単独実施の場合、改善を促す
                assignment = pe_assignments[time_slot][0]
                violation = ConstraintViolation(
                    description=f"火曜{time_slot.period}校時: 体育授業が1クラスのみで実施されています。複数クラスでの同時実施を推奨します",
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="WARNING"
                )
                violations.append(violation)
        
        # 火曜日午前中に体育が全くない場合も警告
        total_pe_count = sum(pe_counts.values())
        if total_pe_count == 0:
            # 代表的な時間枠として火曜1校時を使用
            violation = ConstraintViolation(
                description="火曜日1-3校時に体育授業が設定されていません。複数クラスでの同時実施を推奨します",
                time_slot=tuesday_morning_slots[0],
                assignment=None,
                severity="WARNING"
            )
            violations.append(violation)
        
        # メッセージに同時実施の状況を含める
        message_parts = []
        for time_slot, count in pe_counts.items():
            if count > 0:
                message_parts.append(f"火曜{time_slot.period}校時: {count}クラス")
        
        if message_parts:
            message = f"火曜日体育実施状況 - {', '.join(message_parts)}"
        else:
            message = "火曜日1-3校時に体育授業がありません"
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=message
        )