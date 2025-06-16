"""自然言語形式のFollow-up.csv解析パーサー"""
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TeacherAbsence:
    """教員不在情報"""
    teacher_name: str
    day: str
    periods: List[int]  # 空リストは終日
    reason: str


@dataclass
class FixedSchedule:
    """固定スケジュール情報"""
    subject: str
    day: str
    period: int
    class_refs: List[str] = None  # Noneは全クラス


@dataclass
class MeetingSchedule:
    """会議スケジュール情報"""
    meeting_name: str  # 企画、生指、特会など
    day: str
    period: int
    participating_teachers: List[str] = None  # 参加教員リスト（Noneは不明）


@dataclass
class TestPeriod:
    """テスト期間情報"""
    day: str
    periods: List[int]


@dataclass
class SpecialRequest:
    """特別要望"""
    description: str
    request_type: str  # "分散", "重複回避", "代替配置", "まとめて実施"等
    details: Dict[str, any]


class NaturalFollowUpParser:
    """自然言語形式のFollow-up.csvファイルの解析を担当"""
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        self.current_day = None
        self.absences = []
        self.fixed_schedules = []
        self.special_requests = []
        self.meetings = []
        self.test_periods = []
        
    def parse_file(self, filename: str = "Follow-up.csv") -> Dict:
        """Follow-up.csvから情報を解析"""
        file_path = self.base_path / filename
        
        if not file_path.exists():
            self.logger.warning(f"Follow-up file not found: {file_path}")
            return self._create_empty_result()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
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
            
            section = "weekly"  # weekly, special, permanent
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # セクション判定
                if "今週のみの特別対応" in line or "今週のみ" in line:
                    section = "special"
                    continue
                elif "恒久的な要望" in line or "毎週適用" in line:
                    section = "permanent"
                    continue
                elif "その他" in line:
                    section = "special"  # その他セクションを特別対応として扱う
                    continue
                
                # 曜日の判定
                day_match = re.match(r'^(月|火|水|木|金)曜日[:：]?', line)
                if day_match:
                    self.current_day = day_match.group(1)
                    continue
                
                # 項目の解析（- で始まる行、または教員名や活動で始まる行）
                if line.startswith('- ') or line.startswith('・'):
                    content = line[2:].strip()
                    
                    if section == "weekly":
                        self._parse_weekly_item(content)
                    elif section == "special":
                        self._parse_special_item(content)
                    elif section == "permanent":
                        self._parse_permanent_item(content)
                        
                elif ('先生' in line or '実施' in line or '不在' in line or 'テスト' in line) and self.current_day:
                    content = line
                    
                    if section == "weekly":
                        self._parse_weekly_item(content)
                    elif section == "special":
                        self._parse_special_item(content)
                    elif section == "permanent":
                        self._parse_permanent_item(content)
                
                # 特別対応・恒久要望セクションの一般的な内容
                elif section in ["special", "permanent"] and line:
                    if section == "special":
                        self._parse_special_item(line)
                    elif section == "permanent":
                        self._parse_permanent_item(line)
                
                # サブセクション（##で始まる行）
                elif line.startswith('##'):
                    # 恒久的要望のサブセクション名を記録
                    pass
            
            return self._create_result()
            
        except Exception as e:
            self.logger.error(f"Follow-up解析エラー: {e}")
            return self._create_empty_result()
    
    def _parse_weekly_item(self, content: str):
        """週次項目の解析"""
        if not self.current_day:
            return
        
        # 初任者研修の特別処理
        if "初任者研修" in content or "初研" in content:
            self._handle_beginner_training(content, self.current_day)
            return
        
        # テスト期間の検出
        test_pattern = r'([０-９0-9]+)[・・、]?([０-９0-9]+)?[・・、]?([０-９0-9]+)?校?時.*テスト.*変更.*しない'
        test_match = re.search(test_pattern, content)
        if test_match:
            periods = []
            for i in range(1, 4):
                if test_match.group(i):
                    # 全角数字を半角に変換
                    num_str = test_match.group(i).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                    periods.append(int(num_str))
            if periods:
                self.test_periods.append(TestPeriod(
                    day=self.current_day,
                    periods=periods
                ))
                self.logger.info(f"テスト期間を検出: {self.current_day} {periods}校時")
            return
        
        # 教員不在パターン
        absence_patterns = [
            r'(.+?先生)は?(.+?)不在',
            r'(.+?先生)は?(.+?)で(終日)?不在',
            r'(.+?先生)、?(.+?先生)は?(.+?)不在',
            r'(.+?先生)(.+?)で?1日休み',
            r'(.+?先生)(.+?)休み'
        ]
        
        for pattern in absence_patterns:
            match = re.search(pattern, content)
            if match:
                self._extract_teacher_absences(content, self.current_day)
                return
        
        # 会議パターン（企画、生指、特会など）
        meeting_patterns = [
            r'(企画|生活指導|生指|特別活動会議|特会|HF会議|HF)は?(\d+)時間?目に実施',
            r'(\d+)時間?目[：:](企画|生活指導|生指|特別活動会議|特会|HF会議|HF)を?実施'
        ]
        
        for pattern in meeting_patterns:
            match = re.search(pattern, content)
            if match:
                self._extract_meeting_schedule(content, self.current_day)
                return
        
        # 固定スケジュールパターン
        fixed_patterns = [
            r'(.+?)は?(\d+)時間?目に実施',
            r'(\d+)時間?目[：:](.+?)を?実施',
            r'(.+?)\((\d+)時間?目\)は?時間変更しない'
        ]
        
        for pattern in fixed_patterns:
            match = re.search(pattern, content)
            if match:
                self._extract_fixed_schedule(content, self.current_day)
                return
        
        # 会議として「企画」「生指」なども検出
        if "企画" in content and "実施" in content:
            self._extract_meeting_schedule(content, self.current_day)
            return
    
    def _parse_special_item(self, content: str):
        """特別対応項目の解析"""
        self.logger.debug(f"特別対応項目を解析: {content}")
        
        # 例：水曜日の特別活動会議（特会）は校長先生が火曜・水曜不在のため別の曜日に移動
        if "移動" in content or "変更" in content:
            self.special_requests.append(SpecialRequest(
                description=content,
                request_type="reschedule",
                details={"content": content}
            ))
        
        # 空欄を全て埋める指示
        elif "空白" in content and "埋め" in content:
            self.logger.info(f"空欄埋め指示を検出: {content}")
            self.special_requests.append(SpecialRequest(
                description=content,
                request_type="fill_all_empty",
                details={"force_fill": True, "allow_overtime": True}
            ))
        
        # 教員不足時の調整指示
        elif "教員" in content and "調整" in content:
            self.special_requests.append(SpecialRequest(
                description=content,
                request_type="teacher_adjustment",
                details={"priority": "日内移動優先", "content": content}
            ))
    
    def _parse_permanent_item(self, content: str):
        """恒久的要望の解析"""
        # 分散配置
        if "異なる時間帯" in content or "分散" in content:
            self.special_requests.append(SpecialRequest(
                description=content,
                request_type="分散",
                details=self._extract_dispersion_details(content)
            ))
        
        # 重複回避
        elif "重ならない" in content:
            self.special_requests.append(SpecialRequest(
                description=content,
                request_type="重複回避",
                details=self._extract_avoidance_details(content)
            ))
        
        # まとめて実施
        elif "まとめて" in content:
            self.special_requests.append(SpecialRequest(
                description=content,
                request_type="まとめて実施",
                details=self._extract_grouping_details(content)
            ))
        
        # 代替配置
        elif "空ける" in content and "場合" in content:
            self.special_requests.append(SpecialRequest(
                description=content,
                request_type="代替配置",
                details=self._extract_substitution_details(content)
            ))
    
    def _extract_teacher_absences(self, content: str, day: str):
        """教員不在情報の抽出"""
        # 複数の先生が含まれる場合の処理
        teachers = re.findall(r'(\S+?先生)', content)
        
        # 時間帯の抽出
        periods = []
        period_match = re.search(r'(\d+)[・,、]?(\d+)?[・,、]?(\d+)?時間?目', content)
        if period_match:
            for i in range(1, 4):
                if period_match.group(i):
                    periods.append(int(period_match.group(i)))
        
        # 午後不在の処理
        if "午後" in content and "不在" in content:
            periods = [4, 5, 6]
        
        # 理由の抽出
        reason = "不在"
        reason_patterns = [
            r'(年休|振替?休暇?|外勤|出張|会議)',
            r'(.+?)のため'
        ]
        for pattern in reason_patterns:
            match = re.search(pattern, content)
            if match:
                reason = match.group(1)
                break
        
        # 各教員の不在情報を記録
        for teacher in teachers:
            # 教員名から「先生」を削除
            normalized_teacher = teacher.replace("先生", "").strip()
            self.absences.append(TeacherAbsence(
                teacher_name=normalized_teacher,
                day=day,
                periods=periods.copy(),
                reason=reason
            ))
    
    def _extract_fixed_schedule(self, content: str, day: str):
        """固定スケジュール情報の抽出"""
        # 時間の抽出
        period_match = re.search(r'(\d+)時間?目', content)
        if not period_match:
            return
        
        period = int(period_match.group(1))
        
        # 教科・活動名の抽出
        subject = None
        subject_patterns = [
            r'([^（\(]+?)[は\(（]?\d+時間?目',
            r'\d+時間?目[：:](.+?)を?実施',
            r'(.+?)は?\d+時間?目に実施'
        ]
        
        for pattern in subject_patterns:
            match = re.search(pattern, content)
            if match:
                subject = match.group(1).strip()
                break
        
        if subject:
            # クラス指定があるかチェック
            class_match = re.search(r'(\d+組)', content)
            class_refs = [class_match.group(1)] if class_match else None
            
            self.fixed_schedules.append(FixedSchedule(
                subject=subject,
                day=day,
                period=period,
                class_refs=class_refs
            ))
    
    def _extract_dispersion_details(self, content: str) -> Dict:
        """分散配置の詳細抽出"""
        details = {"type": "dispersion"}
        
        # クラスの抽出
        class_pattern = r'(\d+年\d+組)'
        classes = re.findall(class_pattern, content)
        if classes:
            details["classes"] = classes
        
        # 教科の抽出（自立など）
        if "自立" in content:
            details["subject"] = "自立"
        
        return details
    
    def _extract_avoidance_details(self, content: str) -> Dict:
        """重複回避の詳細抽出"""
        details = {"type": "avoidance"}
        
        # 対象の抽出
        items = re.findall(r'「(.+?)」', content)
        if not items:
            items = re.findall(r'(.+?)と(.+?)が', content)
            if items and isinstance(items[0], tuple):
                items = list(items[0])
        
        if items:
            details["items"] = items
        
        return details
    
    def _extract_grouping_details(self, content: str) -> Dict:
        """まとめて実施の詳細抽出"""
        details = {"type": "grouping"}
        
        # 曜日
        day_match = re.search(r'(月|火|水|木|金)曜', content)
        if day_match:
            details["day"] = day_match.group(1)
        
        # 教員
        teacher_match = re.search(r'(\S+?先生)', content)
        if teacher_match:
            details["teacher"] = teacher_match.group(1)
        
        # クラス
        classes = re.findall(r'(\d+年?\d+組)', content)
        if classes:
            details["classes"] = classes
        
        # 教科
        if "英語" in content:
            details["subject"] = "英"
        
        # 補助教員
        if "空ける" in content:
            support_match = re.search(r'(\S+?先生)を?空ける', content)
            if support_match:
                details["support_teacher"] = support_match.group(1)
        
        return details
    
    def _extract_substitution_details(self, content: str) -> Dict:
        """代替配置の詳細抽出"""
        details = {"type": "substitution"}
        
        # 条件となる教員
        if_match = re.search(r'(\S+?先生)が?(.+?)不在', content)
        if if_match:
            details["if_teacher_absent"] = if_match.group(1)
            
            # 時間
            period_match = re.search(r'(\d+)時間?目', if_match.group(2))
            if period_match:
                details["if_period"] = int(period_match.group(1))
        
        # 代替教員
        then_match = re.search(r'(\S+?先生)を?(.+?)空ける', content)
        if then_match:
            details["then_teacher_free"] = then_match.group(1)
            
            # 時間
            period_match = re.search(r'(\d+)時間?目', then_match.group(2))
            if period_match:
                details["then_period"] = int(period_match.group(1))
        
        return details
    
    def _handle_beginner_training(self, content: str, day: str):
        """初任者研修の特別処理"""
        # 時間帯の抽出
        periods = []
        period_patterns = [
            r'(\d+)[・,、]?(\d+)?[・,、]?(\d+)?時間?目',
            r'(\d+)・(\d+)・(\d+)時間?目'
        ]
        
        for pattern in period_patterns:
            match = re.search(pattern, content)
            if match:
                for i in range(1, 4):
                    if match.group(i):
                        periods.append(int(match.group(i)))
                break
        
        if not periods:
            # デフォルトで1,2,4時間目を使用
            periods = [1, 2, 4]
        
        # 警告メッセージを出力
        self.logger.warning(
            f"初任者研修を検出しました（{day}曜日 {','.join(map(str, periods))}時間目）。"
            "初任者教員の名前が特定できないため、手動で該当教員の不在情報を追加してください。"
        )
        
        # 特別要望として記録
        self.special_requests.append(SpecialRequest(
            description=f"初任者研修（{day}曜日 {','.join(map(str, periods))}時間目）- 初任者教員を特定できません",
            request_type="beginner_training",
            details={
                "day": day,
                "periods": periods,
                "warning": "初任者教員の名前を手動で確認し、該当教員の不在情報を追加してください"
            }
        ))
    
    def _extract_meeting_schedule(self, content: str, day: str):
        """会議スケジュール情報の抽出"""
        # 時間の抽出
        period_match = re.search(r'(\d+)時間?目', content)
        if not period_match:
            return
        
        period = int(period_match.group(1))
        
        # 会議名の抽出
        meeting_name = None
        meeting_patterns = [
            (r'(企画)は?\d+時間?目に実施', '企画'),
            (r'\d+時間?目[：:](企画)を?実施', '企画'),
            (r'(生活指導|生指)は?\d+時間?目に実施', '生指'),
            (r'\d+時間?目[：:](生活指導|生指)を?実施', '生指'),
            (r'(特別活動会議|特会)は?\d+時間?目に実施', '特会'),
            (r'\d+時間?目[：:](特別活動会議|特会)を?実施', '特会'),
            (r'(HF会議|HF)は?\d+時間?目に実施', 'HF'),
            (r'\d+時間?目[：:](HF会議|HF)を?実施', 'HF')
        ]
        
        for pattern, name in meeting_patterns:
            if re.search(pattern, content):
                meeting_name = name
                break
        
        if meeting_name:
            self.meetings.append(MeetingSchedule(
                meeting_name=meeting_name,
                day=day,
                period=period,
                participating_teachers=None  # 会議メンバーは別ファイルから読み込む
            ))
    
    def _create_result(self) -> Dict:
        """解析結果をまとめて返す"""
        return {
            "teacher_absences": self.absences,
            "fixed_schedules": self.fixed_schedules,
            "special_requests": self.special_requests,
            "meetings": self.meetings,
            "test_periods": self.test_periods,
            "parse_success": True
        }
    
    def _create_empty_result(self) -> Dict:
        """空の結果を返す"""
        return {
            "teacher_absences": [],
            "fixed_schedules": [],
            "special_requests": [],
            "meetings": [],
            "test_periods": [],
            "parse_success": False
        }
    
    def get_summary(self, result: Dict) -> str:
        """解析結果のサマリーを生成"""
        lines = []
        
        # 教員不在
        if result["teacher_absences"]:
            lines.append("【教員不在】")
            for absence in result["teacher_absences"]:
                periods_str = "終日" if not absence.periods else f"{','.join(map(str, absence.periods))}時間目"
                lines.append(f"  - {absence.teacher_name}: {absence.day}曜{periods_str} ({absence.reason})")
        
        # 固定スケジュール
        if result["fixed_schedules"]:
            lines.append("\n【固定スケジュール】")
            for fixed in result["fixed_schedules"]:
                class_str = "全クラス" if not fixed.class_refs else ','.join(fixed.class_refs)
                lines.append(f"  - {fixed.day}曜{fixed.period}時間目: {fixed.subject} ({class_str})")
        
        # 会議
        if result.get("meetings"):
            lines.append("\n【会議】")
            for meeting in result["meetings"]:
                lines.append(f"  - {meeting.day}曜{meeting.period}時間目: {meeting.meeting_name}")
        
        # 特別要望
        if result["special_requests"]:
            lines.append("\n【特別要望】")
            for req in result["special_requests"]:
                lines.append(f"  - [{req.request_type}] {req.description}")
        
    def _normalize_teacher_name(self, teacher_name: str) -> str:
        """教員名を正規化（「先生」を削除）"""
        return teacher_name.replace("先生", "").strip()

        return '\n'.join(lines)