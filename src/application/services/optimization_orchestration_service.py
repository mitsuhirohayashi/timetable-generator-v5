"""最適化オーケストレーションサービス - 各種最適化の調整"""
import logging
from typing import Dict, Tuple

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from .optimizers.teacher_workload_optimizer import TeacherWorkloadOptimizer
from .optimizers.gym_usage_optimizer import GymUsageOptimizer
from .optimizers.meeting_time_optimizer import MeetingTimeOptimizer


class OptimizationOrchestrationService:
    """最適化処理を調整するサービス
    
    会議時間、体育館使用、教師負担の最適化を
    統合的に管理します。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 遅延初期化のためのプライベート変数
        self._workload_optimizer = None
        self._gym_optimizer = None
        self._meeting_optimizer = None
    
    @property
    def workload_optimizer(self):
        """教師負担最適化サービス（遅延初期化）"""
        if self._workload_optimizer is None:
            self._workload_optimizer = TeacherWorkloadOptimizer()
        return self._workload_optimizer
    
    @property
    def gym_optimizer(self):
        """体育館使用最適化サービス（遅延初期化）"""
        if self._gym_optimizer is None:
            self._gym_optimizer = GymUsageOptimizer()
        return self._gym_optimizer
    
    @property
    def meeting_optimizer(self):
        """会議時間最適化サービス（遅延初期化）"""
        if self._meeting_optimizer is None:
            self._meeting_optimizer = MeetingTimeOptimizer()
        return self._meeting_optimizer
    
    def apply_optimizations(
        self,
        schedule: Schedule,
        school: School,
        optimize_meeting_times: bool = False,
        optimize_gym_usage: bool = False,
        optimize_workload: bool = False
    ) -> Tuple[Schedule, Dict[str, int]]:
        """各種最適化を適用
        
        Args:
            schedule: 対象スケジュール
            school: 学校データ
            optimize_meeting_times: 会議時間最適化を実行するか
            optimize_gym_usage: 体育館使用最適化を実行するか
            optimize_workload: 教師負担最適化を実行するか
            
        Returns:
            (optimized_schedule, improvements): 最適化後のスケジュールと改善数
        """
        results = {
            'meeting_improvements': 0,
            'gym_improvements': 0,
            'workload_improvements': 0
        }
        
        if not any([optimize_meeting_times, optimize_gym_usage, optimize_workload]):
            self.logger.info("最適化オプションが指定されていません")
            return schedule, results
        
        self.logger.info("=== 最適化処理を開始 ===")
        
        # 1. 会議時間最適化
        if optimize_meeting_times:
            schedule, improvements = self._optimize_meeting_times(schedule, school)
            results['meeting_improvements'] = improvements
        
        # 2. 体育館使用最適化
        if optimize_gym_usage:
            schedule, improvements = self._optimize_gym_usage(schedule, school)
            results['gym_improvements'] = improvements
        
        # 3. 教師負担バランス最適化
        if optimize_workload:
            schedule, improvements = self._optimize_workload(schedule, school)
            results['workload_improvements'] = improvements
        
        self.logger.info(f"=== 最適化完了: 会議調整={results['meeting_improvements']}件, "
                        f"体育配置={results['gym_improvements']}件, "
                        f"負担改善={results['workload_improvements']}件 ===")
        
        return schedule, results
    
    def _optimize_meeting_times(
        self, 
        schedule: Schedule, 
        school: School
    ) -> Tuple[Schedule, int]:
        """会議時間最適化を実行"""
        self.logger.info("会議時間最適化を開始...")
        
        try:
            optimized_schedule, improvements = self.meeting_optimizer.optimize_meeting_times(
                schedule, school, max_iterations=50
            )
            
            if improvements > 0:
                self.logger.info(f"会議時間最適化完了: {improvements}件の調整を実施")
            else:
                self.logger.info("会議時間最適化: 調整対象なし")
            
            return optimized_schedule, improvements
            
        except Exception as e:
            self.logger.error(f"会議時間最適化エラー: {e}")
            return schedule, 0
    
    def _optimize_gym_usage(
        self,
        schedule: Schedule,
        school: School
    ) -> Tuple[Schedule, int]:
        """体育館使用最適化を実行"""
        self.logger.info("体育館使用最適化を開始...")
        
        try:
            optimized_schedule, improvements = self.gym_optimizer.optimize_gym_usage(
                schedule, school, max_iterations=100
            )
            
            if improvements > 0:
                self.logger.info(f"体育館使用最適化完了: {improvements}件の変更")
            else:
                self.logger.info("体育館使用最適化: 改善対象なし")
            
            return optimized_schedule, improvements
            
        except Exception as e:
            self.logger.error(f"体育館使用最適化エラー: {e}")
            return schedule, 0
    
    def _optimize_workload(
        self,
        schedule: Schedule,
        school: School  
    ) -> Tuple[Schedule, int]:
        """教師負担バランス最適化を実行"""
        self.logger.info("教師負担バランス最適化を開始...")
        
        try:
            optimized_schedule, improvements = self.workload_optimizer.optimize_workload(
                schedule, school, max_iterations=50
            )
            
            if improvements > 0:
                self.logger.info(f"教師負担バランス最適化完了: {improvements}件改善")
            else:
                self.logger.info("教師負担バランス最適化: 改善対象なし")
            
            return optimized_schedule, improvements
            
        except Exception as e:
            self.logger.error(f"教師負担バランス最適化エラー: {e}")
            return schedule, 0