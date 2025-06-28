"""依存性注入コンテナ

Clean Architectureの依存性逆転の原則を実現するためのDIコンテナ。
インターフェースと実装のバインディングを管理する。
"""

import logging
from typing import Type, Dict, Any, Optional, Callable
from pathlib import Path

# インターフェース
from ..domain.interfaces.repositories import (
    IScheduleRepository,
    ISchoolRepository,
    ITeacherScheduleRepository,
    ITeacherMappingRepository,
    ITeacherAbsenceRepository
)
from ..domain.interfaces.services import (
    IScheduleGenerator,
    IConstraintChecker,
    IScheduleOptimizer,
    IEmptySlotFiller,
    IGrade5Synchronizer,
    IExchangeClassSynchronizer,
    ITeacherWorkloadBalancer
)
from ..domain.interfaces.path_configuration import IPathConfiguration
from ..domain.interfaces.followup_parser import IFollowUpParser
from ..domain.interfaces.configuration_reader import IConfigurationReader

# 実装
from .repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from .repositories.teacher_schedule_repository import TeacherScheduleRepository
from .repositories.teacher_mapping_repository import TeacherMappingRepository
from .repositories.teacher_absence_loader import TeacherAbsenceLoader
from .config.path_config import path_config
from .adapters.path_configuration_adapter import PathConfigurationAdapter
from .adapters.followup_parser_adapter import FollowUpParserAdapter
from .config.system_config_loader import SystemConfigLoader
from .config.path_manager import PathManager, get_path_manager
from .config.config_loader import ConfigLoader
from .config.constraint_loader import ConstraintLoader
from .parsers.input_preprocessor import InputPreprocessor

logger = logging.getLogger(__name__)


class DIContainer:
    """依存性注入コンテナ"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._services: Dict[Type, Callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self._initialized = True
        
        # デフォルトのバインディングを登録
        self._register_default_bindings()
    
    def _register_default_bindings(self):
        """デフォルトのインターフェースと実装のバインディングを登録"""
        
        # リポジトリのバインディング
        self.register(
            IScheduleRepository,
            lambda: CSVScheduleRepository(base_path=path_config.base_dir),
            singleton=True
        )
        
        self.register(
            ISchoolRepository,
            lambda: CSVSchoolRepository(base_path=path_config.config_dir),
            singleton=True
        )
        
        self.register(
            ITeacherScheduleRepository,
            lambda: TeacherScheduleRepository(),
            singleton=True
        )
        
        self.register(
            ITeacherMappingRepository,
            lambda: TeacherMappingRepository(base_path=path_config.config_dir),
            singleton=True
        )
        
        self.register(
            ITeacherAbsenceRepository,
            lambda: TeacherAbsenceLoader(),
            singleton=True
        )
        
        # パス設定とパーサーのバインディング
        self.register(
            IPathConfiguration,
            lambda: PathConfigurationAdapter(),
            singleton=True
        )
        
        self.register(
            IFollowUpParser,
            lambda: FollowUpParserAdapter(),
            singleton=True
        )
        
        # システム設定ローダーのバインディング
        self.register(
            IConfigurationReader,
            lambda: SystemConfigLoader(),
            singleton=True
        )
        
        # PathManagerのバインディング
        self.register(
            PathManager,
            lambda: PathManager(),
            singleton=True
        )
        
        # ConfigLoaderのバインディング
        self.register(
            ConfigLoader,
            lambda: ConfigLoader(self.resolve(IPathConfiguration).config_dir),
            singleton=True
        )
        
        # ConstraintLoaderのバインディング
        self.register(
            ConstraintLoader,
            lambda: ConstraintLoader(),
            singleton=True
        )
        
        # InputPreprocessorのバインディング
        self.register(
            InputPreprocessor,
            lambda: InputPreprocessor(),
            singleton=True
        )
        
        # サービスのバインディング（実装が利用可能になったら追加）
        # self.register(IScheduleGenerator, lambda: AdvancedCSPScheduleGenerator())
        # self.register(IConstraintChecker, lambda: UnifiedConstraintValidator())
        # など
    
    def register(self, interface: Type, factory: Callable, singleton: bool = False):
        """インターフェースと実装ファクトリを登録
        
        Args:
            interface: インターフェースの型
            factory: 実装インスタンスを生成するファクトリ関数
            singleton: シングルトンとして管理するか
        """
        self._services[interface] = (factory, singleton)
        logger.debug(f"Registered {interface.__name__} with {'singleton' if singleton else 'transient'} lifetime")
    
    def resolve(self, interface: Type) -> Any:
        """インターフェースから実装を解決
        
        Args:
            interface: インターフェースの型
            
        Returns:
            実装インスタンス
            
        Raises:
            ValueError: インターフェースが登録されていない場合
        """
        if interface not in self._services:
            raise ValueError(f"No implementation registered for {interface.__name__}")
        
        factory, is_singleton = self._services[interface]
        
        if is_singleton:
            if interface not in self._singletons:
                self._singletons[interface] = factory()
            return self._singletons[interface]
        else:
            return factory()
    
    def reset(self):
        """コンテナをリセット（主にテスト用）"""
        self._services.clear()
        self._singletons.clear()
        self._register_default_bindings()
    
    def override(self, interface: Type, factory: Callable, singleton: bool = False):
        """既存のバインディングを上書き（主にテスト用）
        
        Args:
            interface: インターフェースの型
            factory: 新しい実装ファクトリ
            singleton: シングルトンとして管理するか
        """
        if interface in self._singletons:
            del self._singletons[interface]
        self.register(interface, factory, singleton)


# グローバルインスタンス
container = DIContainer()


def get_container() -> DIContainer:
    """DIコンテナのインスタンスを取得"""
    return container


# 便利なヘルパー関数
def get_path_configuration() -> IPathConfiguration:
    """パス設定を取得"""
    return container.resolve(IPathConfiguration)


def get_followup_parser() -> IFollowUpParser:
    """Follow-upパーサーを取得"""
    return container.resolve(IFollowUpParser)


def get_teacher_absence_repository() -> ITeacherAbsenceRepository:
    """教師不在リポジトリを取得"""
    return container.resolve(ITeacherAbsenceRepository)


def get_configuration_reader():
    """設定読み込みサービスを取得（互換性のため）"""
    from .adapters.configuration_adapter import ConfigurationAdapter
    return ConfigurationAdapter(get_path_configuration().config_dir)


def get_csp_configuration():
    """互換性のためのヘルパー"""
    from .adapters.csp_configuration_adapter import CSPConfigurationAdapter
    return CSPConfigurationAdapter()


def get_path_manager() -> PathManager:
    """PathManagerを取得"""
    return container.resolve(PathManager)


def get_config_loader() -> ConfigLoader:
    """ConfigLoaderを取得"""
    return container.resolve(ConfigLoader)


def get_constraint_loader() -> ConstraintLoader:
    """ConstraintLoaderを取得"""
    return container.resolve(ConstraintLoader)


def get_input_preprocessor() -> InputPreprocessor:
    """InputPreprocessorを取得"""
    return container.resolve(InputPreprocessor)


def get_schedule_repository():
    """スケジュールリポジトリを取得"""
    return container.resolve(IScheduleRepository)