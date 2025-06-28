"""スケジュール最適化ユースケース

生成されたスケジュールの最適化を担当する。
"""
import logging
from typing import Dict, Optional

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from ..services.optimizers.integrated_optimizer_improved import IntegratedOptimizerImproved
from ..services.optimizers.meeting_time_optimizer import MeetingTimeOptimizer
from ..services.optimizers.exchange_class_optimizer import ExchangeClassOptimizer
from ..services.optimizers.gym_usage_optimizer import GymUsageOptimizer
from ..services.optimizers.teacher_workload_optimizer import TeacherWorkloadOptimizer
from ..services.optimizers.grade5_sync_optimizer import Grade5SyncOptimizer


class ScheduleOptimizationUseCase:
    """スケジュール最適化ユースケース
    
    責任：
    - 各種最適化の実行
    - 交流学級・5組同期の修正
    - 空きコマ埋め処理
    - 会議時間・体育館・教師負担の最適化
    """
    
    def __init__(
        self,
        constraint_system: UnifiedConstraintSystem
    ):
        """初期化
        
        Args:
            constraint_system: 統一制約システム
        """
        self.constraint_system = constraint_system
        self.logger = logging.getLogger(__name__)
        
        # 統合最適化サービス
        self.integrated_optimizer = IntegratedOptimizerImproved(constraint_system)
        
        # QA.txtからルールを読み込み
        from ...infrastructure.config.qa_rules_loader import QARulesLoader
        qa_loader = QARulesLoader()
        
        # 会議設定を構築
        meetings = {}
        for name, info in qa_loader.rules.get('meetings', {}).items():
            meetings[name] = info
        
        # 個別最適化サービス
        self.meeting_optimizer = MeetingTimeOptimizer(
            absence_repository=None,  # DIコンテナから自動注入
            regular_meetings=meetings,
            teacher_roles=qa_loader.rules.get('teacher_roles', {}),
            all_day_absences=qa_loader.rules.get('regular_absences', {})
        )
        self.exchange_optimizer = ExchangeClassOptimizer(constraint_system)
        self.gym_optimizer = GymUsageOptimizer(constraint_system)
        self.workload_optimizer = TeacherWorkloadOptimizer(constraint_system)
        self.grade5_optimizer = Grade5SyncOptimizer(constraint_system)
    
    def execute(
        self,
        schedule: Schedule,
        school: School,
        options: Dict[str, bool]
    ) -> Dict[str, int]:
        """最適化を実行
        
        Args:
            schedule: スケジュール
            school: 学校データ
            options: 最適化オプション
                - optimize_meeting_times: 会議時間最適化
                - optimize_gym_usage: 体育館使用最適化
                - optimize_workload: 教師負担最適化
                - fill_empty_slots: 空きスロット埋め
                
        Returns:
            Dict[str, int]: 最適化結果の統計
        """
        stats = {
            'total_improved': 0,
            'exchange_sync_fixed': 0,
            'grade5_sync_fixed': 0,
            'empty_slots_filled': 0,
            'meeting_optimized': 0,
            'gym_conflicts_resolved': 0,
            'workload_balanced': 0
        }
        
        # 1. 交流学級の同期修正
        self.logger.info("=== 交流学級の同期修正 ===")
        sync_result = self.exchange_optimizer.optimize(schedule, school)
        stats['exchange_sync_fixed'] = sync_result.improvement_count
        
        # 2. 5組の同期修正
        self.logger.info("=== 5組の同期修正 ===")
        grade5_result = self.grade5_optimizer.optimize(schedule, school)
        stats['grade5_sync_fixed'] = grade5_result.improvement_count
        
        # 3. 統合最適化（空きスロット埋め、標準時数調整）
        if options.get('fill_empty_slots', True):
            self.logger.info("=== 統合最適化（空きスロット埋め） ===")
            integrated_result = self.integrated_optimizer.optimize(
                schedule,
                school,
                max_iterations=5
            )
            stats['empty_slots_filled'] = integrated_result['empty_slots_filled']
            stats['total_improved'] += integrated_result['improvements']
        
        # 4. 会議時間最適化
        if options.get('optimize_meeting_times', False):
            self.logger.info("=== 会議時間最適化 ===")
            meeting_result = self.meeting_optimizer.optimize(schedule, school)
            stats['meeting_optimized'] = meeting_result.improvement_count
            stats['total_improved'] += meeting_result.improvement_count
        
        # 5. 体育館使用最適化
        if options.get('optimize_gym_usage', False):
            self.logger.info("=== 体育館使用最適化 ===")
            gym_result = self.gym_optimizer.optimize(schedule, school)
            stats['gym_conflicts_resolved'] = gym_result.improvement_count
            stats['total_improved'] += gym_result.improvement_count
        
        # 6. 教師負担バランス最適化
        if options.get('optimize_workload', False):
            self.logger.info("=== 教師負担バランス最適化 ===")
            workload_result = self.workload_optimizer.optimize(schedule, school)
            stats['workload_balanced'] = workload_result.improvement_count
            stats['total_improved'] += workload_result.improvement_count
        
        # 最適化結果のログ出力
        self._log_optimization_results(stats)
        
        return stats
    
    def _log_optimization_results(self, stats: Dict[str, int]) -> None:
        """最適化結果をログ出力"""
        self.logger.info("=== 最適化結果サマリー ===")
        self.logger.info(f"交流学級同期修正: {stats['exchange_sync_fixed']}件")
        self.logger.info(f"5組同期修正: {stats['grade5_sync_fixed']}件")
        self.logger.info(f"空きスロット埋め: {stats['empty_slots_filled']}個")
        self.logger.info(f"会議時間最適化: {stats['meeting_optimized']}件")
        self.logger.info(f"体育館競合解消: {stats['gym_conflicts_resolved']}件")
        self.logger.info(f"教師負担改善: {stats['workload_balanced']}件")
        self.logger.info(f"総改善数: {stats['total_improved']}件")