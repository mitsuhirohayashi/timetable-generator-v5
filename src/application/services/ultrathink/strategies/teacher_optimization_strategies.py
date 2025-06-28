"""教師最適化戦略モジュール

教師の満足度とワークライフバランスを改善するための各種戦略を実装します。
"""
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.assignment import Assignment


class TeacherOptimizationStrategies:
    """教師最適化戦略クラス"""
    
    def __init__(self, fixed_subjects: List[str]):
        self.logger = logging.getLogger(__name__)
        self.fixed_subjects = fixed_subjects
    
    def redistribute_teacher_load(
        self,
        schedule: Schedule,
        school: School,
        teacher_name: str,
        overloaded_day: str,
        teacher_loads: Dict[str, Dict]
    ) -> bool:
        """教師の負荷を再分配
        
        Args:
            schedule: スケジュール
            school: 学校情報
            teacher_name: 教師名
            overloaded_day: 過負荷の曜日
            teacher_loads: 教師負荷情報
            
        Returns:
            再分配が成功したかどうか
        """
        # 過負荷の日から移動可能な授業を探す
        movable_assignments = []
        
        for period in range(1, 7):
            time_slot = TimeSlot(overloaded_day, period)
            
            for class_ref in schedule.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if (assignment and assignment.teacher and 
                    assignment.teacher.name == teacher_name and
                    assignment.subject.name not in self.fixed_subjects):
                    movable_assignments.append((time_slot, assignment))
        
        # 負荷の少ない日を探す
        teacher_load = teacher_loads[teacher_name]
        target_days = [
            day for day, count in teacher_load['daily_counts'].items()
            if count < teacher_load['daily_counts'][overloaded_day] - 1
        ]
        
        # 移動を試みる
        for time_slot, assignment in movable_assignments:
            for target_day in target_days:
                # 同じ時限の別の日に移動
                target_slot = TimeSlot(target_day, time_slot.period)
                
                if not schedule.get_assignment(target_slot, assignment.class_ref):
                    # 制約チェック（簡易版）
                    if self._can_assign_safely(schedule, target_slot, assignment):
                        # 元の配置を削除して新しい場所に配置
                        schedule.remove_assignment(time_slot, assignment.class_ref)
                        schedule.assign(target_slot, assignment)
                        return True
        
        return False
    
    def break_long_consecutive_classes(
        self,
        schedule: Schedule,
        school: School,
        teacher_name: str,
        consecutive_info: List[Dict]
    ) -> bool:
        """長い連続授業を分割
        
        Args:
            schedule: スケジュール
            school: 学校情報
            teacher_name: 教師名
            consecutive_info: 連続授業情報
            
        Returns:
            分割が成功したかどうか
        """
        if not consecutive_info:
            return False
        
        # 最も長い連続授業を対象
        longest = max(consecutive_info, key=lambda x: x['length'])
        
        if longest['length'] <= 3:  # 3連続まではOK
            return False
        
        # 中間の授業を移動
        middle_period = longest['start'] + longest['length'] // 2
        time_slot = TimeSlot(longest['day'], middle_period)
        
        # その時間の授業を探す
        for class_ref in schedule.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if (assignment and assignment.teacher and
                assignment.teacher.name == teacher_name):
                
                # 別の時間に移動
                for target_period in [1, 2, 5, 6]:  # 端の時間を優先
                    if target_period == middle_period:
                        continue
                    
                    target_slot = TimeSlot(longest['day'], target_period)
                    if not schedule.get_assignment(target_slot, class_ref):
                        if self._can_assign_safely(schedule, target_slot, assignment):
                            schedule.remove_assignment(time_slot, class_ref)
                            schedule.assign(target_slot, assignment)
                            return True
        
        return False
    
    def swap_for_time_preference(
        self,
        schedule: Schedule,
        school: School,
        teacher_pattern_analyzer: Optional[object] = None
    ) -> bool:
        """時間帯の好みに基づいてスワップ
        
        Args:
            schedule: スケジュール
            school: 学校情報
            teacher_pattern_analyzer: 教師パターン分析器
            
        Returns:
            スワップが成功したかどうか
        """
        if not teacher_pattern_analyzer:
            return False
        
        # 満足度の低い配置を探す
        low_satisfaction_placements = []
        
        for time_slot, assignment in schedule.get_all_assignments():
            if not assignment.teacher or assignment.subject.name in self.fixed_subjects:
                continue
            
            preference = teacher_pattern_analyzer.get_teacher_preference(assignment.teacher.name)
            
            # 時間帯の好みをチェック
            if time_slot.period <= 3 and preference.morning_preference < 0.4:
                # 午前が苦手なのに午前に配置
                low_satisfaction_placements.append((time_slot, assignment, 'prefers_afternoon'))
            elif time_slot.period > 3 and preference.afternoon_preference < 0.4:
                # 午後が苦手なのに午後に配置
                low_satisfaction_placements.append((time_slot, assignment, 'prefers_morning'))
        
        # スワップを試みる
        for time_slot1, assignment1, pref1 in low_satisfaction_placements[:5]:
            for time_slot2, assignment2, pref2 in low_satisfaction_placements:
                if (time_slot1 == time_slot2 or
                    pref1 == pref2 or
                    assignment1.teacher.name == assignment2.teacher.name):
                    continue
                
                # 好みが逆の場合、スワップ候補
                if ((pref1 == 'prefers_afternoon' and time_slot2.period > 3) or
                    (pref1 == 'prefers_morning' and time_slot2.period <= 3)):
                    
                    # スワップを試みる
                    if self._try_swap_assignments(
                        schedule, time_slot1, assignment1.class_ref,
                        time_slot2, assignment2.class_ref
                    ):
                        return True
        
        return False
    
    def optimize_consecutive_classes(
        self,
        schedule: Schedule,
        school: School,
        teacher_pattern_analyzer: Optional[object] = None
    ) -> bool:
        """連続授業の最適化
        
        Args:
            schedule: スケジュール
            school: 学校情報
            teacher_pattern_analyzer: 教師パターン分析器
            
        Returns:
            最適化が成功したかどうか
        """
        if not teacher_pattern_analyzer:
            return False
        
        # 各教師の連続授業パターンを分析
        for teacher in school.get_all_teachers():
            if not self._is_real_teacher(teacher.name):
                continue
            
            consecutive_info = self._analyze_consecutive_classes(teacher.name, schedule)
            
            # 長すぎる連続授業があれば分割
            if any(info['length'] > 3 for info in consecutive_info):
                if self.break_long_consecutive_classes(
                    schedule, school, teacher.name, consecutive_info
                ):
                    return True
            
            # 教師の好みに応じて連続授業を調整
            preference = teacher_pattern_analyzer.get_teacher_preference(teacher.name)
            if preference.consecutive_preference < 0.3:
                # 連続授業を避けたい教師
                if self._reduce_consecutive_classes(
                    schedule, school, teacher.name, consecutive_info
                ):
                    return True
        
        return False
    
    def balance_teacher_workload(
        self,
        schedule: Schedule,
        school: School,
        analyze_workload_func: callable
    ) -> bool:
        """教師の負荷をバランス化
        
        Args:
            schedule: スケジュール
            school: 学校情報
            analyze_workload_func: ワークロード分析関数
            
        Returns:
            バランス化が成功したかどうか
        """
        teacher_loads = analyze_workload_func(schedule, school)
        
        # 負荷の偏りが大きい教師を特定
        overloaded_teachers = []
        
        for teacher_name, load_info in teacher_loads.items():
            daily_counts = load_info['daily_counts']
            if daily_counts:
                max_load = max(daily_counts.values())
                min_load = min(daily_counts.values())
                
                if max_load - min_load > 2:
                    overloaded_teachers.append({
                        'teacher': teacher_name,
                        'max_day': max(daily_counts, key=daily_counts.get),
                        'min_day': min(daily_counts, key=daily_counts.get),
                        'max_load': max_load,
                        'min_load': min_load
                    })
        
        # 最も偏りの大きい教師から処理
        overloaded_teachers.sort(key=lambda x: x['max_load'] - x['min_load'], reverse=True)
        
        for teacher_info in overloaded_teachers[:3]:
            if self.redistribute_teacher_load(
                schedule, school,
                teacher_info['teacher'],
                teacher_info['max_day'],
                teacher_loads
            ):
                return True
        
        return False
    
    def improve_class_affinity(
        self,
        schedule: Schedule,
        school: School,
        teacher_pattern_analyzer: Optional[object] = None
    ) -> bool:
        """クラスとの親和性を改善
        
        Args:
            schedule: スケジュール
            school: 学校情報
            teacher_pattern_analyzer: 教師パターン分析器
            
        Returns:
            改善が成功したかどうか
        """
        # 実装は簡略化
        return False
    
    def _can_assign_safely(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> bool:
        """安全に配置できるかチェック（簡易版）"""
        # 教師重複チェック
        for class_ref in schedule.get_all_classes():
            existing = schedule.get_assignment(time_slot, class_ref)
            if (existing and existing.teacher and
                existing.teacher.name == assignment.teacher.name):
                # 5組の合同授業は例外
                if not (class_ref.class_number == 5 and assignment.class_ref.class_number == 5):
                    return False
        
        # 日内重複チェック
        day_subjects = defaultdict(int)
        for period in range(1, 7):
            slot = TimeSlot(time_slot.day, period)
            existing = schedule.get_assignment(slot, assignment.class_ref)
            if existing:
                day_subjects[existing.subject.name] += 1
        
        if day_subjects.get(assignment.subject.name, 0) >= 1:
            return False
        
        return True
    
    def _try_swap_assignments(
        self,
        schedule: Schedule,
        time_slot1: TimeSlot,
        class_ref1,
        time_slot2: TimeSlot,
        class_ref2
    ) -> bool:
        """2つの授業をスワップ"""
        assignment1 = schedule.get_assignment(time_slot1, class_ref1)
        assignment2 = schedule.get_assignment(time_slot2, class_ref2)
        
        if not assignment1 or not assignment2:
            return False
        
        # 両方削除
        schedule.remove_assignment(time_slot1, class_ref1)
        schedule.remove_assignment(time_slot2, class_ref2)
        
        # スワップして配置
        new_assignment1 = Assignment(class_ref1, assignment2.subject, assignment2.teacher)
        new_assignment2 = Assignment(class_ref2, assignment1.subject, assignment1.teacher)
        
        if (self._can_assign_safely(schedule, time_slot1, new_assignment1) and
            self._can_assign_safely(schedule, time_slot2, new_assignment2)):
            schedule.assign(time_slot1, new_assignment1)
            schedule.assign(time_slot2, new_assignment2)
            return True
        else:
            # 元に戻す
            schedule.assign(time_slot1, assignment1)
            schedule.assign(time_slot2, assignment2)
            return False
    
    def _analyze_consecutive_classes(
        self,
        teacher_name: str,
        schedule: Schedule
    ) -> List[Dict]:
        """教師の連続授業を分析"""
        consecutive_info = []
        
        for day in ["月", "火", "水", "木", "金"]:
            consecutive_start = None
            consecutive_count = 0
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                has_class = False
                
                for class_ref in schedule.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if (assignment and assignment.teacher and
                        assignment.teacher.name == teacher_name):
                        has_class = True
                        break
                
                if has_class:
                    if consecutive_start is None:
                        consecutive_start = period
                        consecutive_count = 1
                    else:
                        consecutive_count += 1
                else:
                    if consecutive_count >= 2:
                        consecutive_info.append({
                            'day': day,
                            'start': consecutive_start,
                            'length': consecutive_count
                        })
                    consecutive_start = None
                    consecutive_count = 0
            
            # 最後までチェック
            if consecutive_count >= 2:
                consecutive_info.append({
                    'day': day,
                    'start': consecutive_start,
                    'length': consecutive_count
                })
        
        return consecutive_info
    
    def _reduce_consecutive_classes(
        self,
        schedule: Schedule,
        school: School,
        teacher_name: str,
        consecutive_info: List[Dict]
    ) -> bool:
        """連続授業を減らす"""
        # 最も短い連続授業から処理（分割しやすい）
        sorted_info = sorted(consecutive_info, key=lambda x: x['length'])
        
        for info in sorted_info:
            if info['length'] == 2:
                # 2連続の場合、片方を移動
                for offset in [0, 1]:
                    period = info['start'] + offset
                    time_slot = TimeSlot(info['day'], period)
                    
                    for class_ref in schedule.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if (assignment and assignment.teacher and
                            assignment.teacher.name == teacher_name):
                            
                            # 離れた時間に移動
                            for target_period in [1, 6]:
                                if abs(target_period - period) >= 2:
                                    target_slot = TimeSlot(info['day'], target_period)
                                    if not schedule.get_assignment(target_slot, class_ref):
                                        if self._can_assign_safely(schedule, target_slot, assignment):
                                            schedule.remove_assignment(time_slot, class_ref)
                                            schedule.assign(target_slot, assignment)
                                            return True
        
        return False
    
    def _is_real_teacher(self, teacher_name: str) -> bool:
        """実在の教師かどうかを判定"""
        return (
            teacher_name and
            not teacher_name.endswith("担当") and
            teacher_name not in ["欠", "YT", "道", "学", "総", "学総", "行"]
        )