"""自立活動配置サービスのインターフェース"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from dataclasses import dataclass

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher


@dataclass
class JiritsuRequirement:
    """自立活動要件"""
    exchange_class: ClassReference
    parent_class: ClassReference
    hours_needed: int
    jiritsu_teacher: Teacher
    placed_slots: List[TimeSlot]


class JiritsuPlacementService(ABC):
    """自立活動配置サービスのインターフェース
    
    責務:
    - 自立活動要件の分析
    - 自立活動と親学級の数学/英語の同時配置
    - バックトラッキングによる最適配置
    """
    
    @abstractmethod
    def analyze_requirements(self, school: School, schedule: Schedule) -> List[JiritsuRequirement]:
        """自立活動要件を分析
        
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
            schedule: スケジュール
            school: 学校情報
            requirements: 自立活動要件のリスト
            
        Returns:
            配置した自立活動の数
        """
        pass
    
    @abstractmethod
    def find_feasible_slots(self, schedule: Schedule, school: School,
                           requirement: JiritsuRequirement) -> List[Tuple[TimeSlot, Subject, Teacher]]:
        """配置可能なスロットを探索
        
        Args:
            schedule: スケジュール
            school: 学校情報
            requirement: 自立活動要件
            
        Returns:
            配置可能なスロットのリスト（時間枠、親学級教科、親学級教師）
        """
        pass