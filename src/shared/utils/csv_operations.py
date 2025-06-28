"""CSV操作の共通ユーティリティ

複数のモジュールで使用されるCSV読み書きの共通処理を提供します。
"""
import csv
import os
from typing import List, Dict, Any, Optional, TextIO
from pathlib import Path


class CSVOperations:
    """CSV操作の共通処理"""
    
    @staticmethod
    def read_csv(
        file_path: str,
        encoding: str = 'utf-8-sig',
        skip_empty_rows: bool = True,
        normalize_headers: bool = True
    ) -> List[Dict[str, str]]:
        """CSVファイルを読み込む
        
        Args:
            file_path: ファイルパス
            encoding: エンコーディング（デフォルト: utf-8-sig）
            skip_empty_rows: 空行をスキップするか
            normalize_headers: ヘッダーを正規化するか
            
        Returns:
            辞書のリスト（各行が辞書）
            
        Raises:
            FileNotFoundError: ファイルが存在しない場合
            ValueError: CSVの形式が不正な場合
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")
        
        rows = []
        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            
            # ヘッダーの正規化
            if normalize_headers and reader.fieldnames:
                reader.fieldnames = [
                    CSVOperations._normalize_header(h) 
                    for h in reader.fieldnames
                ]
            
            for row in reader:
                # 空行のスキップ
                if skip_empty_rows and all(
                    not value.strip() for value in row.values()
                ):
                    continue
                
                # 値の前後の空白を削除
                normalized_row = {
                    key: value.strip() if value else ''
                    for key, value in row.items()
                }
                rows.append(normalized_row)
        
        return rows
    
    @staticmethod
    def write_csv(
        file_path: str,
        rows: List[Dict[str, Any]],
        fieldnames: Optional[List[str]] = None,
        encoding: str = 'utf-8-sig',
        ensure_dir: bool = True
    ) -> None:
        """CSVファイルに書き込む
        
        Args:
            file_path: ファイルパス
            rows: 書き込むデータ（辞書のリスト）
            fieldnames: フィールド名（省略時は最初の行から取得）
            encoding: エンコーディング
            ensure_dir: ディレクトリが存在しない場合に作成するか
        """
        if ensure_dir:
            dir_path = os.path.dirname(file_path)
            if dir_path:  # ディレクトリパスが空でない場合のみ
                os.makedirs(dir_path, exist_ok=True)
        
        if not fieldnames and rows:
            fieldnames = list(rows[0].keys())
        
        with open(file_path, 'w', encoding=encoding, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    
    @staticmethod
    def read_csv_raw(
        file_path: str,
        encoding: str = 'utf-8-sig'
    ) -> List[List[str]]:
        """CSVファイルを生の形式で読み込む
        
        Args:
            file_path: ファイルパス
            encoding: エンコーディング
            
        Returns:
            行のリスト（各行は文字列のリスト）
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")
        
        rows = []
        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(row)
        
        return rows
    
    @staticmethod
    def write_csv_raw(
        file_path: str,
        rows: List[List[Any]],
        encoding: str = 'utf-8-sig',
        ensure_dir: bool = True
    ) -> None:
        """CSVファイルに生の形式で書き込む
        
        Args:
            file_path: ファイルパス
            rows: 書き込むデータ（リストのリスト）
            encoding: エンコーディング
            ensure_dir: ディレクトリが存在しない場合に作成するか
        """
        if ensure_dir:
            dir_path = os.path.dirname(file_path)
            if dir_path:  # ディレクトリパスが空でない場合のみ
                os.makedirs(dir_path, exist_ok=True)
        
        with open(file_path, 'w', encoding=encoding, newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
    
    @staticmethod
    def append_to_csv(
        file_path: str,
        row: Dict[str, Any],
        fieldnames: Optional[List[str]] = None,
        encoding: str = 'utf-8-sig'
    ) -> None:
        """CSVファイルに行を追加
        
        Args:
            file_path: ファイルパス
            row: 追加する行（辞書）
            fieldnames: フィールド名
            encoding: エンコーディング
        """
        file_exists = os.path.exists(file_path)
        
        if not fieldnames:
            fieldnames = list(row.keys())
        
        with open(file_path, 'a', encoding=encoding, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # ファイルが存在しない場合はヘッダーも書き込む
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(row)
    
    @staticmethod
    def _normalize_header(header: str) -> str:
        """ヘッダーを正規化
        
        Args:
            header: ヘッダー文字列
            
        Returns:
            正規化されたヘッダー
        """
        # 前後の空白を削除
        header = header.strip()
        
        # BOMを削除
        if header.startswith('\ufeff'):
            header = header[1:]
        
        # 全角スペースを半角に変換
        header = header.replace('　', ' ')
        
        return header
    
    @staticmethod
    def merge_csv_files(
        file_paths: List[str],
        output_path: str,
        encoding: str = 'utf-8-sig',
        skip_headers: bool = True
    ) -> None:
        """複数のCSVファイルをマージ
        
        Args:
            file_paths: マージするファイルパスのリスト
            output_path: 出力ファイルパス
            encoding: エンコーディング
            skip_headers: 2つ目以降のファイルのヘッダーをスキップするか
        """
        all_rows = []
        fieldnames = None
        
        for i, file_path in enumerate(file_paths):
            rows = CSVOperations.read_csv_raw(file_path, encoding)
            
            if i == 0:
                # 最初のファイルはヘッダーを含めて全て追加
                all_rows.extend(rows)
                if rows:
                    fieldnames = rows[0]
            else:
                # 2つ目以降のファイル
                if skip_headers and rows:
                    # ヘッダーをスキップ
                    all_rows.extend(rows[1:])
                else:
                    all_rows.extend(rows)
        
        CSVOperations.write_csv_raw(output_path, all_rows, encoding)