"""ファイルパス管理の一元化

プロジェクト全体で使用するファイルパスを管理する
"""
from pathlib import Path
from typing import Optional
import logging

class PathManager:
    """ファイルパス管理クラス"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """初期化
        
        Args:
            base_dir: ベースディレクトリ（デフォルトはプロジェクトルート）
        """
        if base_dir is None:
            # デフォルトはこのファイルから3階層上（プロジェクトルート）
            base_dir = Path(__file__).parent.parent.parent.parent
        
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / "data"
        self.config_dir = self.data_dir / "config"
        self.input_dir = self.data_dir / "input"
        self.output_dir = self.data_dir / "output"
        self.temp_dir = self.base_dir / "temp"
        self.logs_dir = self.base_dir / "logs"
        
        self.logger = logging.getLogger(__name__)
        
        # 必要なディレクトリを作成
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """必要なディレクトリを作成"""
        directories = [
            self.data_dir,
            self.config_dir,
            self.input_dir,
            self.output_dir,
            self.temp_dir,
            self.logs_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_config_path(self, filename: str) -> Path:
        """設定ファイルのパスを取得
        
        Args:
            filename: ファイル名
            
        Returns:
            Path: 設定ファイルのフルパス
        """
        return self.config_dir / filename
    
    def get_input_path(self, filename: str) -> Path:
        """入力ファイルのパスを取得
        
        Args:
            filename: ファイル名
            
        Returns:
            Path: 入力ファイルのフルパス
        """
        return self.input_dir / filename
    
    def get_output_path(self, filename: str) -> Path:
        """出力ファイルのパスを取得（パス重複を防ぐ）
        
        Args:
            filename: ファイル名
            
        Returns:
            Path: 出力ファイルのフルパス
        """
        # 絶対パスの場合はそのまま返す
        if filename.startswith("/"):
            return Path(filename)
        
        # すでにdata/outputを含む場合は重複を避ける
        if filename.startswith("data/output/"):
            return self.base_dir / filename
        
        # outputディレクトリ内のファイルとして返す
        return self.output_dir / filename
    
    def get_temp_path(self, filename: str) -> Path:
        """一時ファイルのパスを取得
        
        Args:
            filename: ファイル名
            
        Returns:
            Path: 一時ファイルのフルパス
        """
        return self.temp_dir / filename
    
    def get_log_path(self, filename: str) -> Path:
        """ログファイルのパスを取得
        
        Args:
            filename: ファイル名
            
        Returns:
            Path: ログファイルのフルパス
        """
        return self.logs_dir / filename
    
    def resolve_path(self, path_str: str) -> Path:
        """文字列パスを適切なPathオブジェクトに解決
        
        Args:
            path_str: パス文字列
            
        Returns:
            Path: 解決されたPath
        """
        # 絶対パスの場合
        if path_str.startswith("/"):
            return Path(path_str)
        
        # 相対パスの場合の処理
        path = Path(path_str)
        
        # dataで始まる場合の特別処理
        if path.parts[0] == "data" and len(path.parts) > 1:
            if path.parts[1] == "config":
                return self.config_dir / Path(*path.parts[2:])
            elif path.parts[1] == "input":
                return self.input_dir / Path(*path.parts[2:])
            elif path.parts[1] == "output":
                return self.output_dir / Path(*path.parts[2:])
        
        # その他の場合はbase_dirからの相対パス
        return self.base_dir / path
    
    def __str__(self) -> str:
        """文字列表現"""
        return f"PathManager(base={self.base_dir})"
    
    def log_paths(self) -> None:
        """現在のパス設定をログ出力"""
        self.logger.info(f"PathManager設定:")
        self.logger.info(f"  ベースディレクトリ: {self.base_dir}")
        self.logger.info(f"  データディレクトリ: {self.data_dir}")
        self.logger.info(f"  設定ディレクトリ: {self.config_dir}")
        self.logger.info(f"  入力ディレクトリ: {self.input_dir}")
        self.logger.info(f"  出力ディレクトリ: {self.output_dir}")
        self.logger.info(f"  一時ディレクトリ: {self.temp_dir}")
        self.logger.info(f"  ログディレクトリ: {self.logs_dir}")


# シングルトンインスタンス
_path_manager_instance = None

def get_path_manager() -> PathManager:
    """PathManagerのシングルトンインスタンスを取得
    
    Returns:
        PathManager: PathManagerインスタンス
    """
    global _path_manager_instance
    if _path_manager_instance is None:
        _path_manager_instance = PathManager()
    return _path_manager_instance