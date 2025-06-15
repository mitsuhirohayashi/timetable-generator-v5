"""スケジュールI/Oの基底クラス"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School


class ScheduleReader(ABC):
    """スケジュール読み込みの抽象基底クラス"""
    
    @abstractmethod
    def read(self, file_path: Path, school: Optional[School] = None) -> Schedule:
        """スケジュールを読み込む"""
        pass


class ScheduleWriter(ABC):
    """スケジュール書き込みの抽象基底クラス"""
    
    @abstractmethod
    def write(self, schedule: Schedule, file_path: Path) -> None:
        """スケジュールを書き込む"""
        pass