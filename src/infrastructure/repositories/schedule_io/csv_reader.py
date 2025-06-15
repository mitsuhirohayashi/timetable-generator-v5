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


class CSVScheduleReader(ScheduleReader):
    """CSV形式のスケジュール読み込み"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.forbidden_cells: Dict[Tuple[TimeSlot, ClassReference], Set[str]] = {}
        self._fixed_subjects = ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]
    
    def read(self, file_path: Path, school: Optional[School] = None) -> Schedule:
        """CSVファイルからスケジュールを読み込む"""
        schedule = Schedule()
        # 初期スケジュール読み込み時は固定科目保護を一時的に無効化
        schedule.disable_fixed_subject_protection()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                lines = list(reader)
            
            if len(lines) < 3:
                raise ValueError("CSVファイルの形式が正しくありません")
            
            # タイムスロットを解析
            time_slots = self._parse_time_slots(lines[1])
            
            # 各クラスのデータを読み込み
            for line in lines[2:]:
                if not self._is_valid_class_line(line):
                    continue
                
                class_ref = parse_class_reference(line[0].strip().replace('"', ''))
                if not class_ref:
                    continue
                
                self._process_class_assignments(
                    schedule, school, class_ref, line[1:], time_slots
                )
            
            self.logger.info(f"スケジュールを読み込みました: {file_path}")
            # 読み込み完了後に固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            return schedule
            
        except Exception as e:
            self.logger.error(f"スケジュール読み込みエラー: {e}")
            # エラー時も固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
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
            
            # 割り当てを作成
            assignment = Assignment(class_ref, subject, teacher)
            schedule.assign(time_slot, assignment)
            
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
        if school:
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher:
                return teacher
        
        # デフォルト教員名を設定
        if subject_name == "欠":
            return Teacher("欠課")
        else:
            return Teacher(f"{subject_name}担当")
    
    def get_forbidden_cells(self) -> Dict[Tuple[TimeSlot, ClassReference], Set[str]]:
        """読み込んだ非○○制約を取得"""
        return self.forbidden_cells