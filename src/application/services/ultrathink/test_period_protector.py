"""
テスト期間保護サービス

Follow-up.csvで指定されたテスト期間中の授業を保護します。
テスト期間中はinput.csvの内容をそのまま保持し、変更を防ぎます。
"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment


class TestPeriodProtector:
    """テスト期間保護サービス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # デフォルトのテスト期間（Follow-up.csvから読み込まれる）
        self.test_periods: Set[Tuple[str, int]] = set()
        
        # 保護すべき割り当て（input.csvから読み込まれる）
        self.protected_assignments: Dict[Tuple[str, int, ClassReference], Assignment] = {}
        
        # テスト期間のメッセージ
        self.test_period_messages: Dict[str, List[str]] = {
            "月": [],
            "火": [],
            "水": [],
            "木": [],
            "金": []
        }
    
    def load_followup_data(self, followup_data: Dict[str, List[str]]):
        """Follow-up.csvからテスト期間情報を読み込む"""
        self.logger.info("Follow-up.csvからテスト期間情報を読み込み中...")
        
        # 各曜日のテスト期間を解析
        for day, messages in followup_data.items():
            if day not in ["月", "火", "水", "木", "金"]:
                continue
            
            for message in messages:
                if "テストなので時間割の変更をしないでください" in message:
                    self.test_period_messages[day].append(message)
                    # テスト期間を抽出
                    periods = self._extract_test_periods_from_message(message, day)
                    self.test_periods.update(periods)
        
        self.logger.info(f"テスト期間を検出: {sorted(list(self.test_periods))}")
    
    def _extract_test_periods_from_message(self, message: str, day: str) -> Set[Tuple[str, int]]:
        """メッセージからテスト期間を抽出"""
        periods = set()
        
        # パターン: "１・２・３校時はテスト"
        if "１・２・３校時" in message:
            periods.update([(day, 1), (day, 2), (day, 3)])
        elif "１・２校時" in message:
            periods.update([(day, 1), (day, 2)])
        elif "１校時" in message:
            periods.add((day, 1))
        elif "２校時" in message:
            periods.add((day, 2))
        elif "３校時" in message:
            periods.add((day, 3))
        elif "４校時" in message:
            periods.add((day, 4))
        elif "５校時" in message:
            periods.add((day, 5))
        elif "６校時" in message:
            periods.add((day, 6))
        
        return periods
    
    def load_initial_schedule(self, initial_schedule: Schedule):
        """初期スケジュール（input.csv）からテスト期間の割り当てを保存"""
        self.logger.info("初期スケジュールからテスト期間の割り当てを保存中...")
        
        for time_slot, assignment in initial_schedule.get_all_assignments():
            if self.is_test_period(time_slot):
                key = (time_slot.day, time_slot.period, assignment.class_ref)
                self.protected_assignments[key] = assignment
                self.logger.debug(
                    f"保護: {time_slot.day}{time_slot.period}限 "
                    f"{assignment.class_ref.grade}-{assignment.class_ref.class_number} "
                    f"{assignment.subject.name}"
                )
        
        self.logger.info(f"保護された割り当て数: {len(self.protected_assignments)}")
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたタイムスロットがテスト期間かどうか"""
        return (time_slot.day, time_slot.period) in self.test_periods
    
    def get_protected_assignment(
        self, 
        time_slot: TimeSlot, 
        class_ref: ClassReference
    ) -> Optional[Assignment]:
        """保護された割り当てを取得"""
        key = (time_slot.day, time_slot.period, class_ref)
        return self.protected_assignments.get(key)
    
    def protect_test_periods(self, schedule: Schedule, school: School):
        """スケジュール内のテスト期間を保護"""
        self.logger.info("テスト期間の保護を開始...")
        
        protected_count = 0
        changed_count = 0
        
        for time_slot, assignment in list(schedule.get_all_assignments()):
            if self.is_test_period(time_slot):
                protected_assignment = self.get_protected_assignment(
                    time_slot, 
                    assignment.class_ref
                )
                
                if protected_assignment:
                    # 現在の割り当てと保護された割り当てが異なる場合
                    if (assignment.subject.name != protected_assignment.subject.name or
                        (assignment.teacher and protected_assignment.teacher and 
                         assignment.teacher.name != protected_assignment.teacher.name)):
                        
                        # 保護された割り当てに戻す
                        schedule.remove_assignment(time_slot, assignment.class_ref)
                        schedule.assign(
                            time_slot,
                            assignment.class_ref,
                            protected_assignment.subject,
                            protected_assignment.teacher
                        )
                        
                        self.logger.debug(
                            f"修正: {time_slot.day}{time_slot.period}限 "
                            f"{assignment.class_ref.grade}-{assignment.class_ref.class_number} "
                            f"{assignment.subject.name} → {protected_assignment.subject.name}"
                        )
                        changed_count += 1
                    
                    protected_count += 1
        
        self.logger.info(
            f"テスト期間保護完了: "
            f"保護数={protected_count}, 修正数={changed_count}"
        )
        
        return changed_count
    
    def validate_test_periods(self, schedule: Schedule) -> List[str]:
        """テスト期間の違反をチェック"""
        violations = []
        
        for time_slot, assignment in schedule.get_all_assignments():
            if self.is_test_period(time_slot):
                protected_assignment = self.get_protected_assignment(
                    time_slot,
                    assignment.class_ref
                )
                
                if protected_assignment:
                    if (assignment.subject.name != protected_assignment.subject.name or
                        (assignment.teacher and protected_assignment.teacher and 
                         assignment.teacher.name != protected_assignment.teacher.name)):
                        
                        violations.append(
                            f"{time_slot.day}{time_slot.period}限 "
                            f"{assignment.class_ref.grade}-{assignment.class_ref.class_number}: "
                            f"{protected_assignment.subject.name}であるべきが"
                            f"{assignment.subject.name}になっている"
                        )
        
        return violations
    
    def get_test_period_info(self) -> Dict[str, any]:
        """テスト期間情報を取得"""
        return {
            'test_periods': sorted(list(self.test_periods)),
            'protected_assignments_count': len(self.protected_assignments),
            'messages': self.test_period_messages
        }