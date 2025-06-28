"""CSV形式のスケジュール読み込み"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .base import ScheduleReader
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from ....domain.utils import parse_class_reference
from ....shared.utils.csv_operations import CSVOperations
from ....shared.mixins.logging_mixin import LoggingMixin
from ..teacher_mapping_repository import TeacherMappingRepository


class CSVScheduleReader(LoggingMixin, ScheduleReader):
    """CSV形式のスケジュール読み込み"""
    
    def __init__(self, strict_absence_check: bool = False):
        super().__init__()
        self.forbidden_cells: Dict[Tuple[TimeSlot, ClassReference], Set[str]] = {}
        self._fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
        self._test_periods: Dict[Tuple[TimeSlot, ClassReference], Assignment] = {}
        # テスト期間はFollow-up.csvから読み込むため、ここでは空にする
        self._test_subjects = set()  # {"テスト", "技家", "テ", "test", "TEST"}
        # 教師マッピングリポジトリを初期化
        self._teacher_mapping_repo = None
        # 厳格な教師不在チェックを行うかどうか
        self.strict_absence_check = strict_absence_check
        self._teacher_absence_loader = None
    
    def read(self, file_path: Path, school: Optional[School] = None) -> Schedule:
        """CSVファイルからスケジュールを読み込む"""
        schedule = Schedule()
        # 初期スケジュール読み込み時は固定科目保護と5組同期を一時的に無効化
        schedule.disable_fixed_subject_protection()
        schedule.disable_grade5_sync()
        
        # 教師マッピングリポジトリを初期化（遅延初期化）
        if self._teacher_mapping_repo is None:
            from ....infrastructure.config.path_config import path_config
            self._teacher_mapping_repo = TeacherMappingRepository(path_config.data_dir)
            # マッピングデータを読み込む
            self._teacher_mapping = self._teacher_mapping_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
        else:
            self._teacher_mapping = getattr(self, '_teacher_mapping', {})
        
        # 厳格チェックモードの場合、教師不在情報を読み込み
        if self.strict_absence_check and self._teacher_absence_loader is None:
            from ....infrastructure.di_container import get_container, ITeacherAbsenceRepository
            self._teacher_absence_loader = get_container().resolve(ITeacherAbsenceRepository)
        
        try:
            lines = CSVOperations.read_csv_raw(str(file_path))
            
            if len(lines) < 3:
                raise ValueError("CSVファイルの形式が正しくありません")
            
            # タイムスロットを解析
            time_slots = self._parse_time_slots(lines[1])
            
            # 5組のデータを先に収集（後で一括処理するため）
            grade5_data = {}
            
            # 各クラスのデータを読み込み
            for line in lines[2:]:
                if not self._is_valid_class_line(line):
                    continue
                
                class_ref = parse_class_reference(line[0].strip().replace('"', ''))
                if not class_ref:
                    continue
                
                # 5組の場合は一旦データを保存
                if class_ref.class_number == 5:
                    grade5_data[class_ref] = (line[1:], time_slots)
                else:
                    # 5組以外は通常通り処理
                    self._process_class_assignments(
                        schedule, school, class_ref, line[1:], time_slots
                    )
            
            # 5組のデータを処理する前に5組同期を有効化
            # （5組データは同期して処理する必要があるため）
            schedule.enable_grade5_sync()
            
            # 5組のデータを最後に処理（同期を考慮）
            for class_ref, (assignments, time_slots) in grade5_data.items():
                self._process_class_assignments(
                    schedule, school, class_ref, assignments, time_slots
                )
            
            self.logger.info(f"スケジュールを読み込みました: {file_path}")
            # 読み込み完了後に固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            return schedule
            
        except Exception as e:
            self.logger.error(f"スケジュール読み込みエラー: {e}")
            # エラー時も固定科目保護と5組同期を再有効化
            schedule.enable_fixed_subject_protection()
            schedule.enable_grade5_sync()
            raise
    
    def _parse_time_slots(self, period_row: List[str]) -> List[TimeSlot]:
        """期間行からタイムスロットを解析"""
        time_slots = []
        days = ["月", "火", "水", "木", "金"]
        
        for i, period_str in enumerate(period_row[1:], 1):
            if period_str.isdigit():
                day_index = (i - 1) // 6
                period = int(period_str)
                if day_index < len(days):
                    time_slots.append(TimeSlot(days[day_index], period))
        
        return time_slots
    
    def _is_valid_class_line(self, line: List[str]) -> bool:
        """有効なクラス行かチェック"""
        return line and line[0].strip() and line[0].strip() != '""'
    
    def _process_class_assignments(
        self, 
        schedule: Schedule,
        school: Optional[School],
        class_ref: ClassReference,
        assignments: List[str],
        time_slots: List[TimeSlot]
    ) -> None:
        """クラスの割り当てを処理"""
        for i, subject_name in enumerate(assignments):
            if i >= len(time_slots):
                break
                
            subject_name = subject_name.strip().replace('"', '')
            if not subject_name or subject_name == "0":
                continue
            
            time_slot = time_slots[i]
            
            # 非○○制約の処理
            if subject_name.startswith("非"):
                self._handle_forbidden_constraint(
                    class_ref, time_slot, subject_name[1:]
                )
                continue
            
            # 通常の割り当て処理
            self._assign_subject(
                schedule, school, class_ref, time_slot, subject_name
            )
    
    def _handle_forbidden_constraint(
        self,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        forbidden_subject: str
    ) -> None:
        """非○○制約を処理"""
        key = (time_slot, class_ref)
        if key not in self.forbidden_cells:
            self.forbidden_cells[key] = set()
        self.forbidden_cells[key].add(forbidden_subject)
        self.logger.info(
            f"セル配置禁止を追加: {class_ref}の{time_slot}に"
            f"{forbidden_subject}を配置禁止"
        )
    
    def _assign_subject(
        self,
        schedule: Schedule,
        school: Optional[School],
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject_name: str
    ) -> None:
        """教科を割り当て"""
        try:
            subject = Subject(subject_name)
            
            # 教科の妥当性チェック
            if not subject.is_valid_for_class(class_ref):
                self.logger.warning(
                    f"クラス{class_ref}に無効な教科をスキップ: {subject_name}"
                )
                return
            
            # セル配置禁止チェック
            key = (time_slot, class_ref)
            if key in self.forbidden_cells and \
               subject_name in self.forbidden_cells[key]:
                self.logger.warning(
                    f"セル配置禁止違反を防止: {class_ref}の{time_slot}に"
                    f"{subject_name}は配置不可"
                )
                return
            
            # 教員を取得
            teacher = self._get_teacher(school, subject, class_ref, subject_name)
            
            # 厳格チェックモードの場合、教師不在チェック
            if self.strict_absence_check and self._teacher_absence_loader and teacher:
                if hasattr(teacher, 'name') and teacher.name not in ["欠課", "未定", "TBA"]:
                    if self._teacher_absence_loader.is_teacher_absent(teacher.name, time_slot.day, time_slot.period):
                        # 固定科目でも不在教師の場合は割り当てを拒否
                        self.logger.warning(
                            f"厳格チェック: 不在教師の授業をスキップ: {time_slot} {class_ref} "
                            f"{subject_name} ({teacher.name})"
                        )
                        return
            
            # 割り当てを作成
            assignment = Assignment(class_ref, subject, teacher)
            try:
                # 割り当て前にセルがロックされていないか確認
                if schedule.is_locked(time_slot, class_ref):
                    existing_assignment = schedule.get_assignment(time_slot, class_ref)
                    # 既に同じ内容が割り当てられている場合は何もしない
                    if existing_assignment and existing_assignment.subject.name == subject_name:
                        pass
                    else:
                        self.logger.warning(
                            f"ロックされたセルへの割り当てをスキップ: {time_slot} {class_ref} - "
                            f"既存: {existing_assignment.subject.name if existing_assignment else 'なし'}, "
                            f"新規: {subject_name}"
                        )
                    return

                schedule.assign(time_slot, assignment)
                
                # テスト科目の場合は記録してロック
                if subject_name in self._test_subjects or "テスト" in subject_name:
                    self._test_periods[(time_slot, class_ref)] = assignment
                    schedule.lock_cell(time_slot, class_ref)
                    self.logger.info(
                        f"テスト期間をロック: {class_ref} {time_slot} = {subject_name}"
                    )
                
                # デバッグ: 5組のテスト期間データ読み込みを確認
                if class_ref.class_number == 5 and time_slot.day in ["月", "火", "水"] and time_slot.period <= 3:
                    self.logger.info(
                        f"[CSV読み込み] 5組テスト期間データ: {time_slot} {class_ref} - {subject_name}"
                    )
                    
            except Exception as e:
                self.logger.error(f"割り当てエラー: {time_slot} {class_ref} - {subject_name}: {e}")
                # エラーが発生しても読み込みを続行
                return
            
            # 固定教科はロック
            if subject_name in self._fixed_subjects:
                schedule.lock_cell(time_slot, class_ref)
                
        except ValueError as e:
            self.logger.warning(f"無効な教科名をスキップ: {subject_name} ({e})")
    
    def _get_teacher(
        self,
        school: Optional[School],
        subject: Subject,
        class_ref: ClassReference,
        subject_name: str
    ) -> Teacher:
        """教員を取得"""
        # まず教師マッピングから取得を試みる
        if self._teacher_mapping_repo and hasattr(self, '_teacher_mapping'):
            teacher = self._teacher_mapping_repo.get_teacher_for_subject_class(
                self._teacher_mapping,
                subject,
                class_ref
            )
            if teacher:
                return teacher
        
        # 学校データから取得を試みる
        if school:
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher:
                return teacher
        
        # デフォルト教員名を設定
        if subject_name == "欠":
            return Teacher("欠課")
        else:
            # 交流学級専用の教師名を生成（重複を避けるため）
            if class_ref.class_number in [6, 7]:
                return Teacher(f"{subject_name}_{class_ref}")
            else:
                return Teacher(f"{subject_name}担当")
    
    def get_forbidden_cells(self) -> Dict[Tuple[TimeSlot, ClassReference], Set[str]]:
        """読み込んだ非○○制約を取得"""
        return self.forbidden_cells
    
    def get_test_periods(self) -> Dict[Tuple[TimeSlot, ClassReference], Assignment]:
        """テスト期間の割り当て情報を取得"""
        return self._test_periods