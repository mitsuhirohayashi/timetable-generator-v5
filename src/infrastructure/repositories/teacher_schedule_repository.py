"""教師別時間割リポジトリ"""
import csv
import logging
from pathlib import Path
from typing import List

from ..config.path_config import path_config
from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.value_objects.time_slot import TimeSlot


class TeacherScheduleRepository:
    """教師別時間割の入出力を担当"""
    
    def __init__(self, use_enhanced_features: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_enhanced_features = use_enhanced_features
        self.days = ["月", "火", "水", "木", "金"]
        self.periods = range(1, 7)
    
    def save_teacher_schedule(
        self,
        schedule: Schedule,
        school: School,
        filename: str = "teacher_schedule.csv"
    ) -> None:
        """教師別時間割をCSVファイルに保存"""
        file_path = self._resolve_file_path(filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                
                # ヘッダー行
                self._write_header(writer)
                
                # 校時行
                self._write_periods(writer)
                
                # 各教師の行
                self._write_teachers(writer, schedule, school)
                
                # 拡張機能が有効な場合は会議時間の行も追加
                if self.use_enhanced_features:
                    self._add_meeting_rows(writer)
            
            log_msg = "教師別時間割を保存しました"
            if self.use_enhanced_features:
                log_msg += "（拡張機能対応）"
            self.logger.info(f"{log_msg}: {file_path}")
            
        except Exception as e:
            self.logger.error(f"教師別時間割保存エラー: {e}")
            raise
    
    def _resolve_file_path(self, filename: str) -> Path:
        """ファイルパスを解決"""
        if filename == "teacher_schedule.csv":
            return path_config.get_output_path(filename)
        elif filename.startswith("/"):
            return Path(filename)
        else:
            return Path(filename)
    
    def _write_header(self, writer: csv.writer) -> None:
        """ヘッダー行を書き込む"""
        header = ["教員"]
        for day in self.days:
            for _ in self.periods:
                header.append(day)
        writer.writerow(header)
    
    def _write_periods(self, writer: csv.writer) -> None:
        """校時行を書き込む"""
        period_row = [""]
        for _ in self.days:
            for period in self.periods:
                period_row.append(str(period))
        writer.writerow(period_row)
    
    def _write_teachers(
        self,
        writer: csv.writer,
        schedule: Schedule,
        school: School
    ) -> None:
        """各教師の行を書き込む"""
        all_teachers = list(school.get_all_teachers())
        
        for teacher in sorted(all_teachers, key=lambda t: t.name):
            row = [teacher.name]
            
            for day in self.days:
                for period in self.periods:
                    time_slot = TimeSlot(day, period)
                    
                    # この時間の授業を探す
                    cell_content = self._find_teacher_assignment(
                        schedule, school, teacher, time_slot
                    )
                    row.append(cell_content)
            
            writer.writerow(row)
    
    def _find_teacher_assignment(
        self,
        schedule: Schedule,
        school: School,
        teacher,
        time_slot: TimeSlot
    ) -> str:
        """教師の特定時間の授業を探す"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and \
               assignment.teacher.name == teacher.name:
                # クラス表示形式の選択
                if self.use_enhanced_features:
                    return f"{class_ref.short_name_alt}"
                else:
                    return f"{class_ref.grade}-{class_ref.class_number}"
        
        return ""
    
    def _add_meeting_rows(self, writer: csv.writer) -> None:
        """会議時間の行を追加（拡張機能）"""
        # 会議情報（既存の実装から）
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
        for teacher, schedule_data in meetings.items():
            writer.writerow([teacher] + schedule_data)