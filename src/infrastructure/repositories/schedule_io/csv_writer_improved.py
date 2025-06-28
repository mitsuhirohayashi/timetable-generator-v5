"""CSV形式のスケジュール書き込み（改良版）- 入力形式を保持"""
import csv
import logging
from pathlib import Path
from typing import List, Optional, Set

from .base import ScheduleWriter
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....shared.utils.csv_operations import CSVOperations
from ....shared.mixins.logging_mixin import LoggingMixin


class CSVScheduleWriterImproved(LoggingMixin, ScheduleWriter):
    """CSV形式のスケジュール書き込み（入力形式保持版）"""
    
    def __init__(self, use_support_hours: bool = False, school: Optional[School] = None):
        super().__init__()
        self.use_support_hours = use_support_hours
        self.school = school
        self.days = ["月", "火", "水", "木", "金"]
        self.periods = range(1, 7)
        
        # 標準的なクラス順序（input.csvの順序を保持）
        self.standard_class_order = [
            # 1年生
            ClassReference(1, 1), ClassReference(1, 2), ClassReference(1, 3),
            ClassReference(1, 5),  # 1年5組
            ClassReference(1, 6), ClassReference(1, 7),
            # 2年生
            ClassReference(2, 1), ClassReference(2, 2), ClassReference(2, 3),
            ClassReference(2, 5),  # 2年5組
            ClassReference(2, 6), ClassReference(2, 7),
            # 空白行
            None,
            # 3年生
            ClassReference(3, 1), ClassReference(3, 2), ClassReference(3, 3),
            ClassReference(3, 5),  # 3年5組
            ClassReference(3, 6), ClassReference(3, 7),
        ]
    
    def write(self, schedule: Schedule, file_path: Path) -> None:
        """スケジュールをCSVファイルに書き込む（入力形式を保持）"""
        # 親ディレクトリが存在しない場合は作成
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # データを準備
            all_rows = []
            
            # ヘッダー行を追加
            self._add_header(all_rows)
            
            # 校時行を追加
            self._add_periods(all_rows)
            
            # 各クラスの行を追加（input.csvと同じ順序）
            self._add_classes_in_order(all_rows, schedule)
            
            # CSVOperationsを使用して書き込み
            CSVOperations.write_csv_raw(str(file_path), all_rows)
                
            self.logger.info(f"スケジュールを保存しました（入力形式保持）: {file_path}")
            
        except Exception as e:
            self.logger.error(f"スケジュール保存エラー: {e}")
            raise
    
    def _add_header(self, rows: List[List[str]]) -> None:
        """ヘッダー行を追加"""
        header = ["基本時間割"]
        for day in self.days:
            for _ in self.periods:
                header.append(day)
        rows.append(header)
    
    def _add_periods(self, rows: List[List[str]]) -> None:
        """校時行を追加"""
        period_row = [""]
        for _ in self.days:
            for period in self.periods:
                period_row.append(str(period))
        rows.append(period_row)
    
    def _add_classes_in_order(self, rows: List[List[str]], schedule: Schedule) -> None:
        """各クラスの行を入力ファイルと同じ順序で追加"""
        # スケジュールに存在するクラスを取得
        existing_classes = self._get_all_classes_from_schedule(schedule)
        
        # Schoolオブジェクトがある場合は、そこからも全クラスを取得
        if self.school:
            all_school_classes = set(self.school.get_all_classes())
            self.logger.info(f"Schoolオブジェクトから{len(all_school_classes)}クラスを取得")
        else:
            # Schoolオブジェクトがない場合は、標準クラス一覧を全て含める
            all_school_classes = set(c for c in self.standard_class_order if c is not None)
            self.logger.info("Schoolオブジェクト未設定。標準クラス一覧を使用（5組を含む）")
        
        # 標準順序に従って出力
        output_count = 0
        for class_ref in self.standard_class_order:
            if class_ref is None:
                # 空白行
                rows.append([""] * 31)
                self.logger.debug("空白行を追加")
            else:
                # クラスが存在する場合のみ出力
                if class_ref in all_school_classes or class_ref in existing_classes:
                    row = self._create_class_row(class_ref, schedule)
                    rows.append(row)
                    output_count += 1
                    self.logger.debug(f"{class_ref.full_name}を出力")
                else:
                    # クラスが見つからない場合も空の行を出力（形式を保持）
                    self.logger.warning(f"{class_ref.full_name}が見つかりません。空の行を出力")
                    row = [class_ref.full_name] + [""] * 30
                    rows.append(row)
                    output_count += 1
        
        self.logger.info(f"合計{output_count}クラスを出力（5組を含む）")
        
        # 標準順序にない追加クラスがある場合は警告
        extra_classes = set()
        for c in all_school_classes.union(existing_classes):
            if c not in self.standard_class_order:
                extra_classes.add(c)
        
        if extra_classes:
            self.logger.warning(f"標準順序にないクラス: {[c.full_name for c in extra_classes]}")
            # 追加クラスも出力
            for class_ref in sorted(extra_classes, key=lambda c: (c.grade, c.class_number)):
                row = self._create_class_row(class_ref, schedule)
                rows.append(row)
    
    def _create_class_row(self, class_ref: ClassReference, schedule: Schedule) -> List[str]:
        """クラスの行データを作成"""
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
        
        return row
    
    def _get_all_classes_from_schedule(self, schedule: Schedule) -> Set[ClassReference]:
        """スケジュールから全てのクラスを抽出"""
        classes = set()
        for _, assignment in schedule.get_all_assignments():
            classes.add(assignment.class_ref)
        return classes
    
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