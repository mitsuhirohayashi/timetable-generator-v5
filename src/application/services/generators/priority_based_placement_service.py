"""優先度ベースの教科配置サービス（競合時間帯の事前検出と回避）"""
import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.base import ConstraintValidator
from ....domain.interfaces.csp_configuration import ICSPConfiguration


@dataclass
class PlacementTask:
    """配置タスク"""
    class_ref: ClassReference
    subject: Subject
    teacher: Teacher
    priority: float
    remaining_hours: int
    constraints_count: int  # この配置に関する制約の数


class PriorityBasedPlacementService:
    """優先度ベースの教科配置サービス"""
    
    def __init__(self, config: ICSPConfiguration, constraint_validator: ConstraintValidator):
        self.config = config
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
        
        # 既知の問題時間帯（経験的に競合しやすい）
        self.high_conflict_slots = [
            TimeSlot("火", 5),  # 火曜5限は特に競合しやすい
            TimeSlot("水", 3),  # 水曜3限も競合しやすい
            TimeSlot("木", 3),  # 木曜3限（生徒指導会議）
        ]
    
    def place_with_priority(self, schedule: Schedule, school: School) -> int:
        """優先度順に教科を配置"""
        self.logger.info("優先度ベースの配置を開始")
        
        # 1. 配置タスクを収集
        tasks = self._collect_placement_tasks(schedule, school)
        
        # 2. 競合分析
        conflict_analysis = self._analyze_conflicts(tasks, school)
        
        # 3. 優先度を計算してソート
        sorted_tasks = self._prioritize_tasks(tasks, conflict_analysis)
        
        # 4. 順番に配置
        total_placed = 0
        for task in sorted_tasks:
            placed = self._place_task(task, schedule, school, conflict_analysis)
            total_placed += placed
            
            if placed < task.remaining_hours:
                self.logger.warning(f"{task.class_ref}の{task.subject}: "
                                  f"{placed}/{task.remaining_hours}時間のみ配置")
        
        self.logger.info(f"優先度ベース配置完了: {total_placed}コマ配置")
        return total_placed
    
    def _collect_placement_tasks(self, schedule: Schedule, school: School) -> List[PlacementTask]:
        """配置タスクを収集"""
        tasks = []
        
        for class_ref in school.get_all_classes():
            # 特別クラスは別処理
            if class_ref.class_number in [5, 6, 7]:
                continue
            
            for subject in school.get_required_subjects(class_ref):
                if subject.is_protected_subject():
                    continue
                
                # 必要時数と配置済み時数を計算
                required_hours = int(round(school.get_standard_hours(class_ref, subject)))
                placed_hours = sum(
                    1 for _, assignment in schedule.get_all_assignments()
                    if assignment.class_ref == class_ref and assignment.subject == subject
                )
                
                remaining = required_hours - placed_hours
                if remaining <= 0:
                    continue
                
                # 教師を取得
                teacher = school.get_assigned_teacher(subject, class_ref)
                if not teacher:
                    continue
                
                # タスクを作成
                task = PlacementTask(
                    class_ref=class_ref,
                    subject=subject,
                    teacher=teacher,
                    priority=0.0,  # 後で計算
                    remaining_hours=remaining,
                    constraints_count=0  # 後で計算
                )
                tasks.append(task)
        
        return tasks
    
    def _analyze_conflicts(self, tasks: List[PlacementTask], school: School) -> Dict:
        """競合分析"""
        analysis = {
            'teacher_load': defaultdict(int),  # 教師ごとの総担当時数
            'teacher_classes': defaultdict(set),  # 教師ごとの担当クラス
            'slot_demand': defaultdict(int),  # 時間枠ごとの需要
            'critical_teachers': set(),  # 特に競合しやすい教師
        }
        
        # 教師の負荷を分析
        for task in tasks:
            teacher_name = task.teacher.name
            analysis['teacher_load'][teacher_name] += task.remaining_hours
            analysis['teacher_classes'][teacher_name].add(task.class_ref)
        
        # 競合しやすい教師を特定（多くのクラスを担当）
        for teacher_name, classes in analysis['teacher_classes'].items():
            if len(classes) >= 3:  # 3クラス以上担当
                analysis['critical_teachers'].add(teacher_name)
                self.logger.debug(f"競合しやすい教師: {teacher_name} ({len(classes)}クラス担当)")
        
        # 特定の教師の詳細分析（井上先生など）
        if "井上" in analysis['teacher_load']:
            self.logger.info(f"井上先生の分析: {analysis['teacher_load']['井上']}時間, "
                           f"{len(analysis['teacher_classes']['井上'])}クラス担当")
        
        return analysis
    
    def _prioritize_tasks(self, tasks: List[PlacementTask], conflict_analysis: Dict) -> List[PlacementTask]:
        """タスクの優先度を計算してソート"""
        for task in tasks:
            # 基本優先度
            priority = 0.0
            
            # 1. 教師の競合度（高いほど優先）
            if task.teacher.name in conflict_analysis['critical_teachers']:
                priority += 50.0
            
            # 2. 残り時数（多いほど優先）
            priority += task.remaining_hours * 10.0
            
            # 3. 教師の総負荷（高いほど優先）
            teacher_load = conflict_analysis['teacher_load'][task.teacher.name]
            priority += teacher_load * 2.0
            
            # 4. 特定の教科の優先度
            if task.subject.name in ["数", "英"]:  # 主要教科
                priority += 20.0
            elif task.subject.name == "保":  # 体育館使用
                priority += 15.0
            
            # 5. 井上先生の特別処理
            if task.teacher.name == "井上":
                priority += 100.0  # 最優先で配置
                self.logger.debug(f"井上先生のタスク優先度: {priority} ({task.class_ref}, {task.subject})")
            
            task.priority = priority
        
        # 優先度順にソート（降順）
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        # 上位タスクをログ出力
        self.logger.info("優先度上位のタスク:")
        for i, task in enumerate(sorted_tasks[:5]):
            self.logger.info(f"  {i+1}. {task.class_ref} {task.subject} "
                           f"({task.teacher.name}先生) - 優先度: {task.priority:.1f}")
        
        return sorted_tasks
    
    def _place_task(self, task: PlacementTask, schedule: Schedule, school: School,
                   conflict_analysis: Dict) -> int:
        """タスクを配置"""
        placed_count = 0
        
        # 配置可能なスロットを評価
        slot_scores = []
        
        for day in self.config.weekdays:
            # 日内重複チェック
            daily_count = sum(
                1 for period in range(1, 7)
                for slot, assignment in schedule.get_all_assignments()
                if (slot.day == day and 
                    assignment.class_ref == task.class_ref and 
                    assignment.subject == task.subject)
            )
            if daily_count > 0:
                continue
            
            for period in range(1, 7):
                slot = TimeSlot(day, period)
                
                # 基本チェック
                if schedule.get_assignment(slot, task.class_ref):
                    continue
                if schedule.is_locked(slot, task.class_ref):
                    continue
                
                # スロットを評価
                score = self._evaluate_slot(slot, task, schedule, school, conflict_analysis)
                if score >= 0:  # 配置可能
                    slot_scores.append((slot, score))
        
        # スコア順にソート（高いほど良い）
        slot_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 上位スロットから配置を試みる
        for slot, score in slot_scores[:task.remaining_hours]:
            assignment = Assignment(task.class_ref, task.subject, task.teacher)
            
            # 制約チェック
            if self.constraint_validator.check_assignment(schedule, school, slot, assignment):
                try:
                    schedule.assign(slot, assignment)
                    placed_count += 1
                    
                    # 井上先生の配置をログ
                    if task.teacher.name == "井上":
                        self.logger.info(f"井上先生を配置: {task.class_ref} {slot.day}{slot.period}限 "
                                       f"(スコア: {score:.1f})")
                    
                    if placed_count >= task.remaining_hours:
                        break
                        
                except ValueError as e:
                    self.logger.debug(f"配置エラー: {e}")
        
        return placed_count
    
    def _evaluate_slot(self, slot: TimeSlot, task: PlacementTask, schedule: Schedule,
                      school: School, conflict_analysis: Dict) -> float:
        """スロットの評価（高いほど良い）"""
        score = 100.0  # 基本スコア
        
        # 1. 競合時間帯のペナルティ
        if slot in self.high_conflict_slots:
            score -= 50.0
            
            # 井上先生の火曜5限は特に避ける
            if task.teacher.name == "井上" and slot == TimeSlot("火", 5):
                # 既に他のクラスが配置されているかチェック
                for cls in school.get_all_classes():
                    if cls == task.class_ref:
                        continue
                    existing = schedule.get_assignment(slot, cls)
                    if existing and existing.teacher and existing.teacher.name == "井上":
                        return -1  # 配置不可
        
        # 2. 教師の可用性チェック
        for cls in school.get_all_classes():
            if cls == task.class_ref:
                continue
            existing = schedule.get_assignment(slot, cls)
            if existing and existing.teacher and existing.teacher.name == task.teacher.name:
                # 5組の例外
                grade5_classes = {"1年5組", "2年5組", "3年5組"}
                if not (cls.full_name in grade5_classes and task.class_ref.full_name in grade5_classes):
                    return -1  # 配置不可
        
        # 3. 教科別の時間帯選好
        if task.subject.name in ["数", "英", "国"]:  # 主要教科
            if slot.period <= 3:  # 午前中
                score += 20.0
            else:
                score -= 10.0
        elif task.subject.name == "保":  # 体育
            if slot.period in [3, 4, 5]:  # 中間の時間
                score += 15.0
        
        # 4. 曜日バランス
        # 週の中間を好む
        if slot.day in ["火", "水", "木"]:
            score += 10.0
        
        # 5. 教師の負荷分散
        # 同じ日に同じ教師が多く配置されないように
        same_day_count = sum(
            1 for period in range(1, 7)
            for cls in school.get_all_classes()
            if cls != task.class_ref
            for s, a in schedule.get_all_assignments()
            if (s.day == slot.day and s.period == period and
                a.class_ref == cls and a.teacher and 
                a.teacher.name == task.teacher.name)
        )
        score -= same_day_count * 5.0
        
        return score