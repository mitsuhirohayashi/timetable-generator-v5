"""自立活動配置サービスのインターフェース"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference


@dataclass
class JiritsuRequirement:
    """自立活動の要件"""
    exchange_class: ClassReference
    parent_class: ClassReference
    periods_per_week: int
    allowed_parent_subjects: List[str]
    
    def __repr__(self) -> str:
        return (f"JiritsuRequirement({self.exchange_class} <- {self.parent_class}, "
                f"{self.periods_per_week}コマ/週, 親学級教科: {self.allowed_parent_subjects})")


class JiritsuPlacementService(ABC):
    """自立活動配置サービスのインターフェース"""
    
    @abstractmethod
    def analyze_requirements(self, school: School, schedule: Schedule) -> List[JiritsuRequirement]:
        """自立活動の要件を分析
        
        Args:
            school: 学校情報
            schedule: 現在のスケジュール
            
        Returns:
            自立活動要件のリスト
        """
        pass
    
    @abstractmethod
    def place_activities(self, schedule: Schedule, school: School, 
                        requirements: List[JiritsuRequirement]) -> int:
        """自立活動を配置
        
        Args:
            schedule: 配置先のスケジュール
            school: 学校情報
            requirements: 自立活動要件のリスト
            
        Returns:
            配置した自立活動の数
        """
        pass
    
    @abstractmethod
    def can_place_jiritsu(self, schedule: Schedule, school: School,
                         time_slot: TimeSlot, requirement: JiritsuRequirement) -> bool:
        """特定の時間枠に自立活動を配置可能かチェック
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: 配置先の時間枠
            requirement: 自立活動要件
            
        Returns:
            配置可能な場合True
        """
        pass