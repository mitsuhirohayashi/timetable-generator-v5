"""リファクタリング版CSVScheduleRepository - ファサードパターンで各責務を統合"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.entities.grade5_unit import Grade5Unit
from ...domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...domain.value_objects.assignment import Assignment
from ...domain.value_objects.special_support_hours import SpecialSupportHourMapping, SpecialSupportHourMappingEnhanced
from ...domain.utils import parse_class_reference
from ..config.path_config import path_config
from .schedule_io.csv_reader import CSVScheduleReader
from .schedule_io.csv_writer import CSVScheduleWriter
from .teacher_schedule_repository import TeacherScheduleRepository
# Validation service removed to avoid circular import
from .teacher_absence_loader import TeacherAbsenceLoader
from .teacher_mapping_repository import TeacherMappingRepository


class CSVScheduleRepository:
    """リファクタリング版スケジュールリポジトリ - 各責務を専門クラスに委譲"""
    
    def __init__(
        self,
        base_path: Path = Path("."),
        use_enhanced_features: bool = False,
        use_support_hours: bool = False
    ):
        """初期化
        
        Args:
            base_path: ベースパス
            use_enhanced_features: 拡張機能を使用するか
            use_support_hours: 特別支援時数表記を使用するか
        """
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        self.use_enhanced_features = use_enhanced_features
        self.use_support_hours = use_support_hours
        
        # 責務ごとのコンポーネントを初期化
        self.reader = CSVScheduleReader()
        self.writer = CSVScheduleWriter(use_support_hours)
        self.teacher_schedule_repo = TeacherScheduleRepository(use_enhanced_features)
        self.absence_loader = TeacherAbsenceLoader()
        
        # 読み込んだ制約情報
        self._forbidden_cells = {}
    
    def save_schedule(self, schedule: Schedule, filename: str = "output.csv") -> None:
        """スケジュールをCSVファイルに保存"""
        file_path = self._resolve_output_path(filename)
        self.writer.write(schedule, file_path)
    
    def load_desired_schedule(
        self,
        filename: str = "input.csv",
        school: Optional[School] = None
    ) -> Schedule:
        """希望時間割をCSVファイルから読み込み"""
        file_path = self._resolve_input_path(filename)
        
        # 基本的な読み込み
        schedule = self.reader.read(file_path, school)
        
        # 制約情報を保存
        self._forbidden_cells = self.reader.get_forbidden_cells()
        
        if school:
            # Grade5Unitに教師不在チェッカーを設定
            schedule.grade5_unit.set_teacher_absence_checker(
                self.absence_loader.is_teacher_absent
            )
        
        return schedule
    
    def save_teacher_schedule(
        self,
        schedule: Schedule,
        school: School,
        filename: str = "teacher_schedule.csv"
    ) -> None:
        """教師別時間割をCSVファイルに保存"""
        self.teacher_schedule_repo.save_teacher_schedule(
            schedule, school, filename
        )
    
    def get_forbidden_cells(self) -> Dict[Tuple[TimeSlot, ClassReference], Set[str]]:
        """読み込んだCSVファイルから抽出した非○○制約を取得"""
        return self._forbidden_cells
    
    def _resolve_output_path(self, filename: str) -> Path:
        """出力ファイルパスを解決"""
        if filename.startswith("/"):
            return Path(filename)
        elif str(path_config.output_dir) in filename:
            return Path(filename)
        elif filename.startswith("data/"):
            return path_config.base_dir / filename
        elif filename == "output.csv":
            return path_config.default_output_csv
        else:
            return path_config.get_output_path(filename)
    
    def _resolve_input_path(self, filename: str) -> Path:
        """入力ファイルパスを解決"""
        if filename.startswith("/"):
            return Path(filename)
        elif filename.startswith("data/"):
            if str(self.base_path).endswith("/data") or str(self.base_path) == "data":
                return self.base_path.parent / filename
            else:
                return Path(filename)
        else:
            return self.base_path / filename


class CSVSchoolRepository:
    """学校データのCSV入出力を担当"""
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        self.teacher_mapping_repo = TeacherMappingRepository(self.base_path)
    
    def load_standard_hours(self, filename: str = "base_timetable.csv") -> Dict[tuple[ClassReference, Subject], float]:
        """標準時数データをCSVから読み込み"""
        # filenameがdata/で始まる場合は、base_pathとの重複を避ける
        if filename.startswith('data/'):
            file_path = Path(filename)
        else:
            file_path = self.base_path / filename
        standard_hours = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                lines = list(reader)
            
            if len(lines) < 3:
                raise ValueError("標準時数CSVファイルの形式が正しくありません")
            
            # 教科ヘッダー（2行目）
            subject_headers = []
            for header in lines[1][1:]:  # 最初の列はクラス名なのでスキップ
                if header and header.strip():
                    try:
                        subject_headers.append(Subject(header.strip()))
                    except ValueError:
                        subject_headers.append(None)  # 無効な教科名はNone
                else:
                    subject_headers.append(None)
            
            # 各クラスの標準時数（3行目以降）
            for line in lines[2:]:
                if not line or not line[0].strip():
                    continue
                
                class_name = line[0].strip()
                class_ref = parse_class_reference(class_name)
                if not class_ref:
                    continue
                
                # 各教科の時数
                for i, hours_str in enumerate(line[1:], 0):
                    if (i < len(subject_headers) and 
                        subject_headers[i] and 
                        hours_str and hours_str.strip()):
                        
                        try:
                            hours = float(hours_str.strip())
                            if hours > 0:
                                standard_hours[(class_ref, subject_headers[i])] = hours
                        except ValueError:
                            continue
            
            self.logger.info(f"標準時数データを読み込みました: {len(standard_hours)}件")
            return standard_hours
            
        except Exception as e:
            self.logger.error(f"標準時数読み込みエラー: {e}")
            raise
    
    def load_school_data(self, base_timetable_file: str = "base_timetable.csv") -> School:
        """学校の基本データを読み込んでSchoolエンティティを構築"""
        school = School()
        
        # 標準時数データから学校情報を構築
        standard_hours = self.load_standard_hours(base_timetable_file)
        
        # 教員マッピングを読み込み
        # self.base_pathが既にdata/configを指している場合は、configを重複させない
        if str(self.base_path).endswith("config"):
            teacher_mapping_repo = TeacherMappingRepository(self.base_path)
            teacher_mapping = teacher_mapping_repo.load_teacher_mapping("teacher_subject_mapping.csv")
        else:
            teacher_mapping_repo = TeacherMappingRepository(self.base_path)
            teacher_mapping = teacher_mapping_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
        
        for (class_ref, subject), hours in standard_hours.items():
            # クラスを追加
            school.add_class(class_ref)
            
            # クラスに対して無効な教科はスキップ
            if not subject.is_valid_for_class(class_ref):
                self.logger.warning(f"標準時数データ: クラス{class_ref}に無効な教科をスキップ: {subject}")
                continue
            
            # 標準時数を設定
            school.set_standard_hours(class_ref, subject, hours)
            
            # 交流学級の特別処理
            if class_ref.is_exchange_class():
                # 交流学級は自立以外の教科では教員を割り当てない
                if subject.name != "自立":
                    self.logger.debug(f"交流学級 {class_ref} の {subject} は教員割り当て不要（親学級と一緒に授業）")
                    continue
                # 自立の場合は通常通り教員マッピングから取得
            
            # 教員マッピングから実際の教員を取得
            teacher = teacher_mapping_repo.get_teacher_for_subject_class(teacher_mapping, subject, class_ref)
            
            # マッピングにない場合はスキップ（実在の教員のみを使用）
            if not teacher:
                # 交流学級の自立以外は正常な状態なので、警告レベルを下げる
                if class_ref.is_exchange_class():
                    self.logger.debug(f"教員マッピングなし: {class_ref} {subject}")
                else:
                    self.logger.warning(f"教員マッピングなし: {class_ref} {subject} - この教科は担当教員が設定されていないため、スキップします")
                continue
            
            school.assign_teacher_subject(teacher, subject)
            school.assign_teacher_to_class(teacher, subject, class_ref)
        
        # 恒久的な教師の休み情報を適用
        permanent_absences = teacher_mapping_repo.get_permanent_absences()
        for teacher_name, absences in permanent_absences.items():
            for day, absence_type in absences:
                periods = self._get_periods_from_absence_type(absence_type)
                for period in periods:
                    # 教師名のバリエーションを試す
                    teacher_variations = [teacher_name, f"{teacher_name}先生"]
                    for variation in teacher_variations:
                        school.set_teacher_unavailable(day, period, Teacher(variation))
                    self.logger.info(f"恒久的休み設定: {teacher_name} - {day}{period}時限")
        
        self.logger.info(f"学校データを構築しました: {school}")
        return school
    
    def _get_periods_from_absence_type(self, absence_type: str) -> List[int]:
        """休み種別から対象時限を取得"""
        if absence_type == '終日':
            return [1, 2, 3, 4, 5, 6]
        elif absence_type == '午後':
            return [4, 5, 6]
        else:
            return []
    
    def _get_parent_class(self, exchange_class: ClassReference) -> Optional[ClassReference]:
        """交流学級の親学級を取得"""
        exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        return exchange_mappings.get(exchange_class)
    
    # ========== 拡張機能用のメソッド ==========
    
    def _load_desired_schedule_enhanced(self, filename: str, school: School) -> Schedule:
        """拡張版の希望時間割読み込み（教師不在を考慮）"""
        file_path = self.base_path / filename
        schedule = Schedule()
        # 初期スケジュール読み込み時は固定科目保護を一時的に無効化
        schedule.disable_fixed_subject_protection()
        
        # Grade5Unitの初期化
        grade5_unit = Grade5Unit()
        schedule.grade5_unit = grade5_unit
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                # ヘッダー行をスキップ
                if len(rows) < 3:
                    self.logger.warning(f"ファイルが短すぎます: {file_path}")
                    return schedule
                
                # 各クラスの行を処理
                for row_idx in range(2, len(rows)):
                    if row_idx >= len(rows) or not rows[row_idx]:
                        continue
                    
                    row = rows[row_idx]
                    if len(row) < 31:  # クラス名 + 30コマ
                        continue
                    
                    class_name = row[0].strip()
                    if not class_name or '組' not in class_name:
                        continue
                    
                    # クラス参照を作成
                    try:
                        grade, class_num = self._parse_class_name(class_name)
                        class_ref = ClassReference(grade, class_num)
                    except ValueError:
                        self.logger.warning(f"無効なクラス名: {class_name}")
                        continue
                    
                    # 5組かどうか判定
                    is_grade5 = class_num == 5
                    
                    # 各時限の割り当てを処理
                    for col_idx in range(1, min(31, len(row))):
                        subject_name = row[col_idx].strip()
                        
                        if not subject_name:
                            continue
                        
                        # 時間枠を計算
                        day_idx = (col_idx - 1) // 6
                        period = ((col_idx - 1) % 6) + 1
                        days = ["月", "火", "水", "木", "金"]
                        if day_idx >= len(days):
                            continue
                        
                        time_slot = TimeSlot(days[day_idx], period)
                        
                        # 無効な教科名をスキップ
                        if subject_name == '0':
                            self.logger.warning(f"無効な教科名をスキップ: {subject_name} (Invalid subject: {subject_name})")
                            continue
                        
                        # 「非○○」形式の場合、配置禁止として記録
                        if subject_name.startswith('非'):
                            forbidden_subject = subject_name[1:]
                            self._add_forbidden_cell(class_ref, time_slot, forbidden_subject)
                            self.logger.info(f"セル配置禁止を追加: {class_ref}の{time_slot}に{forbidden_subject}を配置禁止")
                            continue
                        
                        # 固定教科の場合はロック
                        if subject_name in ['欠', 'YT', '道', '学', '学活', '学総', '総', '総合', '行']:
                            subject = Subject(subject_name)
                            teacher = Teacher("欠課" if subject_name == '欠' else f"{subject_name}担当")
                            assignment = Assignment(class_ref, subject, teacher)
                            
                            if is_grade5:
                                # 5組の場合、ユニットに登録
                                grade5_unit.assign(time_slot, subject, teacher)
                                grade5_unit.lock_slot(time_slot)
                            else:
                                schedule.assign(time_slot, assignment)
                                schedule.lock_cell(time_slot, class_ref)
                            continue
                        
                        # 教師を取得
                        teacher = school.get_assigned_teacher(Subject(subject_name), class_ref)
                        if not teacher:
                            # 教師が見つからない場合、マッピングリポジトリから取得
                            teacher_name = self.teacher_mapping_repo.get_teacher_for_subject(
                                subject_name, grade, class_num)
                            if teacher_name:
                                teacher = Teacher(teacher_name)
                            else:
                                teacher = Teacher(f"{subject_name}担当")
                        
                        # 教師不在チェック
                        if self.absence_loader.is_teacher_absent(
                            teacher.name, days[day_idx], period):
                            self.logger.warning(
                                f"教師不在のため割り当てをスキップ: {class_ref} {time_slot} "
                                f"{subject_name}({teacher.name}先生)")
                            
                            # 5組の場合は代替教科を探す
                            if is_grade5:
                                alt_subject = self._find_alternative_for_grade5(
                                    school, class_ref, time_slot, subject_name, teacher.name)
                                if alt_subject:
                                    subject = Subject(alt_subject['subject'])
                                    teacher = Teacher(alt_subject['teacher'])
                                    grade5_unit.assign(time_slot, subject, teacher)
                                    self.logger.info(
                                        f"5組代替割り当て: {time_slot} {alt_subject['subject']}"
                                        f"({alt_subject['teacher']}先生)")
                            continue
                        
                        # 通常の割り当て
                        subject = Subject(subject_name)
                        assignment = Assignment(class_ref, subject, teacher)
                        
                        if is_grade5:
                            grade5_unit.assign(time_slot, subject, teacher)
                            self.logger.info(f"5組ユニット: {time_slot}に{subject}({teacher})を割り当て")
                        else:
                            schedule.assign(time_slot, assignment)
                
                # 5組の初期同期処理
                self._sync_grade5_initial_enhanced(schedule, grade5_unit)
                
                # 交流学級の初期同期処理
                self._sync_exchange_classes_initial_enhanced(schedule, school)
                
            self.logger.info(f"希望時間割を読み込みました: {file_path}")
            # 読み込み完了後に固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            return schedule
            
        except Exception as e:
            self.logger.error(f"希望時間割の読み込みエラー: {e}")
            # エラー時も固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            raise
    
    def _parse_class_name(self, class_name: str) -> Tuple[int, int]:
        """クラス名から学年とクラス番号を抽出"""
        parts = class_name.replace('年', ' ').replace('組', '').split()
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        raise ValueError(f"Invalid class name format: {class_name}")
    
    def _add_forbidden_cell(self, class_ref: ClassReference, time_slot: TimeSlot, 
                          forbidden_subject: str) -> None:
        """セル別配置禁止を追加"""
        key = (class_ref, time_slot)
        if key not in self._forbidden_cells:
            self._forbidden_cells[key] = set()
        self._forbidden_cells[key].add(forbidden_subject)
    
    def _find_alternative_for_grade5(self, school: School, class_ref: ClassReference,
                                    time_slot: TimeSlot, original_subject: str, 
                                    absent_teacher: str) -> Optional[Dict[str, str]]:
        """5組の代替教科・教師を探す"""
        # 利用可能な教科と教師のペアを探す
        alternatives = []
        
        # 主要教科を優先
        for subject_name in ['国', '数', '理', '社', '英', '音', '美', '技', '家', '保']:
            if subject_name == original_subject:
                continue
            
            # この教科の教師を取得
            teacher_name = self.teacher_mapping_repo.get_teacher_for_subject(
                subject_name, class_ref.grade, class_ref.class_num)
            
            if teacher_name and not self.absence_loader.is_teacher_absent(
                teacher_name, time_slot.day, time_slot.period):
                alternatives.append({
                    'subject': subject_name,
                    'teacher': teacher_name,
                    'priority': 1 if subject_name in ['国', '数', '理', '社', '英'] else 2
                })
        
        # 優先度順にソート
        alternatives.sort(key=lambda x: x['priority'])
        
        return alternatives[0] if alternatives else None
    
    def _sync_grade5_initial_enhanced(self, schedule: Schedule, grade5_unit: Grade5Unit) -> None:
        """5組の初期同期処理（拡張版）"""
        self.logger.info("=== 5組の初期同期処理を開始 ===")
        sync_count = 0
        
        # Grade5Unitから全ての割り当てを取得してScheduleに反映
        for time_slot, class_ref, assignment in grade5_unit.get_all_assignments():
            schedule.assign(time_slot, assignment)
            if grade5_unit.is_locked(time_slot):
                schedule.lock_cell(time_slot, class_ref)
            sync_count += 1
        
        self.logger.info(f"=== 5組の初期同期完了: {sync_count}時限を同期 ===")
    
    def _sync_exchange_classes_initial_enhanced(self, schedule: Schedule, school: School) -> None:
        """交流学級の初期同期処理（拡張版）"""
        self.logger.info("=== 交流学級の初期同期処理を開始（CSV読み込み時） ===")
        
        # 交流学級のペアを定義
        exchange_pairs = [
            (ClassReference(1, 1), ClassReference(1, 6)),
            (ClassReference(2, 3), ClassReference(2, 6)),
            (ClassReference(3, 3), ClassReference(3, 6))
        ]
        
        sync_count = 0
        jiritsu_sync_count = 0
        
        for parent_class, child_class in exchange_pairs:
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    child_assignment = schedule.get_assignment(time_slot, child_class)
                    
                    # 自立の同期処理
                    if child_assignment and child_assignment.subject.name == "自立":
                        if parent_assignment:
                            self.logger.info(
                                f"交流学級同期（自立）: {time_slot} {child_class}の自立をロック")
                            schedule.lock_cell(time_slot, child_class)
                            self.logger.info(f"  {parent_class}の{parent_assignment.subject}をロック")
                            schedule.lock_cell(time_slot, parent_class)
                            jiritsu_sync_count += 1
        
        self.logger.info(
            f"=== 交流学級の初期同期完了: 通常同期{sync_count}件、自立同期{jiritsu_sync_count}件 ===")
    
    def _get_grade5_display(self, class_ref: ClassReference, subject: str, 
                           day: str, period: int) -> str:
        """5組の表示を取得（時数表記または通常教科）"""
        # 時数表記を使用すべきか判定
        if self.support_hour_system.should_use_support_hour(class_ref, subject, day, period):
            return self.support_hour_system.get_support_hour_code(class_ref, subject, day, period)
        return subject
    
    # ========== 支援時数機能用のメソッド ==========
    
    def _get_support_hour_display(self, assignment: Assignment, 
                                  time_slot: TimeSlot, 
                                  class_ref: ClassReference) -> str:
        """5組の時数表記を取得（支援時数版）"""
        # 特別な教科はそのまま表示
        if assignment.subject.name in ["欠", "YT", "道", "日生", "自立", "作業"]:
            return assignment.subject.name
        
        # 支援時数表記の場合は、CSVWriterに処理を委譲する
        # ここでは単純に教科名を返す
        return assignment.subject.name
    
    # ========== 教師別時間割 ==========
    
    def save_teacher_schedule(self, schedule: Schedule, school: School, 
                             filename: str = "teacher_schedule.csv") -> None:
        """教師別時間割をCSVファイルに保存"""
        if filename == "teacher_schedule.csv":
            file_path = path_config.get_output_path(filename)
        else:
            file_path = Path(filename) if filename.startswith("/") else self.base_path / filename
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                
                # ヘッダー行
                header = ["教員"]
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 7):
                        header.append(day)
                writer.writerow(header)
                
                # 校時行
                period_row = [""]
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 7):
                        period_row.append(str(period))
                writer.writerow(period_row)
                
                # 各教師の行
                all_teachers = list(school.get_all_teachers())
                
                for teacher in sorted(all_teachers, key=lambda t: t.name):
                    row = [teacher.name]
                    
                    for day in ["月", "火", "水", "木", "金"]:
                        for period in range(1, 7):
                            time_slot = TimeSlot(day, period)
                            
                            # この時間の授業を探す
                            cell_content = ""
                            for class_ref in school.get_all_classes():
                                assignment = schedule.get_assignment(time_slot, class_ref)
                                if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                                    # クラス表示形式の選択
                                    if self.use_enhanced_features:
                                        cell_content = f"{class_ref.short_name_alt}"
                                    else:
                                        cell_content = f"{class_ref.grade}-{class_ref.class_number}"
                                    break
                            
                            row.append(cell_content)
                    
                    writer.writerow(row)
                
                # 拡張機能が有効な場合は会議時間の行も追加
                if self.use_enhanced_features:
                    self._add_meeting_rows(writer)
            
            if self.use_enhanced_features or self.use_support_hours:
                self.logger.info(f"教師別時間割を保存しました（5組時数表記対応）: {file_path}")
            else:
                self.logger.info(f"教師別時間割を保存しました: {file_path}")
            
        except Exception as e:
            self.logger.error(f"教師別時間割保存エラー: {e}")
            raise
    
    def _add_meeting_rows(self, writer) -> None:
        """会議時間の行を追加"""
        # 会議情報（理想の結果から）
        meetings = {
            "青井": ["", "", "", "", "", "", "3-1選", "", "", "", "", "YT", 
                    "", "", "", "", "", "YT", "", "", "", "", "", "", 
                    "", "", "", "", "", "YT"],
            "校長": ["企画", "HF", "", "", "", "", "生指", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", "",
                    "終日不在（赤色で表示）"],
            "児玉": ["企画", "HF", "", "", "", "", "生指", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", ""],
            "吉村": ["企画", "HF", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", ""],
        }
        
        # 空行を追加
        writer.writerow([""] * 31)
        
        # 会議行を追加
        for teacher, schedule in meetings.items():
            writer.writerow([teacher] + schedule)
    
    def _get_default_teacher_name(self, subject: Subject, class_ref: ClassReference) -> str:
        """教科・クラスに基づくデフォルト教員名を生成 - 削除予定"""
        # 注意: デフォルト教員は使用しない。実在の教員のみを使用する。
        # この関数は互換性のために残されているが、使用すべきではない
        self.logger.warning(f"警告: デフォルト教員名が要求されました: {subject.name} for {class_ref}")
