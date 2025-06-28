"""レガシー生成戦略

従来のアルゴリズムを使用したスケジュール生成戦略です。
後方互換性のために提供されています。
"""
import logging
from typing import Optional, TYPE_CHECKING

from .base_generation_strategy import BaseGenerationStrategy

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School


class LegacyStrategy(BaseGenerationStrategy):
    """レガシーアルゴリズムを使用した生成戦略"""
    
    def __init__(self, constraint_system):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        
    def get_name(self) -> str:
        return "legacy"
    
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 100,
        **kwargs
    ) -> 'Schedule':
        """レガシーアルゴリズムでスケジュールを生成"""
        self.logger.info("=== レガシーアルゴリズムを使用（非推奨）===")
        
        from ..generators.greedy_subject_placement_service import GreedySubjectPlacementService
        
        schedule = initial_schedule.clone()

        # 貪欲法で通常教科を配置
        placement_service = GreedySubjectPlacementService(
            constraint_validator=self.constraint_system
        )
        placement_service.place_subjects(schedule, school)

        # 空きスロットを埋める
        # empty_slot_filler = EmptySlotFiller(self.constraint_system)
        # empty_slot_filler.fill_empty_slots(schedule, school)

        return schedule