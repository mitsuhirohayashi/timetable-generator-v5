"""Follow-up指示を処理してスケジュールに適用するサービス"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, Subject
from ..value_objects.assignment import Assignment
from ...infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser, TestPeriod


class FollowUpProcessor:
    """Follow-up指示をスケジュールに適用するプロセッサー"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.test_periods: List[TestPeriod] = []
        self.protected_slots: Set[Tuple[str, int, str]] = set()  # (day, period, class_ref)
    
    def process_followup_file(self, file_path: Path) -> Dict:
        """Follow-upファイルを処理"""
        parser = EnhancedFollowUpParser(file_path.parent)
        result = parser.parse_file(file_path.name)
        
        if result["parse_success"]:
            self.test_periods = result.get("test_periods", [])
            self._build_protected_slots()
            
            summary = parser.get_summary(result)
            if summary:
                self.logger.info(f"Follow-up処理結果:\n{summary}")
        
        return result
    
    def _build_protected_slots(self):
        """保護スロットのセットを構築"""
        self.protected_slots.clear()
        
        # テスト期間のスロットを追加
        for test_period in self.test_periods:
            for period in test_period.periods:
                # 5組以外の全クラスを保護
                for grade in range(1, 4):
                    for class_num in range(1, 8):
                        if class_num != 5:  # 5組は除外
                            class_ref = f"{grade}-{class_num}"
                            self.protected_slots.add((test_period.day, period, class_ref))
                            self.logger.debug(
                                f"テスト期間保護: {test_period.day}{period} {class_ref}"
                            )
    
    def protect_test_periods_in_schedule(self, schedule: Schedule, school: School) -> int:
        """テスト期間をスケジュールで保護（科目は変更せず）"""
        protected_count = 0
        
        for test_period in self.test_periods:
            for period in test_period.periods:
                time_slot = TimeSlot(test_period.day, period)
                
                # 5組以外の全クラスを保護
                for class_ref in school.get_all_classes():
                    if class_ref.class_number == 5:  # 5組はスキップ
                        continue
                    
                    # 既存の割り当てを確認
                    existing = schedule.get_assignment(time_slot, class_ref)
                    if existing:
                        # 既存の科目を保持したままロック
                        if not schedule.is_locked(time_slot, class_ref):
                            schedule.lock_cell(time_slot, class_ref)
                            protected_count += 1
                            self.logger.debug(
                                f"テスト期間保護: {time_slot} {class_ref} - {existing.subject.name}を保持"
                            )
                    else:
                        # 割り当てがない場合もロック（後で割り当てられた際に保護される）
                        schedule.lock_cell(time_slot, class_ref)
                        protected_count += 1
                        self.logger.debug(
                            f"テスト期間保護: {time_slot} {class_ref} - 空きスロット"
                        )
        
        if protected_count > 0:
            self.logger.info(f"テスト期間を{protected_count}スロットで保護しました（科目は変更なし）")
        
        return protected_count
    
    def is_protected_slot(self, day: str, period: int, class_ref: str) -> bool:
        """指定されたスロットが保護されているかチェック"""
        return (day, period, class_ref) in self.protected_slots
    
    def get_test_period_info(self, day: str, period: int) -> Optional[TestPeriod]:
        """指定された時間のテスト期間情報を取得"""
        for test_period in self.test_periods:
            if test_period.day == day and period in test_period.periods:
                return test_period
        return None
    
    def _parse_class_ref(self, class_ref: str) -> Tuple[int, int]:
        """クラス参照を解析してグレードとクラス番号を返す"""
        parts = class_ref.split('-')
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                pass
        return 0, 0
    
    def mark_schedule_as_protected(self, schedule: Schedule) -> None:
        """スケジュール内の保護スロットをマーク"""
        for day, period, class_ref in self.protected_slots:
            time_slot = TimeSlot(day, period)
            
            # 保護スロットをロック（科目に関わらず）
            if not schedule.is_locked(time_slot, class_ref):
                schedule.lock_cell(time_slot, class_ref)
                assignment = schedule.get_assignment(time_slot, class_ref)
                subject_name = assignment.subject.name if assignment else "空き"
                self.logger.debug(
                    f"テストスロットをロック: {time_slot} {class_ref} - {subject_name}"
                )