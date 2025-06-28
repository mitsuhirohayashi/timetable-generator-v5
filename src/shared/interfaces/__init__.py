"""共通インターフェース定義"""

from .repository_interface import RepositoryInterface
from .service_interface import ServiceInterface
from .validator_interface import ValidatorInterface

__all__ = [
    'RepositoryInterface',
    'ServiceInterface',
    'ValidatorInterface'
]