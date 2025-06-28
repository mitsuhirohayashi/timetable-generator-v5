"""空きスロット埋めヘルパー

スケジュールの空きスロットを効率的に埋めるヘルパークラスです。
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School
    from ....domain.services.core.unified_constraint_system import UnifiedConstraintSystem
    from ....infrastructure.config.path_manager import PathManager


class EmptySlotFiller:
    """空きスロット埋めヘルパー"""
    
    def __init__(self, constraint_system: 'UnifiedConstraintSystem', path_manager: 'PathManager'):
        self.constraint_system = constraint_system
        self.path_manager = path_manager
        self.logger = logging.getLogger(__name__)
    
    def fill_empty_slots(self, schedule: 'Schedule', school: 'School', max_passes: int = 10) -> int:
        """スマート空きスロット埋め
        
        Args:
            schedule: スケジュール
            school: 学校情報
            max_passes: 最大パス数
            
        Returns:
            埋めた空きスロット数
        """
        self.logger.info("=== 空きスロットを埋めています ===")
        
        # Follow-up.csvから教師不在情報を取得
        from ....infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
        from ....infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
        
        natural_parser = NaturalFollowUpParser(self.path_manager.input_dir)
        natural_result = natural_parser.parse_file("Follow-up.csv")
        
        # 教師不在情報のロード
        absence_loader = TeacherAbsenceLoader()
        if natural_result["parse_success"] and natural_result.get("teacher_absences"):
            absence_loader.update_absences_from_parsed_data(natural_result["teacher_absences"])
        
        # SmartEmptySlotFillerを使用
        from ....domain.services.core.smart_empty_slot_filler import SmartEmptySlotFiller
        
        # QA.txtからルールを読み込み
        from ....infrastructure.config.qa_rules_loader import QARulesLoader
        qa_loader = QARulesLoader()
        
        filler = SmartEmptySlotFiller(
            self.constraint_system, 
            absence_loader,
            homeroom_teachers=qa_loader.rules.get('homeroom_teachers', {}),
            sixth_period_rules=qa_loader.rules.get('grade_6th_period_rules', {}),
            priority_subjects=qa_loader.get_subject_priorities(),
            teacher_ratios=qa_loader.rules.get('teacher_ratios', {})
        )
        
        # 空きスロットを埋める
        filled_count = filler.fill_empty_slots_smartly(schedule, school, max_passes)
        
        if filled_count > 0:
            self.logger.info(f"合計 {filled_count} 個の空きスロットを埋めました")
        else:
            self.logger.info("埋められる空きスロットはありませんでした")
        
        return filled_count