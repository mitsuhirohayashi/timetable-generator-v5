"""教師の負担バランス最適化サービス"""
import logging
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from ....domain.interfaces.teacher_absence_repository import ITeacherAbsenceRepository


class TeacherWorkloadOptimizer:
    """教師の負担を最適化するサービス"""
    
    def __init__(self, absence_repository: Optional[ITeacherAbsenceRepository] = None):
        self.logger = logging.getLogger(__name__)
        
        # 依存性注入
        if absence_repository is None:
            from ....infrastructure.di_container import get_teacher_absence_repository
            absence_repository = get_teacher_absence_repository()
            
        self.absence_repository = absence_repository
        
        # 理想的な1日あたりの授業数
        self.ideal_daily_lessons = {
            "通常教員": 4,  # 1日4コマが理想
            "非常勤": 3,    # 非常勤は1日3コマまで
            "管理職": 2,    # 管理職は1日2コマまで
        }
        
        # 連続授業の最大数
        self.max_consecutive_lessons = 3
        
        # 空き時間の理想的な配置
        self.ideal_break_pattern = {
            "午前": 1,  # 午前中に1コマの空き
            "午後": 1,  # 午後に1コマの空き
        }
    
    def optimize_workload(self, schedule: Schedule, school: School, 
                          max_iterations: int = 100) -> Tuple[Schedule, int]:
        """教師の負担を最適化"""
        self.logger.info("=== 教師負担バランス最適化を開始 ===")
        
        improvement_count = 0
        
        for iteration in range(max_iterations):
            # 現在の負担状況を分析
            workload_analysis = self._analyze_workload(schedule, school)
            
            # 最も改善が必要な教師を特定
            target_teachers = self._identify_overloaded_teachers(workload_analysis)
            
            if not target_teachers:
                self.logger.info(f"最適化完了: {iteration}回の反復で{improvement_count}件改善")
                break
            
            # 各教師について負担軽減を試みる
            improved = False
            for teacher_name, issues in target_teachers:
                if self._reduce_teacher_workload(schedule, school, teacher_name, issues):
                    improvement_count += 1
                    improved = True
            
            if not improved:
                self.logger.info(f"これ以上の改善は困難: {improvement_count}件改善")
                break
        
        # 最終的な負担状況をログ出力
        self._log_final_workload(schedule, school)
        
        return schedule, improvement_count
    
    def _analyze_workload(self, schedule: Schedule, school: School) -> Dict[str, Dict]:
        """教師ごとの負担状況を分析"""
        workload = defaultdict(lambda: {
            "total_lessons": 0,
            "daily_lessons": defaultdict(int),
            "consecutive_lessons": defaultdict(list),
            "break_times": defaultdict(list),
            "issues": []
        })
        
        # 全教師を分析
        all_teachers = list(school.get_all_teachers())
        
        for teacher in all_teachers:
            teacher_name = teacher.name
            
            for day in ["月", "火", "水", "木", "金"]:
                daily_schedule = []
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    has_lesson = False
                    
                    # この時間に授業があるかチェック
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                            has_lesson = True
                            break
                    
                    daily_schedule.append(has_lesson)
                
                # 統計を計算
                daily_lessons = sum(daily_schedule)
                workload[teacher_name]["daily_lessons"][day] = daily_lessons
                workload[teacher_name]["total_lessons"] += daily_lessons
                
                # 連続授業をチェック
                consecutive = 0
                for i, has_lesson in enumerate(daily_schedule):
                    if has_lesson:
                        consecutive += 1
                    else:
                        if consecutive > 0:
                            workload[teacher_name]["consecutive_lessons"][day].append(consecutive)
                            consecutive = 0
                if consecutive > 0:
                    workload[teacher_name]["consecutive_lessons"][day].append(consecutive)
                
                # 空き時間を記録
                for period, has_lesson in enumerate(daily_schedule, 1):
                    if not has_lesson:
                        workload[teacher_name]["break_times"][day].append(period)
        
        # 問題点を特定
        for teacher_name, data in workload.items():
            # 1日の授業数が多すぎる
            for day, count in data["daily_lessons"].items():
                if count > self.ideal_daily_lessons.get(self._get_teacher_type(teacher_name), 4):
                    data["issues"].append(("overload", day, count))
            
            # 連続授業が長すぎる
            for day, consecutives in data["consecutive_lessons"].items():
                for consecutive in consecutives:
                    if consecutive > self.max_consecutive_lessons:
                        data["issues"].append(("consecutive", day, consecutive))
            
            # 空き時間が偏っている
            for day, breaks in data["break_times"].items():
                if len(breaks) == 0 and data["daily_lessons"][day] >= 5:
                    data["issues"].append(("no_break", day, None))
        
        return workload
    
    def _identify_overloaded_teachers(self, workload_analysis: Dict) -> List[Tuple[str, List]]:
        """負担が大きい教師を特定"""
        overloaded = []
        
        for teacher_name, data in workload_analysis.items():
            if data["issues"]:
                # 問題の深刻度でソート
                severity_score = 0
                for issue_type, day, value in data["issues"]:
                    if issue_type == "overload":
                        severity_score += (value - 4) * 10
                    elif issue_type == "consecutive":
                        severity_score += (value - 3) * 5
                    elif issue_type == "no_break":
                        severity_score += 3
                
                overloaded.append((teacher_name, data["issues"], severity_score))
        
        # 深刻度順にソート
        overloaded.sort(key=lambda x: x[2], reverse=True)
        
        return [(name, issues) for name, issues, _ in overloaded[:5]]  # 上位5名
    
    def _reduce_teacher_workload(self, schedule: Schedule, school: School,
                                teacher_name: str, issues: List) -> bool:
        """特定の教師の負担を軽減"""
        for issue_type, day, value in issues:
            if issue_type == "overload":
                # 過負荷の日の授業を他の日に移動
                if self._redistribute_lessons(schedule, school, teacher_name, day):
                    self.logger.info(f"{teacher_name}先生の{day}曜日の授業を再配分")
                    return True
            
            elif issue_type == "consecutive":
                # 連続授業を分割
                if self._break_consecutive_lessons(schedule, school, teacher_name, day):
                    self.logger.info(f"{teacher_name}先生の{day}曜日の連続授業を分割")
                    return True
            
            elif issue_type == "no_break":
                # 空き時間を作る
                if self._create_break_time(schedule, school, teacher_name, day):
                    self.logger.info(f"{teacher_name}先生の{day}曜日に空き時間を作成")
                    return True
        
        return False
    
    def _redistribute_lessons(self, schedule: Schedule, school: School,
                             teacher_name: str, overloaded_day: str) -> bool:
        """授業を他の日に再配分"""
        # 移動可能な授業を探す
        movable_lessons = []
        
        for period in range(1, 7):
            time_slot = TimeSlot(overloaded_day, period)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if (assignment and assignment.teacher and 
                    assignment.teacher.name == teacher_name and
                    not schedule.is_locked(time_slot, class_ref)):
                    movable_lessons.append((time_slot, class_ref, assignment))
        
        # 移動先を探す
        for source_slot, class_ref, assignment in movable_lessons:
            for target_day in ["月", "火", "水", "木", "金"]:
                if target_day == overloaded_day:
                    continue
                
                for target_period in range(1, 7):
                    target_slot = TimeSlot(target_day, target_period)
                    
                    # 移動可能かチェック
                    if (not schedule.get_assignment(target_slot, class_ref) and
                        self._can_move_lesson(schedule, school, assignment, 
                                            source_slot, target_slot, class_ref)):
                        # 授業を移動
                        schedule.remove_assignment(source_slot, class_ref)
                        schedule.assign(target_slot, assignment)
                        return True
        
        return False
    
    def _break_consecutive_lessons(self, schedule: Schedule, school: School,
                                   teacher_name: str, day: str) -> bool:
        """連続授業を分割"""
        # 実装は省略（授業の入れ替えロジック）
        return False
    
    def _create_break_time(self, schedule: Schedule, school: School,
                          teacher_name: str, day: str) -> bool:
        """空き時間を作成"""
        # 実装は省略（授業の削減ロジック）
        return False
    
    def _can_move_lesson(self, schedule: Schedule, school: School,
                        assignment: Assignment, source_slot: TimeSlot,
                        target_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """授業を移動可能かチェック"""
        # 基本的な制約チェック
        if schedule.is_locked(target_slot, class_ref):
            return False
        
        # 教師の利用可能性
        if assignment.teacher:
            if self.absence_repository.is_teacher_absent(
                assignment.teacher.name, target_slot.day, target_slot.period):
                return False
            
            if not schedule.is_teacher_available(target_slot, assignment.teacher):
                return False
        
        # 日内重複チェック
        for period in range(1, 7):
            if period == target_slot.period:
                continue
            check_slot = TimeSlot(target_slot.day, period)
            check_assignment = schedule.get_assignment(check_slot, class_ref)
            if check_assignment and check_assignment.subject == assignment.subject:
                return False
        
        return True
    
    def _get_teacher_type(self, teacher_name: str) -> str:
        """教師のタイプを判定"""
        if teacher_name in ["校長", "教頭"]:
            return "管理職"
        elif teacher_name in ["塚本", "永山", "箱崎"]:  # 非常勤の例
            return "非常勤"
        else:
            return "通常教員"
    
    def _log_final_workload(self, schedule: Schedule, school: School) -> None:
        """最終的な負担状況をログ出力"""
        workload = self._analyze_workload(schedule, school)
        
        self.logger.info("=== 最終的な教師負担状況 ===")
        for teacher_name, data in sorted(workload.items()):
            total = data["total_lessons"]
            daily_avg = total / 5
            
            daily_summary = ", ".join(
                f"{day}:{count}" for day, count in data["daily_lessons"].items()
            )
            
            self.logger.info(
                f"{teacher_name}: 週{total}コマ (平均{daily_avg:.1f}コマ/日) "
                f"[{daily_summary}]"
            )