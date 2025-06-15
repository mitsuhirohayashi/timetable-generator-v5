"""セル別教科配置禁止制約 - 特定のセルに特定の教科を配置することを禁止"""
from typing import Dict, Set, Tuple
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from .base import (
    Constraint, ConstraintResult, ConstraintViolation,
    ConstraintType, ConstraintPriority
)


class CellForbiddenSubjectConstraint(Constraint):
    """特定のセルに特定の教科を配置することを禁止する制約
    
    例: 「非英」と書かれたセルには英語を配置できない
    """
    
    def __init__(self, forbidden_cells: Dict[Tuple[TimeSlot, ClassReference], Set[str]]):
        """
        Args:
            forbidden_cells: {(時間枠, クラス): 禁止教科セット} の辞書
                            例: {(TimeSlot("月", 2), ClassReference(1, 1)): {"英"}}
                            は「1年1組の月曜2限に英語を配置禁止」を意味する
        """
        super().__init__(
            constraint_type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH,
            name="セル別教科配置禁止制約",
            description="特定のセルへの特定教科の配置を禁止"
        )
        self.forbidden_cells = forbidden_cells
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """各セルに禁止教科が配置されていないか検証"""
        violations = []
        
        # ログに制約の詳細を出力
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"セル別配置禁止制約の検証: {len(self.forbidden_cells)}個のセル")
        
        # 各セルの禁止設定をチェック
        for (time_slot, class_ref), forbidden_subjects in self.forbidden_cells.items():
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            if assignment and assignment.subject.name in forbidden_subjects:
                violation = ConstraintViolation(
                    description=f"セル配置禁止違反: {class_ref}の{time_slot}に"
                               f"禁止教科「{assignment.subject.name}」が配置されています"
                               f"（このセルは「非{assignment.subject.name}」指定）",
                    time_slot=time_slot,
                    assignment=assignment,
                    severity="ERROR"
                )
                violations.append(violation)
                logger.warning(f"セル配置禁止違反を検出: {violation.description}")
        
        return ConstraintResult(self.__class__.__name__, violations)
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment) -> bool:
        """指定された割り当てが禁止されていないかチェック（配置前チェック）"""
        from ..value_objects.assignment import Assignment
        
        # 該当セルの禁止教科を取得
        key = (time_slot, assignment.class_ref)
        if key in self.forbidden_cells:
            forbidden_subjects = self.forbidden_cells[key]
            if assignment.subject.name in forbidden_subjects:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"セル配置禁止: {assignment.class_ref}の{time_slot}に"
                             f"「{assignment.subject.name}」は配置できません（非{assignment.subject.name}指定）")
                return False
        
        return True