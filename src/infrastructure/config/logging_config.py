"""ロギング設定の統一管理

このモジュールは、システム全体のロギング設定を一元管理します。
"""
import logging
import logging.handlers
from pathlib import Path
from typing import Optional


class LoggingConfig:
    """ロギング設定クラス"""
    
    # ログレベルの定義
    LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    # モジュール別のログレベル設定
    MODULE_LEVELS = {
        # 重要なモジュールは詳細ログ
        'src.application.use_cases': 'INFO',
        'src.domain.services': 'INFO',
        'src.domain.constraints': 'WARNING',  # 制約違反のみ
        
        # インフラ層は警告以上のみ
        'src.infrastructure.repositories': 'WARNING',
        'src.infrastructure.parsers': 'WARNING',
        
        # CSP関連は情報レベル
        'src.domain.services.csp': 'INFO',
        
        # その他はエラーのみ
        'src': 'ERROR'
    }
    
    @classmethod
    def setup_logging(cls, 
                     log_level: str = 'INFO',
                     log_file: Optional[Path] = None,
                     console_output: bool = True,
                     simple_format: bool = False) -> None:
        """ロギングを設定
        
        Args:
            log_level: デフォルトのログレベル
            log_file: ログファイルのパス（Noneの場合はファイル出力なし）
            console_output: コンソール出力を有効にするか
            simple_format: シンプルなフォーマットを使用するか
        """
        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(cls.LEVELS.get(log_level, logging.INFO))
        
        # 既存のハンドラーをクリア
        root_logger.handlers.clear()
        
        # フォーマッターの設定
        if simple_format:
            formatter = logging.Formatter(
                '%(levelname)s: %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        # コンソールハンドラー
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # ファイルハンドラー
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # モジュール別のログレベル設定
        for module_name, level_name in cls.MODULE_LEVELS.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(cls.LEVELS.get(level_name, logging.INFO))
    
    @classmethod
    def setup_production_logging(cls) -> None:
        """本番環境用のロギング設定"""
        cls.setup_logging(
            log_level='WARNING',
            log_file=Path('logs/timetable_generation.log'),
            console_output=True,
            simple_format=True
        )
    
    @classmethod
    def setup_development_logging(cls) -> None:
        """開発環境用のロギング設定"""
        cls.setup_logging(
            log_level='DEBUG',
            log_file=Path('logs/debug.log'),
            console_output=True,
            simple_format=False
        )
    
    @classmethod
    def setup_quiet_logging(cls) -> None:
        """静音モード（エラーのみ）"""
        cls.setup_logging(
            log_level='ERROR',
            log_file=None,
            console_output=True,
            simple_format=True
        )


def get_logger(name: str) -> logging.Logger:
    """統一されたロガーを取得
    
    Args:
        name: ロガー名（通常は__name__）
        
    Returns:
        設定済みのロガー
    """
    return logging.getLogger(name)