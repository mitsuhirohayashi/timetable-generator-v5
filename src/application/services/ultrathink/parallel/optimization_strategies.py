"""並列最適化戦略

スケジュール最適化のための各種戦略を実装します。
"""
import random
from typing import Dict, List, Optional, Callable
from collections import defaultdict

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot, ClassReference
from .....domain.value_objects.assignment import Assignment


class OptimizationStrategies:
    """最適化戦略の実装"""
    
    def __init__(self):
        """初期化"""
        self.strategies = {
            'random_swap': self.random_swap,
            'two_opt': self.two_opt_swap,
            'teacher_based': self.teacher_based_move,
            'chain_move': self.chain_move,
            'aggressive': self.aggressive_optimization
        }
    
    def get_strategy(self, name: str) -> Optional[Callable]:
        """戦略を取得"""
        return self.strategies.get(name)
    
    def random_swap(self, schedule: Schedule, school: School) -> None:
        """ランダムなスワップ
        
        ランダムに選んだ2つの授業を入れ替えます。
        """
        classes = list(school.get_all_classes())
        if len(classes) < 2:
            return
        
        # ランダムに2つのスロットを選択
        class1 = random.choice(classes)
        class2 = random.choice(classes)
        
        days = ["月", "火", "水", "木", "金"]
        day1 = random.choice(days)
        day2 = random.choice(days)
        period1 = random.randint(1, 5)
        period2 = random.randint(1, 5)
        
        time_slot1 = TimeSlot(day1, period1)
        time_slot2 = TimeSlot(day2, period2)
        
        # スワップを試みる
        self._try_swap(schedule, time_slot1, class1, time_slot2, class2)
    
    def two_opt_swap(self, schedule: Schedule, school: School) -> None:
        """2-optスワップ
        
        2つの授業ペアを連続して入れ替えます。
        """
        self.random_swap(schedule, school)
        self.random_swap(schedule, school)
    
    def teacher_based_move(self, schedule: Schedule, school: School) -> None:
        """教師ベースの移動
        
        教師の重複を解消する方向に授業を移動します。
        """
        self.fix_teacher_conflicts(schedule, school)
    
    def chain_move(self, schedule: Schedule, school: School) -> None:
        """チェーン移動
        
        連鎖的な移動を実行します。
        """
        for _ in range(3):
            self.random_swap(schedule, school)
    
    def aggressive_optimization(self, schedule: Schedule, school: School) -> None:
        """積極的な最適化
        
        大幅な変更を加えて局所最適から脱出を試みます。
        """
        # 大幅な変更を加える
        for _ in range(20):
            self.random_swap(schedule, school)
        
        # 教師重複を集中的に解消
        for _ in range(5):
            self.fix_teacher_conflicts(schedule, school)
    
    def fix_teacher_conflicts(self, schedule: Schedule, school: School) -> None:
        """教師重複を修正"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 6):
                time_slot = TimeSlot(day, period)
                
                # 重複している教師を検出
                teacher_classes = defaultdict(list)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_classes[assignment.teacher.name].append((class_ref, assignment))
                
                # 重複を解消
                for teacher_name, class_assignments in teacher_classes.items():
                    if len(class_assignments) > 1:
                        # 5組の合同授業は除外
                        grade5_classes = {
                            ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)
                        }
                        grade5_count = sum(1 for c, _ in class_assignments if c in grade5_classes)
                        
                        if grade5_count < len(class_assignments):
                            # 1つを残して他を移動
                            for i, (class_ref, assignment) in enumerate(class_assignments[1:]):
                                if class_ref not in grade5_classes:
                                    # 別の時間に移動を試みる
                                    self._relocate_assignment(schedule, school, time_slot, class_ref)
                                    break
    
    def _try_swap(
        self,
        schedule: Schedule,
        time_slot1: TimeSlot,
        class1: ClassReference,
        time_slot2: TimeSlot,
        class2: ClassReference
    ) -> bool:
        """2つの授業をスワップする"""
        assignment1 = schedule.get_assignment(time_slot1, class1)
        assignment2 = schedule.get_assignment(time_slot2, class2)
        
        try:
            # 削除
            if assignment1:
                schedule.remove_assignment(time_slot1, class1)
            if assignment2:
                schedule.remove_assignment(time_slot2, class2)
            
            # スワップして配置
            if assignment2:
                schedule.assign(time_slot1, Assignment(class1, assignment2.subject, assignment2.teacher))
            if assignment1:
                schedule.assign(time_slot2, Assignment(class2, assignment1.subject, assignment1.teacher))
            
            return True
        except:
            # 失敗時は元に戻す
            try:
                if assignment1:
                    schedule.assign(time_slot1, assignment1)
                if assignment2:
                    schedule.assign(time_slot2, assignment2)
            except:
                pass
            return False
    
    def _relocate_assignment(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference
    ) -> bool:
        """配置を別の場所に移動"""
        assignment = schedule.get_assignment(time_slot, class_ref)
        if not assignment:
            return False
        
        days = ["月", "火", "水", "木", "金"]
        
        # 移動先を探す
        for day in days:
            for period in range(1, 6):
                new_slot = TimeSlot(day, period)
                if new_slot == time_slot:
                    continue
                
                if not schedule.get_assignment(new_slot, class_ref):
                    # 教師の可用性を簡易チェック
                    if self._is_teacher_available(schedule, school, new_slot, assignment.teacher):
                        try:
                            schedule.remove_assignment(time_slot, class_ref)
                            new_assignment = Assignment(class_ref, assignment.subject, assignment.teacher)
                            schedule.assign(new_slot, new_assignment)
                            return True
                        except:
                            # 失敗時は元に戻す
                            try:
                                schedule.assign(time_slot, assignment)
                            except:
                                pass
        return False
    
    def _is_teacher_available(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        teacher
    ) -> bool:
        """教師が利用可能かチェック"""
        if not teacher:
            return True
        
        for other_class in school.get_all_classes():
            other_assignment = schedule.get_assignment(time_slot, other_class)
            if (other_assignment and other_assignment.teacher and
                other_assignment.teacher.name == teacher.name):
                # 5組の合同授業は例外
                grade5_classes = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
                if other_class in grade5_classes:
                    continue
                return False
        
        return True
    
    @staticmethod
    def acceptance_probability(delta: float, temperature: float) -> float:
        """シミュレーテッドアニーリングの受理確率
        
        Args:
            delta: スコアの変化量
            temperature: 現在の温度
            
        Returns:
            受理確率（0.0-1.0）
        """
        if delta > 0:
            return 1.0
        try:
            return min(1.0, max(0.0, 2 ** (delta / temperature)))
        except:
            return 0.0