"""入力データ補正サービス

input.csvのデータを読み込み、固定科目の配置を確実にし、
Follow-up.csvからテスト期間を検出して保護する。
"""
import logging
import pandas as pd
from typing import Dict, Set, Optional, Tuple
from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...domain.value_objects.assignment import Assignment
from ...domain.interfaces.path_configuration import IPathConfiguration
from ...domain.interfaces.followup_parser import IFollowUpParser


class InputDataCorrector:
    """入力データ補正サービス
    
    入力データの不整合を修正し、固定科目やテスト期間を保護する。
    """
    
    def __init__(self, path_config: Optional[IPathConfiguration] = None,
                 followup_parser: Optional[IFollowUpParser] = None):
        self.logger = logging.getLogger(__name__)
        
        # 依存性注入
        if path_config is None:
            from ...infrastructure.di_container import get_path_configuration
            path_config = get_path_configuration()
        if followup_parser is None:
            from ...infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
            
        self.path_config = path_config
        self.followup_parser = followup_parser
    
    def correct_input_schedule(self, schedule: Schedule, school: School) -> int:
        """入力スケジュールを補正
        
        Args:
            schedule: 補正対象のスケジュール
            school: 学校情報
            
        Returns:
            補正した項目数
        """
        corrections = 0
        
        # 1. 固定科目の強制配置はスキップ - input.csvを尊重
        # corrections += self._enforce_fixed_subjects(schedule, school)
        
        # 2. テスト期間の検出と保護
        corrections += self._protect_test_periods(schedule, school)
        
        self.logger.info(f"入力データ補正完了: {corrections}項目を補正")
        return corrections
    
    def _enforce_fixed_subjects(self, schedule: Schedule, school: School) -> int:
        """固定科目を強制配置（無効化）"""
        # 強制配置は行わない - input.csvの内容を尊重
        self.logger.info("固定科目の強制配置は無効化されています")
        return 0
    
    def _protect_test_periods(self, schedule: Schedule, school: School) -> int:
        """テスト期間を検出して保護（科目は変更せず）"""
        test_periods = self._detect_test_periods()
        protected = 0
        
        for (day, period), test_info in test_periods.items():
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                # 5組はスキップ
                if class_ref.class_number == 5:
                    continue
                
                # テスト期間は変更不可としてロック（科目は保持）
                if not schedule.is_locked(time_slot, class_ref):
                    schedule.lock_cell(time_slot, class_ref)
                    protected += 1
                    
                    # 既存の割り当て情報をログ出力
                    current = schedule.get_assignment(time_slot, class_ref)
                    if current:
                        self.logger.info(
                            f"テスト期間保護: {time_slot} {class_ref} - {current.subject.name}を保持"
                        )
                    else:
                        self.logger.info(
                            f"テスト期間保護: {time_slot} {class_ref} - 空きスロット"
                        )
        
        if protected > 0:
            self.logger.info(f"{protected}個のテスト期間スロットを保護（科目変更なし）")
        
        return protected
    
    def _detect_test_periods(self) -> Dict[Tuple[str, int], str]:
        """Follow-up.csvからテスト期間を検出
        
        Returns:
            (曜日, 時限) -> テスト情報 のマッピング
        """
        test_periods = {}
        
        try:
            # Follow-up parserを使用してテスト期間を取得
            test_period_list = self.followup_parser.parse_test_periods()
            
            for test_period in test_period_list:
                if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
                    day = test_period.day
                    for period in test_period.periods:
                        test_periods[(day, period)] = getattr(test_period, 'description', 'テスト期間')
                        self.logger.debug(f"テスト期間検出: {day}曜{period}時限")
            
        except Exception as e:
            self.logger.warning(f"テスト期間検出エラー: {e}")
        
        return test_periods
    
    def validate_fixed_subjects(self, schedule: Schedule, school: School) -> list:
        """固定科目の配置を検証
        
        Returns:
            違反のリスト
        """
        from ..policies.fixed_subject_protection_policy import FixedSubjectProtectionPolicy
        
        policy = FixedSubjectProtectionPolicy()
        return policy.validate_schedule(schedule, school)