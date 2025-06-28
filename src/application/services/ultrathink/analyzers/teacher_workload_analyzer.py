"""教師ワークロード分析モジュール

教師の授業負荷、連続授業、ワークライフバランスを分析します。
"""
import logging
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from ..configs.teacher_optimization_config import TeacherOptimizationConfig
from ..strategies.teacher_optimization_strategies import TeacherOptimizationStrategies


class TeacherWorkloadAnalyzer:
    """教師ワークロード分析クラス"""
    
    def __init__(
        self,
        teacher_config: TeacherOptimizationConfig,
        optimization_strategies: TeacherOptimizationStrategies,
        teacher_pattern_analyzer: Optional[object] = None
    ):
        self.logger = logging.getLogger(__name__)
        self.teacher_config = teacher_config
        self.optimization_strategies = optimization_strategies
        self.teacher_pattern_analyzer = teacher_pattern_analyzer
    
    def analyze_teacher_workload(
        self,
        schedule: Schedule,
        school: School
    ) -> Dict[str, Dict]:
        """教師の負荷を分析"""
        teacher_loads = {}
        
        for teacher in school.get_all_teachers():
            load_info = {
                'total_count': 0,
                'daily_counts': defaultdict(int),
                'consecutive_info': [],
                'max_consecutive': 0
            }
            
            # 日ごとに分析
            for day in ["月", "火", "水", "木", "金"]:
                day_assignments = []
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    has_class = False
                    
                    for class_ref in schedule.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                            day_assignments.append(period)
                            load_info['total_count'] += 1
                            load_info['daily_counts'][day] += 1
                            has_class = True
                            break
                
                # 連続授業を分析
                if day_assignments:
                    consecutive = 1
                    for i in range(1, len(day_assignments)):
                        if day_assignments[i] == day_assignments[i-1] + 1:
                            consecutive += 1
                        else:
                            if consecutive > 1:
                                load_info['consecutive_info'].append({
                                    'day': day,
                                    'start': day_assignments[i-consecutive],
                                    'length': consecutive
                                })
                                load_info['max_consecutive'] = max(
                                    load_info['max_consecutive'],
                                    consecutive
                                )
                            consecutive = 1
                    
                    if consecutive > 1:
                        load_info['consecutive_info'].append({
                            'day': day,
                            'start': day_assignments[-consecutive],
                            'length': consecutive
                        })
                        load_info['max_consecutive'] = max(
                            load_info['max_consecutive'],
                            consecutive
                        )
            
            teacher_loads[teacher.name] = load_info
        
        return teacher_loads
    
    def adjust_worklife_balance(
        self,
        schedule: Schedule,
        school: School,
        teacher_context: Optional[Dict] = None
    ) -> int:
        """ワークライフバランスを考慮した調整
        
        Returns:
            調整した件数
        """
        if not self.teacher_config.enable_teacher_preference:
            return 0
        
        self.logger.info("ワークライフバランスの調整")
        
        # 各教師の負荷を分析
        teacher_loads = self.analyze_teacher_workload(schedule, school)
        
        adjustments_made = 0
        
        for teacher_name, load_info in teacher_loads.items():
            if not self.teacher_pattern_analyzer:
                continue
                
            preference = self.teacher_pattern_analyzer.get_teacher_preference(teacher_name)
            
            # 1日の最大授業数を超過している日を調整
            for day, daily_count in load_info['daily_counts'].items():
                if daily_count > preference.daily_max_preferred:
                    # 他の日に移動できる授業を探す
                    if self.redistribute_teacher_load(
                        schedule, school, teacher_name, day, teacher_loads
                    ):
                        adjustments_made += 1
            
            # 連続授業が多すぎる場合の調整
            if load_info['max_consecutive'] > preference.max_consecutive_preferred + 1:
                if self.optimization_strategies.break_long_consecutive_classes(
                    schedule, school, teacher_name, load_info['consecutive_info']
                ):
                    adjustments_made += 1
        
        if adjustments_made > 0:
            self.logger.info(f"{adjustments_made}件のワークライフバランス調整を実施")
        
        return adjustments_made
    
    def redistribute_teacher_load(
        self,
        schedule: Schedule,
        school: School,
        teacher_name: str,
        overloaded_day: str,
        teacher_loads: Dict[str, Dict]
    ) -> bool:
        """教師の負荷を再分配"""
        return self.optimization_strategies.redistribute_teacher_load(
            schedule, school, teacher_name, overloaded_day, teacher_loads
        )