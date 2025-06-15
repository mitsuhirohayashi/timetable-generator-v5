"""CSV形式のスケジュール書き込み"""
import csv
import logging
from pathlib import Path
from typing import List, Optional

from .base import ScheduleWriter
from ....domain.entities.schedule import Schedule
from ....domain.value_objects.time_slot import TimeSlot, ClassReference


class CSVScheduleWriter(ScheduleWriter):
    """CSV形式のスケジュール書き込み"""
    
    def __init__(self, use_support_hours: bool = False):
        self.logger = logging.getLogger(__name__)
        self.use_support_hours = use_support_hours
        self.days = ["月", "火", "水", "木", "金"]
        self.periods = range(1, 7)
    
    def write(self, schedule: Schedule, file_path: Path) -> None:
        """スケジュールをCSVファイルに書き込む"""
        # 親ディレクトリが存在しない場合は作成
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                
                # ヘッダー行を書き込み
                self._write_header(writer)
                
                # 校時行を書き込み
                self._write_periods(writer)
                
                # 各クラスの行を書き込み
                self._write_classes(writer, schedule)
                
            self.logger.info(f"スケジュールを保存しました: {file_path}")
            
        except Exception as e:
            self.logger.error(f"スケジュール保存エラー: {e}")
            raise
    
    def _write_header(self, writer: csv.writer) -> None:
        """ヘッダー行を書き込む"""
        header = ["基本時間割"]
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
    
    def _write_classes(self, writer: csv.writer, schedule: Schedule) -> None:
        """各クラスの行を書き込む"""
        all_classes = self._get_all_classes_from_schedule(schedule)
        
        for class_ref in sorted(all_classes, key=lambda c: (c.grade, c.class_number)):
            row = [class_ref.full_name]
            
            # 各時間枠の割り当てを取得
            for day in self.days:
                for period in self.periods:
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        subject_name = self._get_subject_display(
                            assignment, time_slot, class_ref
                        )
                    else:
                        subject_name = ""
                    
                    row.append(subject_name)
            
            writer.writerow(row)
            
            # 2年7組の後に空白行を追加（既存の仕様を維持）
            if class_ref.full_name == "2年7組":
                self.logger.info("2年7組の後に空白行を追加します")
                writer.writerow([""] * len(row))
    
    def _get_all_classes_from_schedule(self, schedule: Schedule) -> List[ClassReference]:
        """スケジュールから全てのクラスを抽出"""
        classes = set()
        for _, assignment in schedule.get_all_assignments():
            classes.add(assignment.class_ref)
        return list(classes)
    
    def _get_subject_display(
        self,
        assignment,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> str:
        """教科の表示名を取得"""
        # 拡張機能が有効な場合の処理（将来の拡張用）
        if self.use_support_hours and class_ref.class_number == 5:
            # TODO: 支援時数表記の実装
            pass
        
        return assignment.subject.name