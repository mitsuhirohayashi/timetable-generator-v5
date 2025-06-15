"""入力CSVファイルの前処理を行うモジュール

特殊な表記（例：17自、26自など）を正しい形式に変換する
"""
import re
import csv
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class InputPreprocessor:
    """入力CSVファイルの前処理を行うクラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 特殊表記のパターン
        # 例: 17自 -> 1年7組の自立
        self.special_notation_pattern = re.compile(r'^(\d)(\d)(.)$')
        
    def preprocess_csv(self, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """CSVファイルを前処理する
        
        Args:
            input_path: 入力CSVファイルのパス
            output_path: 出力CSVファイルのパス（省略時は一時ファイル）
            
        Returns:
            前処理済みCSVファイルのパス
        """
        if output_path is None:
            output_path = input_path.parent / f"preprocessed_{input_path.name}"
        
        try:
            with open(input_path, 'r', encoding='utf-8') as infile:
                reader = csv.reader(infile)
                rows = list(reader)
            
            # ヘッダー行を保持
            header_rows = rows[:2] if len(rows) >= 2 else rows
            data_rows = rows[2:] if len(rows) > 2 else []
            
            # データ行を処理
            processed_rows = []
            for row in data_rows:
                if self._is_valid_class_row(row):
                    processed_row = self._process_row(row)
                    processed_rows.append(processed_row)
                else:
                    processed_rows.append(row)
            
            # 結果を書き出し
            with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.writer(outfile)
                writer.writerows(header_rows)
                writer.writerows(processed_rows)
            
            self.logger.info(f"入力ファイルを前処理しました: {input_path} -> {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"前処理エラー: {e}")
            raise
    
    def _is_valid_class_row(self, row: List[str]) -> bool:
        """有効なクラス行かチェック"""
        if not row or not row[0].strip():
            return False
        
        # クラス名のパターン（例：1年1組、2年5組）
        class_pattern = re.compile(r'^\d年\d組$')
        return bool(class_pattern.match(row[0].strip()))
    
    def _process_row(self, row: List[str]) -> List[str]:
        """行を処理して特殊表記を変換"""
        processed_row = [row[0]]  # クラス名はそのまま
        
        for cell in row[1:]:
            processed_cell = self._process_cell(cell.strip())
            processed_row.append(processed_cell)
        
        return processed_row
    
    def _process_cell(self, cell: str) -> str:
        """セルの内容を処理して特殊表記を変換"""
        if not cell:
            return cell
        
        # 特殊表記のチェック（例：17自、26自）
        match = self.special_notation_pattern.match(cell)
        if match:
            grade = match.group(1)
            class_num = match.group(2)
            subject = match.group(3)
            
            # ログに変換情報を記録
            self.logger.debug(f"特殊表記を検出: {cell} -> {grade}年{class_num}組の{subject}")
            
            # この特殊表記は無効なので空欄にする
            # （正しい配置は別途処理される）
            return ""
        
        return cell
    
    def extract_special_assignments(self, input_path: Path) -> Dict[Tuple[str, int], Dict[str, str]]:
        """特殊表記から割り当て情報を抽出する
        
        Returns:
            {(day, period): {class_ref: subject}} の辞書
        """
        assignments = {}
        
        try:
            with open(input_path, 'r', encoding='utf-8') as infile:
                reader = csv.reader(infile)
                rows = list(reader)
            
            if len(rows) < 3:
                return assignments
            
            # タイムスロット情報を取得
            time_slots = self._parse_time_slots(rows[1])
            
            # 各クラスの行を処理
            for row in rows[2:]:
                if not self._is_valid_class_row(row):
                    continue
                
                class_ref = row[0].strip()
                
                for i, cell in enumerate(row[1:], 0):
                    if i >= len(time_slots):
                        break
                    
                    cell = cell.strip()
                    if not cell:
                        continue
                    
                    # 特殊表記のチェック
                    match = self.special_notation_pattern.match(cell)
                    if match:
                        grade = match.group(1)
                        class_num = match.group(2) 
                        subject = match.group(3)
                        
                        # 対象クラスを構築
                        target_class = f"{grade}年{class_num}組"
                        day, period = time_slots[i]
                        
                        key = (day, period)
                        if key not in assignments:
                            assignments[key] = {}
                        
                        assignments[key][target_class] = subject
                        
                        self.logger.info(
                            f"特殊割り当てを抽出: {day}曜{period}限 - "
                            f"{target_class}に{subject}を配置"
                        )
            
            return assignments
            
        except Exception as e:
            self.logger.error(f"特殊割り当て抽出エラー: {e}")
            return {}
    
    def _parse_time_slots(self, period_row: List[str]) -> List[Tuple[str, int]]:
        """期間行からタイムスロットを解析"""
        time_slots = []
        days = ["月", "火", "水", "木", "金"]
        
        for i, period_str in enumerate(period_row[1:]):
            if period_str.strip().isdigit():
                day_index = i // 6
                period = int(period_str.strip())
                if day_index < len(days):
                    time_slots.append((days[day_index], period))
        
        return time_slots