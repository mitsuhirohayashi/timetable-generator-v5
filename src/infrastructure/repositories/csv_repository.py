"""CSV形式でのデータ永続化リポジトリ（統合版）"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from ...domain.entities.school import School

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.entities.grade5_unit import Grade5Unit
from ...domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...domain.value_objects.assignment import Assignment
from ...domain.value_objects.subject_config import SubjectConfig
from ...domain.value_objects.special_support_hours import SpecialSupportHourMapping, SpecialSupportHourMappingEnhanced
from ...domain.utils import parse_class_reference
from .teacher_mapping_repository import TeacherMappingRepository
from .config_repository import ConfigRepository
from .teacher_absence_loader import TeacherAbsenceLoader
from ..config.path_config import path_config


class CSVScheduleRepository:
    """スケジュールのCSV入出力を担当（統合版）"""
    
    def __init__(self, base_path: Path = Path("."), 
                 use_enhanced_features: bool = False,
                 use_support_hours: bool = False):
        """初期化
        
        Args:
            base_path: ベースパス
            use_enhanced_features: 拡張機能（5組時数表記など）を使用するか
            use_support_hours: 特別支援時数表記を使用するか
        """
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        self.absence_loader = TeacherAbsenceLoader()
        self.use_enhanced_features = use_enhanced_features
        self.use_support_hours = use_support_hours
        
        # 拡張機能用の追加初期化
        if use_enhanced_features:
            self.teacher_mapping_repo = TeacherMappingRepository(self.base_path)
            self.support_hour_system = Grade5SupportHourSystem()
            self._forbidden_cells = {}  # enhanced版用
        
        # 支援時数機能用の追加初期化
        if use_support_hours:
            self.grade5_unit = Grade5Unit()
            self.hour_mapping = SpecialSupportHourMapping()
    
    def save_schedule(self, schedule: Schedule, filename: str = "output.csv") -> None:
        """スケジュールをCSVファイルに保存"""
        # filenameが絶対パスの場合
        if filename.startswith("/"):
            file_path = Path(filename)
        # filenameがpath_configのoutput_dirで始まる場合
        elif str(path_config.output_dir) in filename:
            file_path = Path(filename)
        # filenameがdata/で始まる場合（重複を避ける）
        elif filename.startswith("data/"):
            # timetable_v5からの相対パスとして処理
            file_path = path_config.base_dir / filename
        # パスを含む場合
        elif "/" in filename:
            # output/以下の相対パスの場合
            if filename.startswith("output/"):
                file_path = path_config.data_dir / filename
            else:
                file_path = self.base_path / filename
        # デフォルトの出力ファイル
        elif filename == "output.csv":
            file_path = path_config.default_output_csv
        else:
            # その他のファイル（output_enhanced_filled.csvなど）
            file_path = path_config.get_output_path(filename)
        
        # 親ディレクトリが存在しない場合は作成
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                
                # ヘッダー行
                header = ["基本時間割"]
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
                
                # 各クラスの行
                all_classes = self._get_all_classes_from_schedule(schedule)
                for class_ref in sorted(all_classes, key=lambda c: (c.grade, c.class_number)):
                    row = [class_ref.full_name]
                    
                    for day in ["月", "火", "水", "木", "金"]:
                        for period in range(1, 7):
                            time_slot = TimeSlot(day, period)
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if assignment:
                                # 拡張機能: 5組の時数表記
                                if self.use_enhanced_features and class_ref.class_number == 5:
                                    subject_name = self._get_grade5_display(
                                        class_ref, assignment.subject.name, day, period
                                    )
                                # 支援時数機能: 特別支援時数表記
                                elif self.use_support_hours and class_ref.class_number == 5:
                                    subject_name = self._get_support_hour_display(
                                        assignment, time_slot, class_ref
                                    )
                                else:
                                    subject_name = assignment.subject.name
                            else:
                                subject_name = ""
                            row.append(subject_name)
                    
                    writer.writerow(row)
                    
                    # 2年7組の後に空白行を追加
                    if class_ref.full_name == "2年7組":
                        self.logger.info(f"2年7組の後に空白行を追加します")
                        writer.writerow([""] * len(row))
            
            # ログメッセージを機能に応じて変更
            if self.use_enhanced_features or self.use_support_hours:
                self.logger.info(f"スケジュールを保存しました（5組時数表記対応）: {file_path}")
            else:
                self.logger.info(f"スケジュールを保存しました: {file_path}")
            
        except Exception as e:
            self.logger.error(f"スケジュール保存エラー: {e}")
            raise
    
    def load_desired_schedule(self, filename: str = "input.csv", school: Optional['School'] = None) -> Schedule:
        """希望時間割をCSVファイルから読み込み"""
        # 拡張機能が有効な場合は専用メソッドを使用
        if self.use_enhanced_features:
            return self._load_desired_schedule_enhanced(filename, school)
        
        # パスの重複を防ぐ
        if filename.startswith("/"):
            file_path = Path(filename)
        elif filename.startswith("data/"):
            # すでにdata/を含む場合は、base_pathがdataなら親ディレクトリから
            if str(self.base_path).endswith("/data") or str(self.base_path) == "data":
                file_path = self.base_path.parent / filename
            else:
                file_path = Path(filename)
        else:
            file_path = self.base_path / filename
        schedule = Schedule()
        # 初期スケジュール読み込み時は固定科目保護を一時的に無効化
        schedule.disable_fixed_subject_protection()
        # "非○○"制約を保存する辞書を追加
        self.forbidden_cells = {}  # {(TimeSlot, ClassReference): set of forbidden subjects}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                lines = list(reader)
            
            if len(lines) < 3:
                raise ValueError("CSVファイルの形式が正しくありません")
            
            # 校時情報を取得（2行目）
            period_row = lines[1]
            time_slots = []
            for i, period_str in enumerate(period_row[1:], 1):
                if period_str.isdigit():
                    day_index = (i - 1) // 6
                    period = int(period_str)
                    day = ["月", "火", "水", "木", "金"][day_index]
                    time_slots.append(TimeSlot(day, period))
            
            # 各クラスのデータを読み込み（3行目以降）
            for line in lines[2:]:
                if not line or not line[0].strip():
                    continue
                
                class_name = line[0].strip().replace('"', '')
                if not class_name:
                    continue
                
                # クラス参照を作成
                class_ref = parse_class_reference(class_name)
                if not class_ref:
                    continue
                
                # 各時間枠の教科を読み込み
                for i, subject_name in enumerate(line[1:], 0):
                    if i < len(time_slots) and subject_name and subject_name.strip():
                        subject_name = subject_name.strip().replace('"', '')
                        
                        # 空欄または「0」はスキップ（「欠」は保持）
                        if not subject_name or subject_name == "0":
                            if subject_name == "0":
                                self.logger.debug(f"空きスロット（0）を検出: {class_ref}の{time_slots[i]}")
                            continue
                        
                        # "非○○"制約の処理
                        if subject_name.startswith("非"):
                            # "非○○"から禁止教科を抽出
                            forbidden_subject = subject_name[1:]  # "非"を除去
                            time_slot = time_slots[i]
                            key = (time_slot, class_ref)
                            if key not in self.forbidden_cells:
                                self.forbidden_cells[key] = set()
                            self.forbidden_cells[key].add(forbidden_subject)
                            self.logger.info(f"セル配置禁止を追加: {class_ref}の{time_slot}に{forbidden_subject}を配置禁止")
                            
                            # 「非○○」セルに適切な教科を配置を試みる
                            # 見つからない場合でも制約は登録済みなので、後で埋められる
                            if school:
                                suitable_assignment = self._find_suitable_subject_for_forbidden_cell(
                                    schedule, school, time_slot, class_ref, forbidden_subject
                                )
                                if suitable_assignment:
                                    schedule.assign(time_slot, suitable_assignment)
                                    self.logger.info(f"非{forbidden_subject}セルに{suitable_assignment.subject.name}を配置")
                                else:
                                    self.logger.warning(f"非{forbidden_subject}セルの代替教科が見つかりませんでした: {class_ref}の{time_slot}")
                                    self.logger.info(f"非{forbidden_subject}セルは後の処理で埋めます: {class_ref}の{time_slot}")
                            continue
                        
                        # 固定教科の処理
                        fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
                        if subject_name in fixed_subjects:
                            # 固定教科として特別な割り当てを作成
                            fixed_subject = Subject(subject_name)
                            # 固定教科用の教員を取得または作成
                            fixed_teacher = None
                            if school:
                                fixed_teacher = school.get_assigned_teacher(fixed_subject, class_ref)
                            if not fixed_teacher:
                                # デフォルト教員名を設定
                                if subject_name == "欠":
                                    fixed_teacher = Teacher("欠課")
                                else:
                                    fixed_teacher = Teacher(f"{subject_name}担当")
                            
                            # 固定教科でも教師不在チェックを行う（欠、YT、行を除く）
                            if subject_name not in ["欠", "YT", "行"] and fixed_teacher and self.absence_loader.is_teacher_absent(
                                fixed_teacher.name, time_slots[i].day, time_slots[i].period):
                                self.logger.warning(
                                    f"固定教科の教師不在のため割り当てをスキップ: {class_ref} {time_slots[i]} "
                                    f"{subject_name}({fixed_teacher.name}先生)")
                                continue
                            
                            assignment = Assignment(class_ref, fixed_subject, fixed_teacher)
                            schedule.assign(time_slots[i], assignment)
                            # 5組の場合は、後で同期処理でロックされるので、ここではロックしない
                            if class_ref.class_number != 5:
                                schedule.lock_cell(time_slots[i], class_ref)  # 固定教科はロック
                            continue
                        
                        
                        try:
                            subject = Subject(subject_name)
                            
                            # クラスに対して無効な教科はスキップ
                            if not subject.is_valid_for_class(class_ref):
                                self.logger.warning(f"クラス{class_ref}に無効な教科をスキップ: {subject_name}")
                                continue
                            
                            # セル別配置禁止チェック
                            key = (time_slots[i], class_ref)
                            if key in self.forbidden_cells and subject_name in self.forbidden_cells[key]:
                                self.logger.warning(f"セル配置禁止違反を防止: {class_ref}の{time_slots[i]}に{subject_name}は配置不可（非{subject_name}指定）")
                                continue
                            
                            # 美術の月曜・火曜配置を一旦読み込む（後で非常勤制約チェックで処理）
                            if subject_name == "美" and time_slots[i].day in ["月", "火"]:
                                self.logger.info(f"美術の月曜・火曜配置を検出: {class_ref}の{time_slots[i]}に美術（後で非常勤制約チェック）")
                            
                            # 教員情報を取得（schoolが提供されている場合）
                            teacher = None
                            if school:
                                teacher = school.get_assigned_teacher(subject, class_ref)
                            
                            # 3年3組の道徳の場合、詳細なデバッグログを出力
                            if class_ref.full_name == "3年3組" and subject_name == "道":
                                self.logger.info(f"=== 3年3組 道徳のデバッグ情報 ===")
                                self.logger.info(f"  時間枠: {time_slots[i]}")
                                self.logger.info(f"  教科: {subject_name}")
                                self.logger.info(f"  教員: {teacher.name if teacher else 'なし'}")
                                if teacher:
                                    is_absent = self.absence_loader.is_teacher_absent(
                                        teacher.name, time_slots[i].day, time_slots[i].period)
                                    self.logger.info(f"  教員不在チェック結果: {is_absent}")
                                    self.logger.info(f"  教員名でチェック: '{teacher.name}'")
                                self.logger.info("=== デバッグ情報終了 ===")
                            
                            # 教師不在チェック
                            if teacher and self.absence_loader.is_teacher_absent(
                                teacher.name, time_slots[i].day, time_slots[i].period):
                                self.logger.warning(
                                    f"教師不在のため割り当てをスキップ: {class_ref} {time_slots[i]} "
                                    f"{subject_name}({teacher.name}先生)")
                                continue
                            
                            assignment = Assignment(class_ref, subject, teacher)
                            schedule.assign(time_slots[i], assignment)
                            
                            # 固定教科はロック
                            if subject.is_protected_subject():
                                schedule.lock_cell(time_slots[i], class_ref)
                                
                        except ValueError as e:
                            self.logger.warning(f"無効な教科名をスキップ: {subject_name} ({e})")
            
            # 5組の初期同期処理を追加
            if school:
                # Grade5Unitに教師不在チェッカーを設定
                schedule.grade5_unit.set_teacher_absence_checker(
                    self.absence_loader.is_teacher_absent
                )
                self._synchronize_grade5_initial(schedule, school)
                # 交流学級の初期同期処理も追加
                self._synchronize_exchange_classes_initial(schedule, school)
            
            self.logger.info(f"希望時間割を読み込みました: {file_path}")
            
            # 教員不在違反をチェックして削除
            if school:
                self._remove_teacher_absence_violations(schedule, school)
                # 体育館使用制約違反をチェックして削除
                self._remove_gym_constraint_violations(schedule, school)
                # 非常勤教師制約違反をチェックして削除
                self._remove_part_time_teacher_violations(schedule, school)
                
                # 制約違反削除により生じた空きスロットを埋める
                from ...domain.services.smart_empty_slot_filler import SmartEmptySlotFiller
                from ...domain.services.unified_constraint_system import UnifiedConstraintSystem
                from ...infrastructure.config.constraint_loader import ConstraintLoader
                
                # 制約システムを初期化
                constraint_system = UnifiedConstraintSystem()
                constraint_system.school = school
                
                # 制約をロード
                constraint_loader = ConstraintLoader()
                constraints = constraint_loader.load_all_constraints()
                for constraint in constraints:
                    constraint_system.register_constraint(constraint)
                
                # 空きスロットを埋める
                filler = SmartEmptySlotFiller(constraint_system, self.absence_loader)
                filled_count = filler.fill_empty_slots_smartly(schedule, school, max_passes=5)
                if filled_count > 0:
                    self.logger.info(f"制約違反削除後に{filled_count}個の空きスロットを埋めました")
            
            # 読み込み完了後に固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            return schedule
            
        except Exception as e:
            self.logger.error(f"希望時間割読み込みエラー: {e}")
            # エラー時も固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            raise
    
    def _synchronize_grade5_initial(self, schedule: Schedule, school: 'School') -> None:
        """初期読み込み時に5組を同期する"""
        self.logger.info("=== 5組の初期同期処理を開始 ===")
        
        grade5_classes = [
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        ]
        
        sync_count = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の現在の割り当てを取得
                assignments = []
                subjects = []
                has_fixed = False
                
                for class_ref in grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    is_locked = schedule.is_locked(time_slot, class_ref)
                    
                    assignments.append((class_ref, assignment, is_locked))
                    
                    if assignment:
                        subjects.append(assignment.subject.name)
                        # 固定教科がある場合
                        if assignment.subject.name in ["道徳", "YT", "欠", "総合", "総", "学活", "学", "学総"]:
                            has_fixed = True
                    else:
                        subjects.append(None)
                
                # すべて同じ教科なら同期不要
                unique_subjects = set(s for s in subjects if s is not None)
                if len(unique_subjects) <= 1:
                    continue
                
                # 同期する教科を決定
                chosen_subject = None
                chosen_teacher = None
                
                if has_fixed:
                    # 固定教科がある場合はそれで統一
                    fixed_subjects = ["道徳", "YT", "欠", "総合", "総", "学活", "学", "学総"]
                    for s in subjects:
                        if s in fixed_subjects:
                            chosen_subject = Subject(s)
                            # 固定教科用の教員を取得
                            for c in grade5_classes:
                                t = school.get_assigned_teacher(chosen_subject, c)
                                if t:
                                    chosen_teacher = t
                                    break
                            if not chosen_teacher:
                                chosen_teacher = Teacher(f"{s}担当")
                            break
                else:
                    # 通常教科の場合
                    # 特別支援教科（自立、日生、作業）がある場合は除外
                    normal_subjects = {}
                    for i, s in enumerate(subjects):
                        if s and s not in ["自立", "日生", "生単", "作業"]:
                            class_ref = grade5_classes[i]
                            # その教科が有効かチェック
                            try:
                                subject_obj = Subject(s)
                                if subject_obj.is_valid_for_class(class_ref):
                                    normal_subjects[s] = normal_subjects.get(s, 0) + 1
                            except:
                                pass
                    
                    if normal_subjects:
                        # 最も多い通常教科で統一
                        chosen_subject_name = max(normal_subjects, key=normal_subjects.get)
                        chosen_subject = Subject(chosen_subject_name)
                        
                        # 5組共通の教員を探す（金子み先生を優先）
                        for c in grade5_classes:
                            t = school.get_assigned_teacher(chosen_subject, c)
                            if t and "金子み" in t.name:
                                chosen_teacher = t
                                break
                        
                        if not chosen_teacher:
                            # 金子み先生が見つからない場合は他の教員
                            for c in grade5_classes:
                                t = school.get_assigned_teacher(chosen_subject, c)
                                if t:
                                    chosen_teacher = t
                                    break
                
                # 同期実行
                if chosen_subject and chosen_teacher:
                    # 教師不在チェック
                    if self.absence_loader.is_teacher_absent(
                        chosen_teacher.name, time_slot.day, time_slot.period):
                        self.logger.warning(
                            f"5組同期スキップ（教師不在）: {time_slot} "
                            f"{chosen_subject}({chosen_teacher.name}先生)")
                        continue
                    
                    changed = False
                    for class_ref, current_assignment, is_locked in assignments:
                        # ロックされていないセルのみ変更
                        if not is_locked:
                            need_update = False
                            
                            if not current_assignment:
                                need_update = True
                            elif current_assignment.subject != chosen_subject:
                                need_update = True
                            
                            if need_update:
                                # ロックされているセルは変更しない（固定教科の保護）
                                if schedule.is_locked(time_slot, class_ref):
                                    self.logger.debug(f"5組同期スキップ（ロック済み）: {time_slot} {class_ref}")
                                    continue
                                
                                # 既存の割り当てを削除
                                if current_assignment:
                                    schedule.remove_assignment(time_slot, class_ref)
                                
                                # 新しい割り当てを作成
                                new_assignment = Assignment(class_ref, chosen_subject, chosen_teacher)
                                schedule.assign(time_slot, new_assignment)
                                
                                # 固定教科の場合はロック
                                if chosen_subject.name in ["道徳", "YT", "欠", "総合", "総", "学活", "学", "学総"]:
                                    # Grade 5クラスは一括でロックする必要がある
                                    for g5_class in grade5_classes:
                                        if not schedule.is_locked(time_slot, g5_class):
                                            schedule.lock_cell(time_slot, g5_class)
                                
                                self.logger.info(f"5組同期: {time_slot} {class_ref} → {chosen_subject}({chosen_teacher})")
                                changed = True
                    
                    if changed:
                        sync_count += 1
        
        self.logger.info(f"=== 5組の初期同期完了: {sync_count}時限を同期 ===")
    
    def _synchronize_exchange_classes_initial(self, schedule: Schedule, school: 'School') -> None:
        """初期読み込み時に交流学級を親学級と同期する"""
        self.logger.info("=== 交流学級の初期同期処理を開始（CSV読み込み時） ===")
        
        # 交流学級と親学級のマッピング
        exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        sync_count = 0
        jiritsu_sync_count = 0
        
        for exchange_class, parent_class in exchange_mappings.items():
            # 両方のクラスが存在するかチェック
            if exchange_class not in [c for _, a in schedule.get_all_assignments() for c in [a.class_ref]]:
                continue
                
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # ロックされているセルはスキップ
                    if schedule.is_locked(time_slot, exchange_class) or schedule.is_locked(time_slot, parent_class):
                        continue
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # Case 1: 交流学級が自立活動の場合
                    if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                        # 教員不在チェック - 教員が不在の場合はロックしない
                        should_lock = True
                        if exchange_assignment.teacher and school.is_teacher_unavailable(time_slot.day, time_slot.period, exchange_assignment.teacher):
                            should_lock = False
                            self.logger.warning(f"交流学級同期（自立）: {time_slot} {exchange_class}の{exchange_assignment.subject}({exchange_assignment.teacher})は教員不在のためロックしない")
                        
                        # 交流学級の自立活動をロック（教員が利用可能な場合のみ）
                        if should_lock:
                            schedule.lock_cell(time_slot, exchange_class)
                            self.logger.info(f"交流学級同期（自立）: {time_slot} {exchange_class}の{exchange_assignment.subject}をロック")
                        
                        # 自立活動の場合は親学級との同期は不要
                        jiritsu_sync_count += 1
                        continue
                        
                        # 以下の親学級変更処理は実行しない（自立活動時は同期不要）
                        if False and parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                            self.logger.info(f"  {parent_class}を数または英に変更")
                            
                            # まず削除
                            schedule.remove_assignment(time_slot, parent_class)
                            
                            # 数学か英語の教員を探す
                            math_teacher = school.get_assigned_teacher(Subject("数"), parent_class)
                            eng_teacher = school.get_assigned_teacher(Subject("英"), parent_class)
                            
                            # セル別配置禁止チェック
                            parent_key = (time_slot, parent_class)
                            forbidden_subjects = self.forbidden_cells.get(parent_key, set())
                            
                            # 数学を優先的に配置（禁止されていない場合）
                            if "数" not in forbidden_subjects and math_teacher and schedule.is_teacher_available(time_slot, math_teacher) and not school.is_teacher_unavailable(time_slot.day, time_slot.period, math_teacher):
                                new_assignment = Assignment(parent_class, Subject("数"), math_teacher)
                                schedule.assign(time_slot, new_assignment)
                                schedule.lock_cell(time_slot, parent_class)  # 親学級もロック
                                self.logger.info(f"  → {parent_class}に数学を配置してロック")
                                jiritsu_sync_count += 1
                            elif "英" not in forbidden_subjects and eng_teacher and schedule.is_teacher_available(time_slot, eng_teacher) and not school.is_teacher_unavailable(time_slot.day, time_slot.period, eng_teacher):
                                new_assignment = Assignment(parent_class, Subject("英"), eng_teacher)
                                schedule.assign(time_slot, new_assignment)
                                schedule.lock_cell(time_slot, parent_class)  # 親学級もロック
                                self.logger.info(f"  → {parent_class}に英語を配置してロック")
                                jiritsu_sync_count += 1
                            else:
                                if "数" in forbidden_subjects:
                                    self.logger.warning(f"  → {parent_class}に数学は配置不可（非数指定）")
                                if "英" in forbidden_subjects:
                                    self.logger.warning(f"  → {parent_class}に英語は配置不可（非英指定）")
                                self.logger.warning(f"  → {parent_class}に数学・英語を配置できませんでした")
                        else:
                            # 親学級が既に数学か英語の場合もロック
                            if parent_assignment and parent_assignment.subject.name in ['数', '英']:
                                # 教員不在チェック
                                if school.is_teacher_unavailable(time_slot.day, time_slot.period, parent_assignment.teacher):
                                    # 不在教員の授業は削除して別の教科を配置
                                    schedule.remove_assignment(time_slot, parent_class)
                                    self.logger.warning(f'  {parent_class}の{parent_assignment.subject}({parent_assignment.teacher})は教員不在のため削除')
                                    
                                    # 英語を試す（数学が不在の場合）
                                    if parent_assignment.subject.name == '数':
                                        eng_teacher = school.get_assigned_teacher(Subject('英'), parent_class)
                                        if eng_teacher and schedule.is_teacher_available(time_slot, eng_teacher) and not school.is_teacher_unavailable(time_slot.day, time_slot.period, eng_teacher):
                                            # セル別配置禁止チェック
                                            parent_key = (time_slot, parent_class)
                                            forbidden_subjects = self.forbidden_cells.get(parent_key, set())
                                            if '英' not in forbidden_subjects:
                                                new_assignment = Assignment(parent_class, Subject('英'), eng_teacher)
                                                schedule.assign(time_slot, new_assignment)
                                                schedule.lock_cell(time_slot, parent_class)
                                                self.logger.info(f'  → {parent_class}に英語を配置してロック（数学教員不在のため）')
                                            else:
                                                self.logger.warning(f'  → {parent_class}に英語は配置不可（非英指定）')
                                else:
                                    # 教員が利用可能な場合のみロック
                                    schedule.lock_cell(time_slot, parent_class)
                                    self.logger.info(f'  {parent_class}の{parent_assignment.subject}をロック')
                    
                    # Case 2: 交流学級が自立活動でない場合は、親学級と同じにする
                    elif parent_assignment:
                        # 体育は同期しない（体育館制約のため）
                        if parent_assignment.subject.name == "保":
                            continue
                            
                        # 交流学級が親学級と異なる場合、または空きの場合
                        if not exchange_assignment or exchange_assignment.subject != parent_assignment.subject:
                            # 既存の割り当てを削除
                            if exchange_assignment:
                                schedule.remove_assignment(time_slot, exchange_class)
                            
                            # セル別配置禁止チェック
                            exchange_key = (time_slot, exchange_class)
                            forbidden_subjects = self.forbidden_cells.get(exchange_key, set())
                            if parent_assignment.subject.name not in forbidden_subjects:
                                # 親学級と同じ教科・教員で割り当て
                                new_assignment = Assignment(exchange_class, parent_assignment.subject, parent_assignment.teacher)
                                schedule.assign(time_slot, new_assignment)
                                self.logger.info(f"交流学級同期: {time_slot} {exchange_class} → {parent_assignment.subject}")
                                sync_count += 1
                            else:
                                self.logger.warning(f"交流学級同期スキップ: {time_slot} {exchange_class}に{parent_assignment.subject}は配置不可（非{parent_assignment.subject.name}指定）")
                    
                    # Case 3: 親学級が空きで交流学級に授業がある場合（自立活動以外）
                    elif exchange_assignment and not exchange_assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                        # 交流学級を空きにする
                        schedule.remove_assignment(time_slot, exchange_class)
                        self.logger.info(f"交流学級同期: {time_slot} {exchange_class} → 空き（親学級に合わせる）")
                        sync_count += 1
        
        self.logger.info(f"=== 交流学級の初期同期完了: 通常同期{sync_count}件、自立同期{jiritsu_sync_count}件 ===")
    
    def _get_all_classes_from_schedule(self, schedule: Schedule) -> List[ClassReference]:
        """スケジュールから全てのクラスを抽出"""
        classes = set()
        for _, assignment in schedule.get_all_assignments():
            classes.add(assignment.class_ref)
        return list(classes)
    
    def get_forbidden_cells(self) -> Dict[tuple[TimeSlot, ClassReference], Set[str]]:
        """読み込んだCSVファイルから抽出した"非○○"制約を取得"""
        return getattr(self, 'forbidden_cells', {})
    
    def _remove_teacher_absence_violations(self, schedule: Schedule, school: School) -> int:
        """読み込んだ時間割から教員不在違反を削除または移動"""
        from ...infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
        absence_loader = TeacherAbsenceLoader()
        
        removed_count = 0
        moved_count = 0
        
        # 移動が必要な授業を収集
        assignments_to_move = []
        
        # 全ての時間枠をチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if not assignment or not assignment.subject:
                        continue
                    
                    # 教員を取得
                    teacher = assignment.teacher
                    if not teacher:
                        # 教科から教員を推定
                        teacher = school.get_assigned_teacher(assignment.subject, class_ref)
                    
                    if teacher and absence_loader.is_teacher_absent(teacher.name, day, period):
                        # ロックされていない場合のみ処理
                        if not schedule.is_locked(time_slot, class_ref):
                            assignments_to_move.append((time_slot, class_ref, assignment))
                        else:
                            self.logger.warning(f"教員不在違反（ロック済み）: {day}曜{period}校時 {class_ref} {assignment.subject}({teacher.name})")
        
        # 移動を試みる
        for time_slot, class_ref, assignment in assignments_to_move:
            # まず削除
            schedule.remove_assignment(time_slot, class_ref)
            
            # 別の時間枠を探す
            moved = False
            for alt_day in ["月", "火", "水", "木", "金"]:
                for alt_period in range(1, 7):
                    alt_time_slot = TimeSlot(alt_day, alt_period)
                    
                    # 特別な時間枠はスキップ
                    if (alt_day == "月" and alt_period == 6) or \
                       (alt_day in ["火", "水", "金"] and alt_period == 6):
                        continue
                    
                    # 既に授業がある場合はスキップ
                    if schedule.get_assignment(alt_time_slot, class_ref):
                        continue
                    
                    # ロックされている場合はスキップ
                    if schedule.is_locked(alt_time_slot, class_ref):
                        continue
                    
                    # 教員が利用可能かチェック
                    if assignment.teacher and absence_loader.is_teacher_absent(
                            assignment.teacher.name, alt_day, alt_period):
                        continue
                    
                    # 教員の重複チェック
                    if assignment.teacher:
                        conflicting = False
                        for other_class in school.get_all_classes():
                            if other_class != class_ref:
                                other_assignment = schedule.get_assignment(alt_time_slot, other_class)
                                if other_assignment and other_assignment.teacher == assignment.teacher:
                                    conflicting = True
                                    break
                        if conflicting:
                            continue
                    
                    # 移動実行
                    schedule.assign(alt_time_slot, assignment)
                    self.logger.info(f"教員不在授業を移動: {time_slot} → {alt_time_slot} {class_ref} {assignment.subject}({assignment.teacher})")
                    moved = True
                    moved_count += 1
                    break
                
                if moved:
                    break
            
            if not moved:
                self.logger.warning(f"教員不在授業を移動できず削除: {time_slot} {class_ref} {assignment.subject}({assignment.teacher})")
                removed_count += 1
        
        if moved_count > 0 or removed_count > 0:
            self.logger.info(f"教員不在違反処理: {moved_count}件を移動、{removed_count}件を削除")
        
        return removed_count
    
    def _remove_gym_constraint_violations(self, schedule: Schedule, school: School) -> int:
        """読み込んだ時間割から体育館使用制約違反を削除（2つ目以降のPEグループを削除）"""
        removed_count = 0
        
        # 交流学級と親学級のマッピング
        exchange_parent_map = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        # 各時間枠でPEクラスをチェック
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間のPEクラスを収集
                pe_classes = []
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append((class_ref, assignment, schedule.is_locked(time_slot, class_ref)))
                
                # PEグループをカウント（交流学級と親学級は1グループとして数える）
                pe_groups = []
                counted_classes = set()
                
                for class_ref, assignment, is_locked in pe_classes:
                    if class_ref in counted_classes:
                        continue
                    
                    # 交流学級の場合
                    if class_ref in exchange_parent_map:
                        parent_class = exchange_parent_map[class_ref]
                        # 親学級も保健体育をしているか確認
                        parent_has_pe = any(c == parent_class for c, _, _ in pe_classes)
                        if parent_has_pe:
                            # 交流学級と親学級を同じグループとして追加
                            group_classes = [class_ref, parent_class]
                            group_assignments = [(c, a, l) for c, a, l in pe_classes if c in group_classes]
                            pe_groups.append(group_assignments)
                            counted_classes.update(group_classes)
                        else:
                            # 親学級が保健体育でない場合は別グループ
                            pe_groups.append([(class_ref, assignment, is_locked)])
                            counted_classes.add(class_ref)
                    # 親学級の場合
                    elif class_ref in exchange_parent_map.values():
                        # 対応する交流学級を探す
                        exchange_class = None
                        for exc, par in exchange_parent_map.items():
                            if par == class_ref:
                                exchange_class = exc
                                break
                        
                        if exchange_class and exchange_class not in counted_classes:
                            # 交流学級も保健体育をしているか確認
                            exchange_has_pe = any(c == exchange_class for c, _, _ in pe_classes)
                            if exchange_has_pe:
                                # 交流学級と親学級を同じグループとして追加
                                group_classes = [class_ref, exchange_class]
                                group_assignments = [(c, a, l) for c, a, l in pe_classes if c in group_classes]
                                pe_groups.append(group_assignments)
                                counted_classes.update(group_classes)
                            else:
                                # 交流学級が保健体育でない場合は別グループ
                                pe_groups.append([(class_ref, assignment, is_locked)])
                                counted_classes.add(class_ref)
                        elif class_ref not in counted_classes:
                            pe_groups.append([(class_ref, assignment, is_locked)])
                            counted_classes.add(class_ref)
                    # 通常クラスの場合
                    else:
                        pe_groups.append([(class_ref, assignment, is_locked)])
                        counted_classes.add(class_ref)
                
                # 2グループ以上ある場合は違反
                if len(pe_groups) > 1:
                    # 5組の合同体育かチェック
                    grade5_classes = [c for group in pe_groups for c, _, _ in group if c.class_number == 5]
                    non_grade5_classes = [c for group in pe_groups for c, _, _ in group if c.class_number != 5]
                    
                    # 5組が3クラスとも体育を行っており、それ以外のクラスがない場合は合同体育として許可
                    if len(grade5_classes) == 3 and len(non_grade5_classes) == 0:
                        self.logger.info(f"{day}曜{period}校時: 5組合同体育を検出（制約違反なし）")
                        continue  # 違反ではないのでスキップ
                    
                    self.logger.warning(f"体育館使用制約違反を検出: {day}曜{period}校時に{len(pe_groups)}グループが保健体育")
                    
                    # ロックされているグループを優先的に残す
                    # グループ内に1つでもロックされたクラスがあればそのグループを優先
                    pe_groups.sort(key=lambda group: (not any(l for _, _, l in group), str(group[0][0])))
                    
                    # 2つ目以降のグループを削除
                    for i in range(1, len(pe_groups)):
                        for class_ref, assignment, is_locked in pe_groups[i]:
                            if not is_locked:
                                schedule.remove_assignment(time_slot, class_ref)
                                removed_count += 1
                                self.logger.info(f"体育館制約違反を削除: {day}曜{period}校時 {class_ref} 保健体育")
                            else:
                                self.logger.warning(f"体育館制約違反（ロック済み）: {day}曜{period}校時 {class_ref} 保健体育")
        
        if removed_count > 0:
            self.logger.info(f"合計{removed_count}件の体育館使用制約違反を削除しました")
        
        return removed_count
    
    def _remove_part_time_teacher_violations(self, schedule: Schedule, school: School) -> None:
        """非常勤教師制約違反を削除"""
        removed = []
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and assignment.teacher and assignment.subject:
                        # 青井先生（美術）の制約チェック
                        if assignment.teacher.name == "青井" and assignment.subject.name == "美":
                            is_violation = False
                            
                            # 月曜・火曜は全時限不可
                            if day in ["月", "火"]:
                                is_violation = True
                            # 水曜は2,3,4校時のみ可
                            elif day == "水" and period not in [2, 3, 4]:
                                is_violation = True
                            # 木曜は1,2,3校時のみ可
                            elif day == "木" and period not in [1, 2, 3]:
                                is_violation = True
                            # 金曜は2,3,4校時のみ可
                            elif day == "金" and period not in [2, 3, 4]:
                                is_violation = True
                            
                            if is_violation and not schedule.is_locked(time_slot, class_ref):
                                schedule.remove_assignment(time_slot, class_ref)
                                removed.append((time_slot, class_ref, assignment))
                                self.logger.warning(
                                    f"非常勤教師制約違反のため削除: {class_ref} {time_slot} "
                                    f"{assignment.subject.name}({assignment.teacher.name}先生)")
        
        if removed:
            self.logger.info(f"非常勤教師制約違反を{len(removed)}件削除しました")
    
    def _fix_forbidden_cell_violations(self, schedule: Schedule, school: School) -> int:
        """「非○○」制約違反を修正（禁止された教科が配置されている場合）"""
        fixed_count = 0
        
        for (time_slot, class_ref), forbidden_subjects in self.forbidden_cells.items():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name in forbidden_subjects:
                # 制約違反を検出
                self.logger.warning(f"セル配置禁止違反を検出: {class_ref}の{time_slot}に{assignment.subject.name}（非{assignment.subject.name}指定）")
                
                # ロックされていない場合のみ修正
                if not schedule.is_locked(time_slot, class_ref):
                    # まず削除
                    schedule.remove_assignment(time_slot, class_ref)
                    
                    # 適切な教科を探して配置
                    suitable_assignment = self._find_suitable_subject_for_forbidden_cell(
                        schedule, school, time_slot, class_ref, assignment.subject.name
                    )
                    
                    if suitable_assignment:
                        schedule.assign(time_slot, suitable_assignment)
                        self.logger.info(f"セル配置禁止違反を修正: {class_ref}の{time_slot} {assignment.subject.name} → {suitable_assignment.subject.name}")
                        fixed_count += 1
                    else:
                        self.logger.warning(f"セル配置禁止違反の代替教科が見つかりません: {class_ref}の{time_slot}")
        
        if fixed_count > 0:
            self.logger.info(f"合計{fixed_count}件のセル配置禁止違反を修正しました")
        
        return fixed_count
    
    def _find_suitable_subject_for_forbidden_cell(self, schedule: Schedule, school: School,
                                                  time_slot: TimeSlot, class_ref: ClassReference,
                                                  forbidden_subject: str) -> Optional[Assignment]:
        """「非○○」セルに配置する適切な教科を探す"""
        self.logger.info(f"非{forbidden_subject}セルの代替教科を探索中: {class_ref}の{time_slot}")
        
        # 主要5教科を優先
        core_subjects = ["国", "数", "理", "社", "英"]
        
        # 利用可能な教科のリスト（禁止教科と固定教科を除外）
        fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
        
        # 現在の週の授業数をカウント
        current_hours = {}
        for d in ["月", "火", "水", "木", "金"]:
            for p in range(1, 7):
                ts = TimeSlot(d, p)
                assignment = schedule.get_assignment(ts, class_ref)
                if assignment:
                    subject_name = assignment.subject.name
                    current_hours[subject_name] = current_hours.get(subject_name, 0) + 1
        
        # まず主要5教科から試す
        for subject_name in core_subjects:
            if subject_name == forbidden_subject:
                continue
            
            try:
                subject = Subject(subject_name)
                if not subject.is_valid_for_class(class_ref):
                    self.logger.info(f"  {subject_name}: クラスに無効")
                    continue
                
                # この教科を教えられる教員を探す
                teacher = school.get_assigned_teacher(subject, class_ref)
                
                # 交流学級の場合、親学級の教員を使用
                if not teacher and class_ref.is_exchange_class():
                    parent_class = self._get_parent_class(class_ref)
                    if parent_class:
                        teacher = school.get_assigned_teacher(subject, parent_class)
                        if teacher:
                            self.logger.info(f"  {subject_name}: 交流学級のため親学級{parent_class}の教員{teacher.name}を使用")
                
                if not teacher:
                    self.logger.info(f"  {subject_name}: 担当教員なし")
                    continue
                
                # 教員が不在でないかチェック
                if self.absence_loader and self.absence_loader.is_teacher_absent(
                        teacher.name, time_slot.day, time_slot.period):
                    self.logger.info(f"  {subject_name}: 教員({teacher.name})不在")
                    continue
                
                # 教員が他のクラスを教えていないかチェック
                conflicting = False
                for other_class in school.get_all_classes():
                    if other_class != class_ref:
                        other_assignment = schedule.get_assignment(time_slot, other_class)
                        if other_assignment and other_assignment.teacher == teacher:
                            conflicting = True
                            self.logger.info(f"  {subject_name}: 教員({teacher.name})が{other_class}で授業中")
                            break
                
                if not conflicting:
                    # 日内重複チェック
                    daily_count = 0
                    for period in range(1, 7):
                        if period == time_slot.period:
                            continue
                        check_slot = TimeSlot(time_slot.day, period)
                        existing = schedule.get_assignment(check_slot, class_ref)
                        if existing and existing.subject.name == subject_name:
                            daily_count += 1
                    
                    if daily_count > 0:
                        self.logger.info(f"  {subject_name}: 日内重複になるため不可（{time_slot.day}曜日に既に{daily_count}回）")
                        continue
                    
                    # 標準時数をチェック
                    standard_hours = school.get_standard_hours(class_ref, subject)
                    current = current_hours.get(subject_name, 0)
                    self.logger.debug(f"  {subject_name}: 配置可能（現在{current}時間/標準{standard_hours}時間）")
                    return Assignment(class_ref, subject, teacher)
                    
            except Exception as e:
                self.logger.debug(f"  {subject_name}: エラー({e})")
                continue
        
        # 主要5教科で見つからない場合は、その他の教科を試す
        all_subjects = ["音", "美", "保", "技", "家"]
        for subject_name in all_subjects:
            if subject_name == forbidden_subject:
                continue
                
            try:
                subject = Subject(subject_name)
                if not subject.is_valid_for_class(class_ref):
                    self.logger.info(f"  {subject_name}: クラスに無効")
                    continue
                
                teacher = school.get_assigned_teacher(subject, class_ref)
                
                # 交流学級の場合、親学級の教員を使用
                if not teacher and class_ref.is_exchange_class():
                    parent_class = self._get_parent_class(class_ref)
                    if parent_class:
                        teacher = school.get_assigned_teacher(subject, parent_class)
                        if teacher:
                            self.logger.info(f"  {subject_name}: 交流学級のため親学級{parent_class}の教員{teacher.name}を使用")
                
                if not teacher:
                    self.logger.info(f"  {subject_name}: 担当教員なし")
                    continue
                
                if self.absence_loader and self.absence_loader.is_teacher_absent(
                        teacher.name, time_slot.day, time_slot.period):
                    self.logger.info(f"  {subject_name}: 教員({teacher.name})不在")
                    continue
                
                conflicting = False
                for other_class in school.get_all_classes():
                    if other_class != class_ref:
                        other_assignment = schedule.get_assignment(time_slot, other_class)
                        if other_assignment and other_assignment.teacher == teacher:
                            conflicting = True
                            self.logger.info(f"  {subject_name}: 教員({teacher.name})が{other_class}で授業中")
                            break
                
                if not conflicting:
                    # 日内重複チェック
                    daily_count = 0
                    for period in range(1, 7):
                        if period == time_slot.period:
                            continue
                        check_slot = TimeSlot(time_slot.day, period)
                        existing = schedule.get_assignment(check_slot, class_ref)
                        if existing and existing.subject.name == subject_name:
                            daily_count += 1
                    
                    if daily_count > 0:
                        self.logger.info(f"  {subject_name}: 日内重複になるため不可（{time_slot.day}曜日に既に{daily_count}回）")
                        continue
                    
                    # 標準時数をチェック
                    standard_hours = school.get_standard_hours(class_ref, subject)
                    current = current_hours.get(subject_name, 0)
                    self.logger.debug(f"  {subject_name}: 配置可能（現在{current}時間/標準{standard_hours}時間）")
                    return Assignment(class_ref, subject, teacher)
                    
            except Exception as e:
                self.logger.debug(f"  {subject_name}: エラー({e})")
                continue
        
        self.logger.warning(f"非{forbidden_subject}セルの代替教科が見つかりませんでした: {class_ref}の{time_slot}")
        return None



class CSVSchoolRepository:
    """学校データのCSV入出力を担当"""
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
    
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
        
        # 教師名を取得
        teacher_name = assignment.teacher.name if assignment.teacher else None
        
        # 時数コードを取得
        hour_code = self.hour_mapping.get_hour_code(
            assignment.subject.name, 
            time_slot.day, 
            time_slot.period,
            teacher_name
        )
        
        return hour_code
    
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
        return None  # デフォルト教員は存在しない