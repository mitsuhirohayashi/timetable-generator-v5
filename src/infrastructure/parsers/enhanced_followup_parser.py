"""拡張Follow-up.csv解析パーサー - テスト期間保護を含む自然言語処理"""
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime

from ...domain.constraints.base import Constraint, ConstraintType, ConstraintPriority
from ...domain.constraints.teacher_absence_constraint import TeacherAbsenceConstraint
from ...domain.constraints.meeting_lock_constraint import MeetingLockConstraint
# from ...domain.constraints.test_period_exclusion import TestPeriodProtectionConstraint
from ...domain.value_objects.time_slot import TimeSlot


@dataclass
class TeacherAbsence:
    """教員不在情報"""
    teacher_name: str
    day: str
    periods: List[int]  # 空リストは終日
    reason: str


@dataclass
class TestPeriod:
    """テスト期間情報"""
    day: str
    periods: List[int]
    description: str
    affected_classes: Optional[List[str]] = None  # Noneは全クラス（5組を除く）


@dataclass
class MeetingSchedule:
    """会議スケジュール情報"""
    meeting_name: str  # 企画、生指、特会など
    day: str
    period: int
    participating_teachers: Optional[List[str]] = None


@dataclass
class ProtectedSlot:
    """保護されたスロット情報"""
    day: str
    period: int
    reason: str
    affected_classes: Optional[List[str]] = None


class EnhancedFollowUpParser:
    """拡張版Follow-up.csv解析パーサー"""
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        self.current_day = None
        
        # 解析結果を格納
        self.teacher_absences = []
        self.test_periods = []
        self.meetings = []
        self.protected_slots = []
        
        # 曜日マッピング
        self.day_map = {
            '月曜': '月', '月曜日': '月',
            '火曜': '火', '火曜日': '火',
            '水曜': '水', '水曜日': '水',
            '木曜': '木', '木曜日': '木',
            '金曜': '金', '金曜日': '金'
        }
        
    def parse_file(self, filename: str = "Follow-up.csv") -> Dict:
        """Follow-up.csvから情報を解析（制約オブジェクトも生成）"""
        file_path = self.base_path / filename
        
        if not file_path.exists():
            self.logger.warning(f"Follow-up file not found: {file_path}")
            return self._create_empty_result()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析実行
            self._parse_content(content)
            
            # 制約オブジェクトを生成
            constraints = self._generate_constraints()
            
            return self._create_result(constraints)
            
        except Exception as e:
            self.logger.error(f"Follow-up解析エラー: {e}")
            return self._create_empty_result()
    
    def _parse_content(self, content: str):
        """コンテンツを解析"""
        # CSVの場合は最初のカラムだけを取得
        lines = []
        for line in content.split('\n'):
            if ',' in line:
                # CSV形式の場合、最初のカラムを取得
                first_col = line.split(',')[0].strip()
                if first_col and not first_col.startswith('#'):
                    lines.append(first_col)
            else:
                # 通常の行
                if line.strip() and not line.strip().startswith('#'):
                    lines.append(line.strip())
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 曜日の判定
            day_match = re.match(r'^(月|火|水|木|金)曜日?[：:]?', line)
            if day_match:
                self.current_day = day_match.group(1)
                continue
            
            # 各種パターンの解析
            if self.current_day:
                # テスト期間の検出
                if self._parse_test_period(line):
                    continue
                
                # 教員不在の検出
                if self._parse_teacher_absence(line):
                    continue
                
                # 会議の検出
                if self._parse_meeting(line):
                    continue
    
    def _parse_test_period(self, line: str) -> bool:
        """テスト期間の指示を解析"""
        # テスト期間のパターン
        test_patterns = [
            r'(\d+)[・,、]?(\d+)?[・,、]?(\d+)?校?時.*?テストなので時間割の変更をしないでください',
            r'テストなので.*?(\d+)[・,、]?(\d+)?[・,、]?(\d+)?校?時.*?時間割の変更をしない',
            r'(\d+)[・,、]?(\d+)?[・,、]?(\d+)?校?時.*?はテスト',
            r'テスト実施.*?(\d+)[・,、]?(\d+)?[・,、]?(\d+)?校?時'
        ]
        
        for pattern in test_patterns:
            match = re.search(pattern, line)
            if match:
                periods = []
                for i in range(1, 4):
                    if match.group(i):
                        periods.append(int(match.group(i)))
                
                if periods:
                    self.test_periods.append(TestPeriod(
                        day=self.current_day,
                        periods=periods,
                        description=line,
                        affected_classes=None  # 全クラス（5組を除く）
                    ))
                    self.logger.info(
                        f"テスト期間を検出: {self.current_day}曜日 {periods}時限 - {line}"
                    )
                    return True
        
        return False
    
    def _parse_teacher_absence(self, line: str) -> bool:
        """教員不在情報を解析"""
        if '先生' not in line or '不在' not in line:
            return False
        
        # 教員名の抽出
        teachers = re.findall(r'(\S+?)先生', line)
        if not teachers:
            return False
        
        # 時間帯の抽出
        periods = self._extract_periods(line)
        
        # 理由の抽出
        reason = self._extract_absence_reason(line)
        
        # 各教員の不在情報を記録
        for teacher in teachers:
            normalized_teacher = teacher.replace("先生", "").strip()
            self.teacher_absences.append(TeacherAbsence(
                teacher_name=normalized_teacher,
                day=self.current_day,
                periods=periods.copy(),
                reason=reason
            ))
            self.logger.debug(
                f"教員不在を検出: {normalized_teacher}先生 - {self.current_day}曜日 "
                f"{periods if periods else '終日'} ({reason})"
            )
        
        return True
    
    def _parse_meeting(self, line: str) -> bool:
        """会議情報を解析"""
        meeting_patterns = [
            (r'(企画|生活指導|生指|特別活動会議|特会|HF会議|HF).*?(\d+)時間?目', None),
            (r'(\d+)時間?目.*?(企画|生活指導|生指|特別活動会議|特会|HF会議|HF)', 1),
        ]
        
        for pattern, name_group in meeting_patterns:
            match = re.search(pattern, line)
            if match:
                if name_group is None:
                    meeting_name = self._normalize_meeting_name(match.group(1))
                    period = int(match.group(2))
                else:
                    period = int(match.group(1))
                    meeting_name = self._normalize_meeting_name(match.group(2))
                
                self.meetings.append(MeetingSchedule(
                    meeting_name=meeting_name,
                    day=self.current_day,
                    period=period,
                    participating_teachers=None
                ))
                self.logger.debug(
                    f"会議を検出: {meeting_name} - {self.current_day}曜日{period}時限"
                )
                return True
        
        return False
    
    def _extract_periods(self, line: str) -> List[int]:
        """時限情報を抽出"""
        periods = []
        
        # 特定キーワードでの時限指定
        if "終日" in line or "1日" in line:
            return list(range(1, 7))
        elif "午前" in line:
            return [1, 2, 3]
        elif "午後" in line:
            return [4, 5, 6]
        
        # 数字での時限指定
        period_match = re.findall(r'(\d+)[・,、]?(?:(\d+)[・,、]?)?(?:(\d+)[・,、]?)?時間?目', line)
        for match in period_match:
            for p in match:
                if p:
                    periods.append(int(p))
        
        # 重複を除去してソート
        return sorted(list(set(periods)))
    
    def _extract_absence_reason(self, line: str) -> str:
        """不在理由を抽出"""
        reason_patterns = [
            r'(年休|振替?休暇?|外勤|出張|会議|研修)',
            r'(.+?)のため',
            r'(.+?)で不在'
        ]
        
        for pattern in reason_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
        
        return "不在"
    
    def _normalize_meeting_name(self, name: str) -> str:
        """会議名を正規化"""
        meeting_map = {
            '企画': '企画',
            '生活指導': '生指',
            '生指': '生指',
            '特別活動会議': '特会',
            '特会': '特会',
            'HF会議': 'HF',
            'HF': 'HF'
        }
        return meeting_map.get(name, name)
    
    def _generate_constraints(self) -> List[Constraint]:
        """解析結果から制約オブジェクトを生成"""
        constraints = []
        
        # テスト期間制約
        if self.test_periods:
            test_slots = []
            for test_period in self.test_periods:
                for period in test_period.periods:
                    time_slot = TimeSlot(test_period.day, period)
                    test_slots.append((time_slot, test_period.description))
            
            if test_slots:
                # テスト期間保護制約を追加
                # NOTE: テスト期間保護はFollowUpProcessorで処理されるため、ここではスキップ
                # constraints.append(TestPeriodProtectionConstraint(test_slots))
                self.logger.info(f"テスト期間を検出: {len(test_slots)}スロット（FollowUpProcessorで処理）")
        
        # 教員不在制約
        if self.teacher_absences:
            absence_list = []
            for absence in self.teacher_absences:
                for period in absence.periods if absence.periods else range(1, 7):
                    absence_list.append({
                        'teacher': absence.teacher_name,
                        'day': absence.day,
                        'period': period
                    })
            
            if absence_list:
                constraints.append(TeacherAbsenceConstraint(absence_list))
                self.logger.info(f"教員不在制約を生成: {len(absence_list)}件")
        
        # 会議制約
        # MeetingLockConstraintは会議情報を内部で管理するため、
        # 個別の会議情報を渡すことはできない
        # 代わりに、会議情報は別途管理する必要がある
        if self.meetings:
            # 会議制約は1つだけ追加（内部で全会議を管理）
            constraints.append(MeetingLockConstraint())
        
        if self.meetings:
            self.logger.info(f"会議制約を生成: {len(self.meetings)}件")
        
        return constraints
    
    def _create_result(self, constraints: List[Constraint]) -> Dict:
        """解析結果をまとめて返す"""
        return {
            "teacher_absences": self.teacher_absences,
            "test_periods": self.test_periods,
            "meetings": self.meetings,
            "protected_slots": self.protected_slots,
            "constraints": constraints,
            "parse_success": True
        }
    
    def _create_empty_result(self) -> Dict:
        """空の結果を返す"""
        return {
            "teacher_absences": [],
            "test_periods": [],
            "meetings": [],
            "protected_slots": [],
            "constraints": [],
            "parse_success": False
        }
    
    def get_summary(self, result: Dict) -> str:
        """解析結果のサマリーを生成"""
        lines = []
        
        # テスト期間
        if result["test_periods"]:
            lines.append("【テスト期間】")
            for test in result["test_periods"]:
                periods_str = ','.join(map(str, test.periods))
                lines.append(f"  - {test.day}曜{periods_str}時限: {test.description}")
        
        # 教員不在
        if result["teacher_absences"]:
            lines.append("\n【教員不在】")
            for absence in result["teacher_absences"]:
                periods_str = "終日" if not absence.periods else f"{','.join(map(str, absence.periods))}時限"
                lines.append(f"  - {absence.teacher_name}: {absence.day}曜{periods_str} ({absence.reason})")
        
        # 会議
        if result["meetings"]:
            lines.append("\n【会議】")
            for meeting in result["meetings"]:
                lines.append(f"  - {meeting.day}曜{meeting.period}時限: {meeting.meeting_name}")
        
        # 制約数
        if result["constraints"]:
            lines.append(f"\n【生成された制約】")
            lines.append(f"  - 合計: {len(result['constraints'])}件")
        
        return '\n'.join(lines)