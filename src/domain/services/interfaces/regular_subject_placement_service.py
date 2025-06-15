"""通常教科配置サービスのインターフェース"""
from abc import ABC, abstractmethod
from typing import Optional

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher


class RegularSubjectPlacementService(ABC):
    """通常教科配置サービスのインターフェース
    
    責務:
    - 通常クラス（5組、6組、7組以外）の教科配置
    - 標準時数に基づく配置
    - 制約を考慮した最適スロット選択
    """
    
    @abstractmethod
    def place_subjects(self, schedule: Schedule, school: School) -> int:
        """通常教科を配置
        
        Args:
            schedule: スケジュール
            school: 学校情報
            
        Returns:
            配置した授業数
        """
        pass
    
    @abstractmethod
    def find_best_slot(self, schedule: Schedule, school: School,
                      class_ref: ClassReference, subject: Subject,
                      teacher: Teacher) -> Optional[TimeSlot]:
        """最適なスロットを探索
        
        Args:
            schedule: スケジュール
            school: 学校情報
            class_ref: クラス参照
            subject: 教科
            teacher: 教師
            
        Returns:
            最適なスロット（見つからない場合はNone）
        """
        pass
    
    @abstractmethod
    def can_place_subject(self, schedule: Schedule, school: School,
                         class_ref: ClassReference, slot: TimeSlot,
                         subject: Subject, teacher: Teacher) -> bool:
        """教科を配置可能かチェック
        
        Args:
            schedule: スケジュール
            school: 学校情報
            class_ref: クラス参照
            slot: 時間枠
            subject: 教科
            teacher: 教師
            
        Returns:
            配置可能な場合True
        """
        pass
    
    @abstractmethod
    def evaluate_slot_for_subject(self, slot: TimeSlot, subject: Subject) -> float:
        """教科に対するスロットの評価
        
        Args:
            slot: 時間枠
            subject: 教科
            
        Returns:
            評価スコア（低いほど良い）
        """
        pass