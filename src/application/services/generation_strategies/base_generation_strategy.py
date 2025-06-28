"""スケジュール生成戦略の基底クラス

全ての生成戦略が実装すべきインターフェースを定義します。
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School
    from ....domain.services.core.unified_constraint_system import UnifiedConstraintSystem


class BaseGenerationStrategy(ABC):
    """スケジュール生成戦略の基底クラス"""
    
    def __init__(self, constraint_system: 'UnifiedConstraintSystem'):
        self.constraint_system = constraint_system
    
    @abstractmethod
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 100,
        **kwargs
    ) -> 'Schedule':
        """スケジュールを生成する
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            max_iterations: 最大反復回数
            **kwargs: 戦略固有のパラメータ
            
        Returns:
            生成されたスケジュール
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """戦略の名前を取得"""
        pass
    
    def validate_schedule(self, schedule: 'Schedule', school: 'School') -> list:
        """スケジュールの妥当性を検証"""
        result = self.constraint_system.validate_schedule(schedule, school)
        return result.violations
    
    def log_violations(self, violations: list) -> None:
        """制約違反をログ出力"""
        if violations:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"制約違反が{len(violations)}件発生しています:")
            for v in violations[:5]:  # 最初の5件のみ表示
                logger.warning(f"  - {v}")