"""高度なCSPスケジュールジェネレーター

CSPOrchestratorをベースに、スケジュール生成に特化したジェネレーター。
新しいScheduleGenerationUseCaseから使用される。
"""
import logging
from typing import Optional, Dict, Any, Tuple

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from ..csp_orchestrator import CSPOrchestrator


class AdvancedCSPScheduleGenerator:
    """高度なCSPスケジュールジェネレーター
    
    CSPOrchestratorの機能をラップし、
    ScheduleGenerationUseCaseのインターフェースに適合させる。
    """
    
    def __init__(self, constraint_system: UnifiedConstraintSystem):
        """初期化
        
        Args:
            constraint_system: 統一制約システム
        """
        self.logger = logging.getLogger(__name__)
        self.constraint_system = constraint_system
        self._orchestrator = None
        self._options = {
            'enable_jiritsu_priority': True,
            'enable_local_search': True,
            'max_iterations': 100
        }
    
    def set_options(self, options: Dict[str, Any]) -> None:
        """オプションを設定
        
        Args:
            options: 設定オプション
        """
        self._options.update(options)
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        max_iterations: int = 100
    ) -> Tuple[Schedule, Dict[str, Any]]:
        """スケジュールを生成
        
        Args:
            school: 学校データ
            initial_schedule: 初期スケジュール
            max_iterations: 最大反復回数
            
        Returns:
            生成されたスケジュールと統計情報のタプル
        """
        self.logger.info("=== AdvancedCSPScheduleGeneratorによる生成開始 ===")
        
        # CSPOrchestratorのアダプターを作成
        adapter = self._create_constraint_adapter()
        
        # CSPOrchestratorを初期化（遅延初期化）
        if self._orchestrator is None:
            self._orchestrator = CSPOrchestrator(adapter)
        
        # 統計情報の初期化
        statistics = {
            'iterations': 0,
            'jiritsu_placed': 0,
            'grade5_placed': 0,
            'regular_placed': 0,
            'violations_before': 0,
            'violations_after': 0
        }
        
        try:
            # 初期違反数をカウント
            if initial_schedule:
                initial_validation = self.constraint_system.validate_schedule(
                    initial_schedule, school
                )
                statistics['violations_before'] = len(initial_validation.violations)
            
            # スケジュール生成
            schedule = self._orchestrator.generate(
                school=school,
                max_iterations=max_iterations or self._options['max_iterations'],
                initial_schedule=initial_schedule
            )
            
            # 生成後の統計情報を収集
            statistics.update(self._collect_statistics(schedule, school))
            
            # 最終検証
            final_validation = self.constraint_system.validate_schedule(schedule, school)
            statistics['violations_after'] = len(final_validation.violations)
            
            self.logger.info(
                f"生成完了: "
                f"配置数={len(schedule.get_all_assignments())}, "
                f"違反数={statistics['violations_after']}"
            )
            
            return schedule, statistics
            
        except Exception as e:
            self.logger.error(f"スケジュール生成エラー: {e}")
            raise
    
    def _create_constraint_adapter(self):
        """制約システムのアダプターを作成
        
        UnifiedConstraintSystemをConstraintValidatorインターフェースに適合させる
        """
        class ConstraintValidatorAdapter:
            def __init__(self, unified_system):
                self.unified_system = unified_system
            
            def check_assignment(self, schedule, school, time_slot, assignment):
                """割り当て前チェック"""
                from ....domain.services.core.unified_constraint_system import AssignmentContext
                context = AssignmentContext(
                    schedule=schedule,
                    school=school,
                    time_slot=time_slot,
                    assignment=assignment
                )
                result, _ = self.unified_system.check_before_assignment(context)
                return result
            
            def validate_all(self, schedule, school):
                """スケジュール全体の検証"""
                validation_result = self.unified_system.validate_schedule(schedule, school)
                return validation_result.violations
        
        return ConstraintValidatorAdapter(self.constraint_system)
    
    def _collect_statistics(self, schedule: Schedule, school: School) -> Dict[str, Any]:
        """統計情報を収集
        
        Args:
            schedule: 生成されたスケジュール
            school: 学校データ
            
        Returns:
            統計情報の辞書
        """
        stats = {}
        
        # 自立活動の数をカウント
        jiritsu_count = 0
        for _, assignment in schedule.get_all_assignments():
            if assignment.subject.name == "自立":
                jiritsu_count += 1
        stats['jiritsu_placed'] = jiritsu_count
        
        # 5組の配置数をカウント
        grade5_count = 0
        grade5_classes = {"1-5", "2-5", "3-5"}
        for _, assignment in schedule.get_all_assignments():
            if str(assignment.class_ref) in grade5_classes:
                grade5_count += 1
        stats['grade5_placed'] = grade5_count
        
        # 通常教科の配置数
        stats['regular_placed'] = len(schedule.get_all_assignments()) - jiritsu_count
        
        return stats