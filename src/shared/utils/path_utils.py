"""パス操作の共通ユーティリティ

ファイルパスやディレクトリパスの操作に関する共通処理を提供します。
"""
import os
from pathlib import Path
from typing import Optional, List, Union


class PathUtils:
    """パス操作ユーティリティ"""
    
    # プロジェクトルートの検出用マーカーファイル
    ROOT_MARKERS = ['.git', 'setup.py', 'requirements.txt', 'README.md']
    
    @staticmethod
    def get_project_root() -> Path:
        """プロジェクトルートディレクトリを取得
        
        Returns:
            プロジェクトルートのPathオブジェクト
            
        Raises:
            RuntimeError: プロジェクトルートが見つからない場合
        """
        current = Path(__file__).resolve()
        
        # 上位ディレクトリを探索
        for parent in current.parents:
            # マーカーファイルをチェック
            for marker in PathUtils.ROOT_MARKERS:
                if (parent / marker).exists():
                    return parent
        
        raise RuntimeError("プロジェクトルートが見つかりません")
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]) -> Path:
        """ディレクトリが存在することを保証
        
        Args:
            path: ディレクトリパス
            
        Returns:
            作成されたディレクトリのPathオブジェクト
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_data_dir() -> Path:
        """データディレクトリを取得
        
        Returns:
            データディレクトリのPathオブジェクト
        """
        root = PathUtils.get_project_root()
        return root / 'data'
    
    @staticmethod
    def get_config_dir() -> Path:
        """設定ディレクトリを取得
        
        Returns:
            設定ディレクトリのPathオブジェクト
        """
        return PathUtils.get_data_dir() / 'config'
    
    @staticmethod
    def get_input_dir() -> Path:
        """入力ディレクトリを取得
        
        Returns:
            入力ディレクトリのPathオブジェクト
        """
        return PathUtils.get_data_dir() / 'input'
    
    @staticmethod
    def get_output_dir() -> Path:
        """出力ディレクトリを取得
        
        Returns:
            出力ディレクトリのPathオブジェクト
        """
        return PathUtils.get_data_dir() / 'output'
    
    @staticmethod
    def get_logs_dir() -> Path:
        """ログディレクトリを取得
        
        Returns:
            ログディレクトリのPathオブジェクト
        """
        root = PathUtils.get_project_root()
        return PathUtils.ensure_dir(root / 'logs')
    
    @staticmethod
    def resolve_path(path: Union[str, Path], base: Optional[Path] = None) -> Path:
        """相対パスを解決
        
        Args:
            path: パス
            base: ベースディレクトリ（省略時はプロジェクトルート）
            
        Returns:
            絶対パスのPathオブジェクト
        """
        path = Path(path)
        
        if path.is_absolute():
            return path
        
        if base is None:
            base = PathUtils.get_project_root()
        else:
            base = Path(base)
        
        return (base / path).resolve()
    
    @staticmethod
    def find_files(
        pattern: str,
        directory: Optional[Union[str, Path]] = None,
        recursive: bool = True
    ) -> List[Path]:
        """パターンに一致するファイルを検索
        
        Args:
            pattern: ファイル名パターン（glob形式）
            directory: 検索ディレクトリ（省略時はプロジェクトルート）
            recursive: サブディレクトリも検索するか
            
        Returns:
            マッチしたファイルのリスト
        """
        if directory is None:
            directory = PathUtils.get_project_root()
        else:
            directory = Path(directory)
        
        if recursive and '**' not in pattern:
            pattern = f"**/{pattern}"
        
        return list(directory.glob(pattern))
    
    @staticmethod
    def backup_file(
        file_path: Union[str, Path],
        backup_suffix: str = '.bak',
        timestamp: bool = True
    ) -> Path:
        """ファイルのバックアップを作成
        
        Args:
            file_path: バックアップするファイル
            backup_suffix: バックアップファイルの接尾辞
            timestamp: タイムスタンプを付加するか
            
        Returns:
            バックアップファイルのパス
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが存在しません: {file_path}")
        
        if timestamp:
            from datetime import datetime
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{file_path.stem}_{timestamp_str}{backup_suffix}{file_path.suffix}"
        else:
            backup_name = f"{file_path.stem}{backup_suffix}{file_path.suffix}"
        
        backup_path = file_path.parent / backup_name
        
        # バックアップを作成
        import shutil
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """ファイル名として使用できない文字を除去
        
        Args:
            filename: ファイル名
            
        Returns:
            クリーンなファイル名
        """
        # Windowsで使用できない文字
        invalid_chars = '<>:"|?*'
        # スラッシュとバックスラッシュ
        invalid_chars += '/\\'
        
        clean_name = filename
        for char in invalid_chars:
            clean_name = clean_name.replace(char, '_')
        
        # 先頭と末尾の空白とピリオドを削除
        clean_name = clean_name.strip(' .')
        
        # 空になった場合はデフォルト名を返す
        if not clean_name:
            clean_name = 'unnamed'
        
        return clean_name
    
    @staticmethod
    def get_relative_path(path: Union[str, Path], base: Optional[Path] = None) -> Path:
        """プロジェクトルートからの相対パスを取得
        
        Args:
            path: パス
            base: ベースディレクトリ（省略時はプロジェクトルート）
            
        Returns:
            相対パス
        """
        path = Path(path).resolve()
        
        if base is None:
            base = PathUtils.get_project_root()
        else:
            base = Path(base).resolve()
        
        try:
            return path.relative_to(base)
        except ValueError:
            # ベースディレクトリの外側の場合は絶対パスを返す
            return path