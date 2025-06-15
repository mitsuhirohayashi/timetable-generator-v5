"""Follow-up.csvから週次の制約条件を読み込むパーサー"""
import csv
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from ...domain.constraints.base import Constraint, ConstraintType, ConstraintPriority
from ...domain.constraints.teacher_absence_constraint import TeacherAbsenceConstraint
from ...domain.constraints.meeting_lock_constraint import MeetingLockConstraint
from .enhanced_followup_parser import EnhancedFollowUpParser


class FollowupConstraintParser:
    """Follow-up.csvから週次の制約条件を読み込むパーサー"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.logger = logging.getLogger(__name__)
        
        # 曜日のマッピング
        self.day_map = {
            '月曜': '月', '月曜日': '月',
            '火曜': '火', '火曜日': '火',
            '水曜': '水', '水曜日': '水',
            '木曜': '木', '木曜日': '木',
            '金曜': '金', '金曜日': '金'
        }
        
        # 時限のパターン
        self.period_patterns = {
            '終日': [1, 2, 3, 4, 5, 6],
            '午前': [1, 2, 3],
            '午後': [4, 5, 6],
            '1・2・3': [1, 2, 3],
            '4・5・6': [4, 5, 6],
            '5・6': [5, 6]
        }
    
    def parse(self) -> List[Constraint]:
        """CSVファイルから制約条件を読み込む"""
        # 拡張パーサーを使用
        enhanced_parser = EnhancedFollowUpParser(self.file_path.parent)
        result = enhanced_parser.parse_file(self.file_path.name)
        
        if result["parse_success"] and result["constraints"]:
            constraints = result["constraints"]
            self.logger.info(f"Follow-up.csvから{len(constraints)}個の制約を読み込みました")
            
            # サマリーを出力
            summary = enhanced_parser.get_summary(result)
            if summary:
                self.logger.info(f"Follow-up.csv解析結果:\n{summary}")
            
            return constraints
        else:
            # フォールバック: 従来の解析方法を使用
            self.logger.info("拡張パーサーが失敗したため、従来の方法で解析します")
            constraints = []
            
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # 教師不在制約を抽出
                    absence_constraints = self._parse_teacher_absences(content)
                    constraints.extend(absence_constraints)
                    
                    # 会議制約を抽出
                    meeting_constraints = self._parse_meetings(content)
                    constraints.extend(meeting_constraints)
            
            except Exception as e:
                self.logger.error(f"Follow-up.csvの読み込みエラー: {e}")
                raise
            
            self.logger.info(f"Follow-up.csvから{len(constraints)}個の制約を読み込みました")
            return constraints
    
    def _parse_teacher_absences(self, content: str) -> List[TeacherAbsenceConstraint]:
        """教師不在情報を抽出"""
        teacher_absences = []
        current_day = None
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 曜日の検出
            for day_text, day_code in self.day_map.items():
                if line.startswith(day_text):
                    current_day = day_code
                    break
            
            if current_day and '先生' in line:
                # 教師名と不在時間を抽出
                teacher_info = self._extract_teacher_absence(line, current_day)
                if teacher_info:
                    teacher_name, day, periods = teacher_info
                    
                    # 各時限ごとに不在情報を記録
                    for period in periods:
                        teacher_absences.append({
                            'teacher': teacher_name,
                            'day': day,
                            'period': period
                        })
        
        # 一つのTeacherAbsenceConstraintオブジェクトを作成
        if teacher_absences:
            return [TeacherAbsenceConstraint(teacher_absences)]
        else:
            return []
    
    def _extract_teacher_absence(self, line: str, day: str) -> Optional[Tuple[str, str, List[int]]]:
        """行から教師名と不在時間を抽出"""
        # 教師名のパターン（「先生」の前の文字列）
        teacher_match = re.search(r'([^\s]+)先生', line)
        if not teacher_match:
            return None
        
        teacher_name = teacher_match.group(1)
        
        # 不在時間のパターンを検索
        periods = []
        
        # 「終日」「午前」「午後」などのキーワードを検索
        for keyword, period_list in self.period_patterns.items():
            if keyword in line:
                periods.extend(period_list)
                break
        
        # 個別の時限指定（例：「5・6時間目」）
        period_match = re.findall(r'(\d)[・,、]?(\d)?[・,、]?(\d)?(?:時間目|校時)', line)
        for match in period_match:
            for p in match:
                if p:
                    periods.append(int(p))
        
        # 「1・2・3に授業を入れない」のようなパターン
        if '授業を入れない' in line:
            no_class_match = re.findall(r'(\d)[・,、]?(\d)?[・,、]?(\d)?(?:に|の)', line)
            for match in no_class_match:
                for p in match:
                    if p:
                        periods.append(int(p))
        
        if not periods:
            # デフォルトで終日とする
            periods = [1, 2, 3, 4, 5, 6]
        
        # 重複を除去してソート
        periods = sorted(list(set(periods)))
        
        return (teacher_name, day, periods)
    
    def _parse_meetings(self, content: str) -> List[MeetingLockConstraint]:
        """会議情報を抽出"""
        meetings = []
        
        # 会議パターンの検索
        meeting_patterns = [
            (r'初任研.*?(\w曜).*?(\d)[・,、]?(\d)?[・,、]?(\d)?時間目', '初任研'),
            (r'生指.*?(\w曜).*?(\d)校時', '生指'),
            (r'(\w曜).*?(\d)校時.*?生指', '生指')
        ]
        
        for pattern, meeting_name in meeting_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match[0] in ['月', '火', '水', '木', '金']:
                    day = match[0]
                else:
                    # 曜日の変換
                    for day_text, day_code in self.day_map.items():
                        if match[0] in day_text:
                            day = day_code
                            break
                    else:
                        continue
                
                # 時限を抽出
                periods = []
                for i in range(1, len(match)):
                    if match[i] and match[i].isdigit():
                        periods.append(int(match[i]))
                
                if periods:
                    constraint = MeetingLockConstraint(
                        meeting_name=meeting_name,
                        day=day,
                        period=periods[0],  # 最初の時限を使用
                        priority=ConstraintPriority.CRITICAL
                    )
                    meetings.append(constraint)
        
        return meetings