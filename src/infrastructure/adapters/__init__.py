"""インフラ層のアダプター実装

ドメイン層のインターフェースを実装し、既存のインフラ実装をラップする。
"""

from .teacher_absence_adapter import TeacherAbsenceAdapter
from .configuration_adapter import ConfigurationAdapter
from .followup_parser_adapter import FollowUpParserAdapter
from .path_configuration_adapter import PathConfigurationAdapter
from .csp_configuration_adapter import CSPConfigurationAdapter

__all__ = [
    'TeacherAbsenceAdapter',
    'ConfigurationAdapter',
    'FollowUpParserAdapter',
    'PathConfigurationAdapter',
    'CSPConfigurationAdapter',
]