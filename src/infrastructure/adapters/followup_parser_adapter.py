"""フォローアップ情報のパーサーアダプター"""

from typing import List, Dict, Any
from datetime import date
from pathlib import Path
import logging

from ...domain.interfaces.followup_parser import IFollowUpParser, TestPeriodInfo
from ...domain.value_objects import TimeSlot
from ..parsers.enhanced_followup_parser import EnhancedFollowUpParser
from ..parsers.natural_followup_parser import NaturalFollowUpParser


class FollowUpParserAdapter(IFollowUpParser):
    """既存のFollowUpパーサーをIFollowUpParserに適合させるアダプター"""
    
    def __init__(self, followup_file_path: Path = None):
        self.logger = logging.getLogger(__name__)
        
        # ファイルパスの設定
        if followup_file_path:
            self._file_path = followup_file_path
        else:
            from ..config.path_config import path_config
            self._file_path = path_config.followup_csv
        
        # パーサーの初期化
        self._enhanced_parser = EnhancedFollowUpParser(self._file_path.parent)
        self._natural_parser = NaturalFollowUpParser(self._file_path.parent)
    
    def parse_teacher_absences(self) -> Dict[str, List[TimeSlot]]:
        """教師の不在情報を解析"""
        # Enhancedパーサーからfollow-up情報を解析
        parsed_result = self._enhanced_parser.parse_file(str(self._file_path.name))
        
        # teacher_absencesを取得
        teacher_absence_list = parsed_result.get('teacher_absences', [])
        
        # 返却形式を変換
        teacher_absences = {}
        
        for absence in teacher_absence_list:
            teacher_name = absence.teacher_name if hasattr(absence, 'teacher_name') else str(absence)
            day = absence.day if hasattr(absence, 'day') else None
            periods = absence.periods if hasattr(absence, 'periods') else []
            
            if teacher_name and day:
                if teacher_name not in teacher_absences:
                    teacher_absences[teacher_name] = []
                
                # 時限が指定されている場合
                if periods:
                    for period in periods:
                        teacher_absences[teacher_name].append(TimeSlot(day, period))
                else:
                    # 終日不在の場合
                    for period in range(1, 7):
                        teacher_absences[teacher_name].append(TimeSlot(day, period))
        
        return teacher_absences
    
    def parse_test_periods(self) -> List[TestPeriodInfo]:
        """テスト期間情報を解析"""
        # Naturalパーサーを使用してテスト期間を解析
        parsed_result = self._natural_parser.parse_file(str(self._file_path.name))
        
        # test_periodsを取得
        test_periods = parsed_result.get('test_periods', [])
        
        # TestPeriodオブジェクトをそのまま返す（day, periods属性を持つ）
        # NaturalFollowUpParser.TestPeriodオブジェクトは既にday/periods属性を持っているため
        # 変換は不要
        return test_periods
    
    def parse_meeting_changes(self) -> Dict[str, Dict[str, Any]]:
        """会議時間の変更情報を解析"""
        # 現在の実装では明示的な会議変更解析はないため、空の辞書を返す
        # 将来的にはFollow-up.csvから会議変更情報を抽出
        return {}
    
    def is_test_period(self, target_date: date) -> bool:
        """指定された日付がテスト期間かどうかを判定"""
        return self._enhanced_parser.is_test_period(target_date)
    
    def get_special_instructions(self) -> List[str]:
        """特別な指示やコメントを取得"""
        # Naturalパーサーを使用して解析
        parsed_info = self._natural_parser.parse_file(str(self._file_path.name))
        
        instructions = []
        
        # テスト期間の指示
        for period in parsed_info.get('test_periods', []):
            if hasattr(period, 'description'):
                instructions.append(period.description)
            else:
                instructions.append(str(period))
        
        # 特別要望
        for req in parsed_info.get('special_requests', []):
            if hasattr(req, 'description'):
                instructions.append(req.description)
        
        return instructions
    
    def reload(self) -> None:
        """Follow-up情報を再読み込み"""
        self._enhanced_parser = EnhancedFollowUpParser(self._file_path.parent)
        self._natural_parser = NaturalFollowUpParser(self._file_path.parent)