"""ユースケースファクトリー - ユースケースの生成を管理"""
import logging
import os


class UseCaseFactory:
    """ユースケースのファクトリークラス
    
    環境変数や設定に基づいて適切なユースケース実装を返します。
    これにより、新旧の実装を安全に切り替えることができます。
    """
    
    @staticmethod
    def create_generate_schedule_use_case():
        """GenerateScheduleUseCaseのインスタンスを作成
        
        環境変数 USE_REFACTORED_USE_CASE が設定されている場合は
        リファクタリング版を使用し、それ以外は従来版を使用します。
        """
        logger = logging.getLogger(__name__)
        use_refactored = os.environ.get('USE_REFACTORED_USE_CASE', 'true').lower() != 'false'
        
        if use_refactored:
            logger.info("リファクタリング版のGenerateScheduleUseCaseを使用します")
            from .generate_schedule_use_case_refactored import GenerateScheduleUseCaseRefactored
            return GenerateScheduleUseCaseRefactored()
        else:
            logger.info("従来版のGenerateScheduleUseCaseを使用します")
            from .generate_schedule import GenerateScheduleUseCase
            return GenerateScheduleUseCase()
    
    @staticmethod
    def create_validate_schedule_use_case():
        """ValidateScheduleUseCaseのインスタンスを作成"""
        from .validate_schedule_use_case import ValidateScheduleUseCase
        return ValidateScheduleUseCase()