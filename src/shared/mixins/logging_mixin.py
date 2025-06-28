"""ロギング機能を提供するミックスイン

クラスにロギング機能を追加するための共通ミックスインです。
"""
import logging
from typing import Optional, Any, Dict


class LoggingMixin:
    """ロギング機能を提供するミックスイン
    
    使用例:
        class MyClass(LoggingMixin):
            def __init__(self):
                super().__init__()
                self.logger.info("MyClassが初期化されました")
    """
    
    @property
    def logger(self) -> logging.Logger:
        """ロガーを取得
        
        クラス名を使用してロガーを作成します。
        """
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(
                f"{self.__class__.__module__}.{self.__class__.__name__}"
            )
        return self._logger
    
    def log_debug(self, message: str, *args, **kwargs) -> None:
        """デバッグログを出力"""
        self.logger.debug(message, *args, **kwargs)
    
    def log_info(self, message: str, *args, **kwargs) -> None:
        """情報ログを出力"""
        self.logger.info(message, *args, **kwargs)
    
    def log_warning(self, message: str, *args, **kwargs) -> None:
        """警告ログを出力"""
        self.logger.warning(message, *args, **kwargs)
    
    def log_error(self, message: str, *args, **kwargs) -> None:
        """エラーログを出力"""
        self.logger.error(message, *args, **kwargs)
    
    def log_exception(self, message: str, exc_info: bool = True) -> None:
        """例外ログを出力
        
        Args:
            message: ログメッセージ
            exc_info: スタックトレースを含めるか
        """
        self.logger.error(message, exc_info=exc_info)
    
    def log_operation_start(self, operation: str, details: Optional[Dict[str, Any]] = None) -> None:
        """操作開始のログを出力
        
        Args:
            operation: 操作名
            details: 詳細情報
        """
        message = f"{operation}を開始"
        if details:
            message += f" - {details}"
        self.log_info(message)
    
    def log_operation_end(
        self, 
        operation: str, 
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """操作終了のログを出力
        
        Args:
            operation: 操作名
            success: 成功したか
            details: 詳細情報
        """
        status = "成功" if success else "失敗"
        message = f"{operation}が{status}"
        if details:
            message += f" - {details}"
        
        if success:
            self.log_info(message)
        else:
            self.log_error(message)
    
    def log_performance(
        self,
        operation: str,
        elapsed_time: float,
        item_count: Optional[int] = None
    ) -> None:
        """パフォーマンス情報をログ出力
        
        Args:
            operation: 操作名
            elapsed_time: 経過時間（秒）
            item_count: 処理したアイテム数
        """
        message = f"{operation} - 処理時間: {elapsed_time:.3f}秒"
        if item_count is not None:
            rate = item_count / elapsed_time if elapsed_time > 0 else 0
            message += f" ({item_count}件, {rate:.1f}件/秒)"
        self.log_info(message)