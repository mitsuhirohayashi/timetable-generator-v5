"""メタデータ収集サービス

テスト期間、教師不在情報、交流学級マッピングなどの
メタデータを収集・管理する責務を持つ。
"""
from typing import Dict, Set, List, Tuple
from collections import defaultdict
import logging

from ....domain.entities import Schedule
from ....domain.constraints.base import Constraint

logger = logging.getLogger(__name__)


class MetadataCollector:
    """時間割生成に必要なメタデータを収集"""
    
    def __init__(self):
        self.test_periods: Set[Tuple[str, str]] = set()
        self.teacher_absences: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        self.exchange_parent_map: Dict[str, str] = {
            "1-6": "1-1", "1-7": "1-2",
            "2-6": "2-3", "2-7": "2-2",
            "3-6": "3-3", "3-7": "3-2"
        }
        self.parent_exchange_map: Dict[str, List[str]] = defaultdict(list)
        self._initialize_parent_exchange_map()
    
    def _initialize_parent_exchange_map(self):
        """親学級→交流学級のマッピングを初期化"""
        for exchange, parent in self.exchange_parent_map.items():
            self.parent_exchange_map[parent].append(exchange)
    
    def collect_from_schedule(self, schedule: Schedule) -> None:
        """スケジュールからメタデータを収集"""
        # テスト期間の収集
        if hasattr(schedule, 'test_periods') and schedule.test_periods:
            self.test_periods = set()
            for day, periods in schedule.test_periods.items():
                for period in periods:
                    self.test_periods.add((day, str(period)))
            logger.info(f"テスト期間: {len(self.test_periods)}スロット")
    
    def collect_from_constraints(self, constraints: List[Constraint]) -> None:
        """制約からメタデータを収集"""
        # 教師不在情報の収集
        for constraint in constraints:
            if hasattr(constraint, 'teacher_absences'):
                for teacher, absences in constraint.teacher_absences.items():
                    for absence_info in absences:
                        if isinstance(absence_info, tuple) and len(absence_info) >= 2:
                            day = absence_info[0]
                            period_info = absence_info[1]
                            
                            if period_info == "終日":
                                # その曜日の全時限を不在とする
                                for period in range(1, 7):
                                    self.teacher_absences[teacher].add((day, str(period)))
                            elif isinstance(period_info, list):
                                # 特定の時限リスト
                                for period in period_info:
                                    self.teacher_absences[teacher].add((day, str(period)))
                            elif isinstance(period_info, (int, str)):
                                # 単一の時限
                                self.teacher_absences[teacher].add((day, str(period_info)))
        
        if self.teacher_absences:
            logger.info(f"教師不在情報: {len(self.teacher_absences)}名")
            for teacher, absences in self.teacher_absences.items():
                logger.debug(f"  {teacher}: {len(absences)}時限")
    
    def is_test_period(self, day: str, period: str) -> bool:
        """指定された時間がテスト期間かどうか"""
        return (day, period) in self.test_periods
    
    def is_teacher_absent(self, teacher_name: str, day: str, period: str) -> bool:
        """指定された時間に教師が不在かどうか"""
        return (day, str(period)) in self.teacher_absences.get(teacher_name, set())
    
    def get_exchange_class(self, parent_class: str) -> List[str]:
        """親学級に対応する交流学級を取得"""
        return self.parent_exchange_map.get(parent_class, [])
    
    def get_parent_class(self, exchange_class: str) -> str:
        """交流学級に対応する親学級を取得"""
        return self.exchange_parent_map.get(exchange_class)