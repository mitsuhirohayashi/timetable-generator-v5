"""空きスロット埋め戦略のインターフェース定義"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.domain.entities.school import Subject, Teacher
from src.domain.value_objects.time_slot import ClassReference


class FillStrategy(ABC):
    """空きスロット埋め戦略の抽象基底クラス"""
    
    def __init__(self, name: str):
        """
        Args:
            name: 戦略名（ログ出力用）
        """
        self.name = name
        self.core_subjects = {"算", "国", "理", "社", "英"}
        self.excluded_subjects = {"欠", "YT", "総", "道", "学", "学活", "総合", "道徳", "学総", "行", "行事"}
    
    @abstractmethod
    def should_check_consecutive_periods(self) -> bool:
        """連続コマチェックを行うかどうか"""
        pass
    
    @abstractmethod
    def should_check_daily_duplicate_strictly(self) -> bool:
        """日内重複を厳格にチェックするかどうか"""
        pass
    
    @abstractmethod
    def should_filter_forbidden_subjects(self) -> bool:
        """禁止教科をフィルタリングするかどうか"""
        pass
    
    @abstractmethod
    def get_max_daily_occurrences(self, subject: Subject) -> int:
        """1日の最大出現回数を取得"""
        pass
    
    @abstractmethod
    def create_candidates(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        shortage_subjects: Dict[Subject, int],
        teacher_loads: Dict[str, int]
    ) -> List[Tuple[Subject, Teacher]]:
        """候補リストを作成"""
        pass
    
    def calculate_candidate_score(
        self,
        subject: Subject,
        teacher: Teacher,
        shortage: int,
        teacher_loads: Dict[str, int]
    ) -> float:
        """候補のスコアを計算（共通ロジック）"""
        score = float(shortage)
        
        # 主要教科ボーナス
        if subject.name in self.core_subjects:
            score += 10.0
        
        # 教師負担を考慮
        teacher_load = teacher_loads.get(teacher.name, 0)
        score -= teacher_load * 0.1
        
        return score