"""日内重複違反検出器"""
import logging
from typing import List
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from ..data_models import Violation


class DailyDuplicateDetector:
    """日内重複違反を検出"""
    
    def __init__(self, violation_weight: float = 0.8):
        """初期化
        
        Args:
            violation_weight: 違反の重み
        """
        self.logger = logging.getLogger(__name__)
        self.violation_weight = violation_weight
    
    def detect(self, schedule: Schedule, school: School) -> List[Violation]:
        """日内重複を検出
        
        同じクラスで同じ日に同じ科目が複数回配置されている場合を検出します。
        
        Args:
            schedule: スケジュール
            school: 学校情報
            
        Returns:
            違反のリスト
        """
        violations = []
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            for day in days:
                subject_counts = defaultdict(int)
                subject_slots = defaultdict(list)
                
                # 1日の全時限をチェック
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        subject_counts[assignment.subject] += 1
                        subject_slots[assignment.subject].append(time_slot)
                
                # 重複をチェック
                for subject, count in subject_counts.items():
                    # 固定科目は除外
                    if subject.name in ["欠", "YT", "道", "学", "総", "学総", "行"]:
                        continue
                    
                    if count > 1:
                        violations.append(Violation(
                            type='daily_duplicate',
                            severity=self.violation_weight,
                            time_slot=subject_slots[subject][0],  # 最初のスロット
                            class_refs=[class_ref],
                            subject=subject,
                            description=f"{class_ref}の{day}曜日に{subject.name}が{count}回"
                        ))
        
        return violations