"""QA.txtからルールを読み込むローダー

ハードコードされたルールをQA.txtから動的に読み込むためのサンプル実装。
これにより、コードを変更せずにビジネスルールを更新できるようになります。
"""
import re
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path
import logging

class LoggingMixin:
    """簡易ロギングMixin（import問題回避）"""
    @property
    def logger(self):
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger


class QARulesLoader(LoggingMixin):
    """QA.txtからビジネスルールを読み込むローダー"""
    
    def __init__(self, qa_file_path: Optional[str] = None):
        super().__init__()
        self.qa_file_path = qa_file_path or str(Path(__file__).parent.parent.parent.parent / "QandA" / "QA.txt")
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict:
        """QA.txtからルールを読み込む"""
        try:
            with open(self.qa_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            rules = {
                'homeroom_teachers': self._extract_homeroom_teachers(content),
                'part_time_schedules': self._extract_part_time_schedules(content),
                'meetings': self._extract_meetings(content),
                'teacher_roles': self._extract_teacher_roles(content),
                'regular_absences': self._extract_regular_absences(content),
                'grade_6th_period_rules': self._extract_6th_period_rules(content),
                'standard_hours': self._extract_standard_hours(content),
                'subject_priorities': self._extract_subject_priorities(content),
                'grade5_preferences': self._extract_grade5_preferences(content),
                'teacher_ratios': self._extract_teacher_ratios(content),
            }
            
            self.logger.info(f"QA.txtから{len(rules)}種類のルールを読み込みました")
            return rules
            
        except Exception as e:
            self.logger.error(f"QA.txt読み込みエラー: {e}")
            return {}
    
    def _extract_homeroom_teachers(self, content: str) -> Dict[str, str]:
        """担任教師を抽出"""
        teachers = {}
        
        # 通常学級のパターン
        pattern = r'- (\d年\d組)：(.+?)先生'
        matches = re.findall(pattern, content)
        for class_name, teacher in matches:
            teachers[class_name] = teacher
        
        return teachers
    
    def _extract_part_time_schedules(self, content: str) -> Dict[str, List[Tuple[str, int]]]:
        """非常勤教師の勤務時間を抽出"""
        schedules = {}
        
        # 青井先生のセクションを探す
        aoi_section = re.search(r'青井先生（美術）：\n((?:- .+\n)+)', content)
        if aoi_section:
            aoi_slots = []
            lines = aoi_section.group(1).strip().split('\n')
            for line in lines:
                # "- 水曜：2、3、4校時" のパターン
                match = re.match(r'- (.曜)：(.+)校時', line)
                if match:
                    day = match.group(1)
                    periods = match.group(2).replace('、', ',').split(',')
                    for period in periods:
                        try:
                            aoi_slots.append((day, int(period.strip())))
                        except ValueError:
                            pass
            schedules['青井'] = aoi_slots
        
        return schedules
    
    def _extract_meetings(self, content: str) -> Dict[str, Dict]:
        """会議情報を抽出"""
        meetings = {}
        
        # 会議パターン
        meeting_patterns = [
            (r'企画会議[^：]*：\n- 時間：(.曜)(\d)限\n- 参加者：(.+)', 'enterprise'),
            (r'HF会議[^：]*：\n- 時間：(.曜)(\d)限\n- 参加者：(.+)', 'hf'),
            (r'生徒指導会議[^：]*：\n- 時間：(.曜)(\d)限\n- 参加者：(.+)', 'student_guidance'),
        ]
        
        for pattern, key in meeting_patterns:
            match = re.search(pattern, content)
            if match:
                meetings[key] = {
                    'day': match.group(1),
                    'period': int(match.group(2)),
                    'participants': [p.strip() for p in match.group(3).split('、')]
                }
        
        return meetings
    
    def _extract_teacher_roles(self, content: str) -> Dict[str, List[str]]:
        """教師の役職を抽出"""
        roles = {}
        
        # "- 青井先生：企画委員、3年主任" のパターン
        pattern = r'- (.+?)先生：(.+)'
        matches = re.findall(pattern, content)
        for teacher, role_str in matches:
            if '、' in role_str:
                roles[teacher] = [r.strip() for r in role_str.split('、')]
        
        return roles
    
    def _extract_regular_absences(self, content: str) -> Dict[str, List[str]]:
        """定期的な不在を抽出"""
        absences = {}
        
        # 毎週の終日不在セクション
        absence_section = re.search(r'毎週の終日不在[^：]*：\n((?:- .+\n)+)', content)
        if absence_section:
            lines = absence_section.group(1).strip().split('\n')
            for line in lines:
                match = re.match(r'- (.曜)：(.+)', line)
                if match:
                    day = match.group(1)
                    teachers = [t.strip().replace('先生', '') for t in match.group(2).split('、')]
                    absences[day] = teachers
        
        return absences
    
    def _extract_6th_period_rules(self, content: str) -> Dict[int, Dict[str, str]]:
        """6限目のルールを抽出"""
        rules = {}
        
        # 3年生の特別ルール
        if re.search(r'3年生.*月曜6限：通常授業可能', content):
            rules[3] = {
                '月': 'normal',
                '火': 'normal',
                '水': 'normal',
                '金': 'YT'
            }
        
        # 1・2年生のルール
        if re.search(r'1・2年生.*月曜6限：欠', content):
            for grade in [1, 2]:
                rules[grade] = {
                    '月': '欠',
                    '火': 'YT',
                    '水': 'YT',
                    '金': 'YT'
                }
        
        return rules
    
    def _extract_standard_hours(self, content: str) -> Dict[str, int]:
        """標準授業時数を抽出"""
        hours = {}
        
        # "- 国語：4時間" のパターン
        pattern = r'- (.+?)：(\d+)時間'
        matches = re.findall(pattern, content)
        for subject, hour in matches:
            hours[subject] = int(hour)
        
        return hours
    
    def _extract_subject_priorities(self, content: str) -> List[str]:
        """教科の優先順位を抽出"""
        # "1. 主要教科（算、国、理、社、英、数）を最優先" のパターン
        match = re.search(r'主要教科（(.+?)）を最優先', content)
        if match:
            subjects = match.group(1).replace('、', ',').split(',')
            return [s.strip() for s in subjects]
        return []
    
    def _extract_grade5_preferences(self, content: str) -> Dict[str, any]:
        """5組の優先設定を抽出"""
        preferences = {}
        
        # 優先教師
        if re.search(r'金子み先生を優先的に5組', content):
            preferences['preferred_teachers'] = ['金子み']
        
        # 教師比率
        ratio_match = re.search(r'理想：(.+?)先生(\d+)コマ、(.+?)先生(\d+)コマ', content)
        if ratio_match:
            preferences['teacher_ratios'] = {
                ratio_match.group(1): int(ratio_match.group(2)),
                ratio_match.group(3): int(ratio_match.group(4))
            }
        
        return preferences
    
    def _extract_teacher_ratios(self, content: str) -> Dict[str, Dict[str, float]]:
        """教師比率を抽出"""
        ratios = {}
        
        # "理想的には週全体で寺田先生と金子み先生の比率を1:1" のパターン
        if re.search(r'寺田先生と金子み先生の比率を1:1', content):
            ratios['国'] = {
                '寺田': 0.5,
                '金子み': 0.5
            }
        
        return ratios
    
    # アクセサメソッド
    def get_homeroom_teacher(self, class_name: str) -> Optional[str]:
        """クラスの担任教師を取得"""
        return self.rules.get('homeroom_teachers', {}).get(class_name)
    
    def get_part_time_slots(self, teacher_name: str) -> List[Tuple[str, int]]:
        """非常勤教師の勤務可能時間を取得"""
        return self.rules.get('part_time_schedules', {}).get(teacher_name, [])
    
    def get_meeting_info(self, meeting_name: str) -> Dict:
        """会議情報を取得"""
        return self.rules.get('meetings', {}).get(meeting_name, {})
    
    def get_teacher_roles(self, teacher_name: str) -> List[str]:
        """教師の役職を取得"""
        return self.rules.get('teacher_roles', {}).get(teacher_name, [])
    
    def get_regular_absences(self, day: str) -> List[str]:
        """特定の曜日の定期不在教師を取得"""
        return self.rules.get('regular_absences', {}).get(day, [])
    
    def get_6th_period_rule(self, grade: int, day: str) -> str:
        """6限目のルールを取得"""
        grade_rules = self.rules.get('grade_6th_period_rules', {}).get(grade, {})
        return grade_rules.get(day, '')
    
    def get_standard_hours(self, subject: str) -> int:
        """教科の標準時数を取得"""
        return self.rules.get('standard_hours', {}).get(subject, 0)
    
    def get_subject_priorities(self) -> List[str]:
        """教科の優先順位リストを取得"""
        return self.rules.get('subject_priorities', [])
    
    def get_grade5_preferred_teachers(self) -> List[str]:
        """5組の優先教師リストを取得"""
        prefs = self.rules.get('grade5_preferences', {})
        return prefs.get('preferred_teachers', [])
    
    def get_teacher_ratio(self, subject: str, teacher: str) -> float:
        """教師の担当比率を取得"""
        subject_ratios = self.rules.get('teacher_ratios', {}).get(subject, {})
        return subject_ratios.get(teacher, 0.0)


# 使用例
if __name__ == "__main__":
    loader = QARulesLoader()
    
    # 担任教師を取得
    print(f"1年1組の担任: {loader.get_homeroom_teacher('1年1組')}")
    
    # 非常勤教師の勤務時間を取得
    print(f"青井先生の勤務時間: {loader.get_part_time_slots('青井')}")
    
    # 会議情報を取得
    print(f"企画会議: {loader.get_meeting_info('enterprise')}")
    
    # 6限目のルールを取得
    print(f"3年生の月曜6限: {loader.get_6th_period_rule(3, '月')}")
    
    # 主要教科リストを取得
    print(f"主要教科: {loader.get_subject_priorities()}")