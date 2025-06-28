"""スケジュールヘルパー

スケジュール操作に関する共通機能を提供するヘルパークラスです。
"""
import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School
    from ....domain.value_objects.constraint_violation import ConstraintViolation


class ScheduleHelper:
    """スケジュール操作ヘルパー"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def copy_schedule(self, original: 'Schedule') -> 'Schedule':
        """スケジュールをコピー
        
        Args:
            original: コピー元のスケジュール
            
        Returns:
            コピーされたスケジュール
        """
        from ....domain.entities.schedule import Schedule
        
        # 新しいスケジュールインスタンスを作成
        new_schedule = Schedule()
        
        # 全ての割り当てをコピー
        for time_slot, assignment in original.get_all_assignments():
            new_schedule.assign(time_slot, assignment)
        
        return new_schedule
    
    def lock_fixed_subjects(self, schedule: 'Schedule') -> None:
        """固定科目をロック
        
        Args:
            schedule: ロック対象のスケジュール
        """
        fixed_subjects = ["欠", "YT", "学", "道", "総", "学総", "行"]
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment and assignment.subject.name in fixed_subjects:
                schedule.lock_cell(time_slot, assignment.class_ref)
    
    def log_violations(self, violations: List['ConstraintViolation']) -> None:
        """制約違反をログ出力
        
        Args:
            violations: 制約違反のリスト
        """
        if not violations:
            return
        
        self.logger.warning(f"制約違反が{len(violations)}件発生しています:")
        
        # 最初の10件のみ表示
        for i, violation in enumerate(violations[:10]):
            self.logger.warning(f"  {i+1}. {violation}")
        
        if len(violations) > 10:
            self.logger.warning(f"  ... 他{len(violations) - 10}件の違反があります")