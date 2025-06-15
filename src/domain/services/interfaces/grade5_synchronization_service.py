"""5組同期サービスのインターフェース"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject


class Grade5SynchronizationService(ABC):
    """5組同期サービスのインターフェース
    
    責務:
    - 5組（1-5, 2-5, 3-5）の共通教科識別
    - 同一時限への同期配置
    - 体育以外の教科の同期
    """
    
    @abstractmethod
    def get_common_subjects(self, school: School, grade5_classes: List[ClassReference]) -> Dict[Subject, int]:
        """共通教科と必要時間数を取得
        
        Args:
            school: 学校情報
            grade5_classes: 5組クラスのリスト
            
        Returns:
            共通教科と必要時間数の辞書
        """
        pass
    
    @abstractmethod
    def synchronize_placement(self, schedule: Schedule, school: School) -> int:
        """5組の同期配置を実行
        
        Args:
            schedule: スケジュール
            school: 学校情報
            
        Returns:
            同期配置した授業数
        """
        pass
    
    @abstractmethod
    def find_best_slot_for_grade5(self, schedule: Schedule, school: School,
                                  classes: List[ClassReference], subject: Subject) -> Optional[TimeSlot]:
        """5組の最適なスロットを探索
        
        Args:
            schedule: スケジュール
            school: 学校情報
            classes: 5組クラスのリスト
            subject: 配置する教科
            
        Returns:
            最適なスロット（見つからない場合はNone）
        """
        pass
    
    @abstractmethod
    def count_placed_hours(self, schedule: Schedule, classes: List[ClassReference],
                          subject: Subject) -> int:
        """配置済み時間数をカウント
        
        Args:
            schedule: スケジュール
            classes: 5組クラスのリスト
            subject: 教科
            
        Returns:
            配置済み時間数
        """
        pass