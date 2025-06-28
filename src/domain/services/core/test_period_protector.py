"""テスト期間保護サービス

テスト期間の教科を確実に保護するためのサービス
"""
import logging
from pathlib import Path
from typing import Set, Tuple
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot
from ...interfaces.followup_parser import IFollowUpParser


class TestPeriodProtector(LoggingMixin):
    """テスト期間保護サービス"""
    
    def __init__(self, followup_parser: IFollowUpParser = None):
        super().__init__()
        self.test_periods: Set[Tuple[str, int]] = set()
        
        # 依存性注入: パーサーが渡されない場合はDIコンテナから取得
        if followup_parser is None:
            from ....infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
        
        self.followup_parser = followup_parser
        self._load_test_periods()
    
    def _load_test_periods(self):
        """テスト期間情報を読み込む"""
        try:
            # パーサーを使用してテスト期間を解析
            test_periods = self.followup_parser.parse_test_periods()
            
            for test_period_info in test_periods:
                # TestPeriodオブジェクトから曜日と時限を抽出
                day = test_period_info.day
                for period in test_period_info.periods:
                    # 重複ログを防ぐため、新規追加時のみログ出力
                    if (day, period) not in self.test_periods:
                        self.logger.info(f"テスト期間追加: {day}曜{period}限")
                    self.test_periods.add((day, period))
            
            # 特別な指示からテスト期間を抽出（補完処理）
            special_instructions = self.followup_parser.get_special_instructions()
            for instruction in special_instructions:
                if "テストなので時間割の変更をしないでください" in instruction:
                    # parse_test_periods() を使用してテスト期間を取得
                    test_period_data = self.followup_parser.parse_test_periods()
                    # 各曜日のテスト期間を確認
                    for day_data in test_period_data:
                        if hasattr(day_data, 'day') and hasattr(day_data, 'periods'):
                            day = day_data.day
                            for period in day_data.periods:
                                self.test_periods.add((day, period))
            
            if self.test_periods:
                self.logger.info(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
                self.logger.debug(f"テスト期間詳細: {sorted(self.test_periods)}")
        except Exception as e:
            self.logger.error(f"テスト期間情報の読み込みに失敗: {e}")
    
    def protect_test_periods(self, schedule: Schedule, school: School) -> int:
        """スケジュール内のテスト期間を保護"""
        protected_count = 0
        
        for day, period in self.test_periods:
            time_slot = TimeSlot(day, period)
            
            # 全クラスのテスト期間スロットを保護
            for class_ref in school.get_all_classes():
                # 既存の割り当ての有無にかかわらず、セルをロックする
                if not schedule.is_locked(time_slot, class_ref):
                    schedule.lock_cell(time_slot, class_ref)
                    protected_count += 1
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    subject_name = assignment.subject.name if assignment else "空きコマ"
                    
                    self.logger.debug(
                        f"テスト期間保護: {time_slot} {class_ref} - "
                        f"内容({subject_name})を問わずロック"
                    )
        
        if protected_count > 0:
            self.logger.info(f"テスト期間として{protected_count}セルをロックしました")
        
        return protected_count
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたスロットがテスト期間かどうか判定"""
        return (time_slot.day, time_slot.period) in self.test_periods

    def check_violations(self, schedule: Schedule) -> list:
        """テスト期間の制約違反をチェック"""
        violations = []
        
        for day, period in self.test_periods:
            time_slot = TimeSlot(day, period)
            
            for class_ref in schedule.get_all_class_refs():
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                # テスト期間中に「行」以外の科目が割り当てられている場合
                if assignment and assignment.subject.name != "行":
                    violations.append({
                        "type": "TestPeriodViolation",
                        "time_slot": time_slot,
                        "class_ref": class_ref,
                        "subject": assignment.subject.name,
                        "message": f"テスト期間({time_slot})に'{assignment.subject.name}'が割り当てられています"
                    })
        
        return violations