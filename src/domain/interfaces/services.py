"""サービスインターフェース定義

ドメイン層のサービスインターフェースを定義。
アプリケーション層やインフラ層から利用される。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Set

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment


class IScheduleGenerator(ABC):
    """スケジュール生成サービスのインターフェース"""
    
    @abstractmethod
    def generate(self, school: School, initial_schedule: Optional[Schedule] = None) -> Schedule:
        """スケジュールを生成"""
        pass
    
    @abstractmethod
    def get_statistics(self) -> Dict[str, any]:
        """生成統計を取得"""
        pass


class IConstraintChecker(ABC):
    """制約チェッカーのインターフェース"""
    
    @abstractmethod
    def check_constraints(self, schedule: Schedule, school: School) -> List[Dict[str, any]]:
        """全ての制約をチェック"""
        pass
    
    @abstractmethod
    def check_specific_constraint(self, schedule: Schedule, school: School, constraint_type: str) -> List[Dict[str, any]]:
        """特定の制約をチェック"""
        pass


class IScheduleOptimizer(ABC):
    """スケジュール最適化サービスのインターフェース"""
    
    @abstractmethod
    def optimize(self, schedule: Schedule, school: School, iterations: int = 100) -> Schedule:
        """スケジュールを最適化"""
        pass
    
    @abstractmethod
    def get_optimization_score(self, schedule: Schedule, school: School) -> float:
        """最適化スコアを計算"""
        pass


class IEmptySlotFiller(ABC):
    """空きスロット埋めサービスのインターフェース"""
    
    @abstractmethod
    def fill_empty_slots(self, schedule: Schedule, school: School) -> Schedule:
        """空きスロットを埋める"""
        pass
    
    @abstractmethod
    def get_fill_statistics(self) -> Dict[str, int]:
        """埋め統計を取得"""
        pass


class IGrade5Synchronizer(ABC):
    """5組同期サービスのインターフェース"""
    
    @abstractmethod
    def synchronize(self, schedule: Schedule, school: School) -> bool:
        """5組を同期"""
        pass
    
    @abstractmethod
    def is_synchronized(self, schedule: Schedule) -> bool:
        """同期されているかチェック"""
        pass


class IExchangeClassSynchronizer(ABC):
    """交流学級同期サービスのインターフェース"""
    
    @abstractmethod
    def synchronize(self, schedule: Schedule, school: School) -> bool:
        """交流学級を同期"""
        pass
    
    @abstractmethod
    def validate_jiritsu_placement(self, schedule: Schedule) -> List[str]:
        """自立活動の配置を検証"""
        pass


class ITeacherWorkloadBalancer(ABC):
    """教師負担バランスサービスのインターフェース"""
    
    @abstractmethod
    def balance_workload(self, schedule: Schedule, school: School) -> Schedule:
        """教師の負担をバランス"""
        pass
    
    @abstractmethod
    def calculate_workload(self, teacher: Teacher, schedule: Schedule) -> Dict[str, float]:
        """教師の負担を計算"""
        pass