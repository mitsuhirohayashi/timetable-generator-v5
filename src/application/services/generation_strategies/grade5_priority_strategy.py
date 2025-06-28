"""5組優先配置戦略

5組（特別支援学級）の授業を優先的に配置し、
その後で通常学級の授業を配置する戦略です。
"""
import logging
from typing import Optional, TYPE_CHECKING

from .base_generation_strategy import BaseGenerationStrategy

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School


class Grade5PriorityStrategy(BaseGenerationStrategy):
    """5組優先配置アルゴリズムを使用した生成戦略"""
    
    def __init__(self, constraint_system):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        
    def get_name(self) -> str:
        return "grade5_priority"
    
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 100,
        **kwargs
    ) -> 'Schedule':
        """5組優先配置アルゴリズムでスケジュールを生成"""
        self.logger.info("=== 5組優先配置アルゴリズムを使用 ===")
        
        from ....domain.services.implementations.synchronized_grade5_service import SynchronizedGrade5Service
        
        # 5組同期サービスを作成
        generator = SynchronizedGrade5Service()
        
        # 生成実行
        schedule = generator.generate(school, self.constraint_system.constraints, initial_schedule)
        
        # 検証
        violations = self.validate_schedule(schedule, school)
        if violations:
            self.logger.warning(f"{len(violations)}件の制約違反が発生しています")
            self.log_violations(violations)
        else:
            self.logger.info("✓ 全ての制約を満たすスケジュールを生成しました")
        
        return schedule