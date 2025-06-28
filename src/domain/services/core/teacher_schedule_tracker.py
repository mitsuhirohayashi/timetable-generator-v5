"""教師スケジュール追跡サービス

教師の配置状況を詳細に追跡し、重複を防止する。
"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import TimeSlot, ClassReference, Teacher
from ...value_objects.assignment import Assignment


class TeacherScheduleTracker(LoggingMixin):
    """教師スケジュール追跡サービス"""
    
    def __init__(self):
        super().__init__()
        
        # 教師ごとのスケジュール
        # teacher_name -> {time_slot: List[ClassReference]}
        self.teacher_schedules: Dict[str, Dict[TimeSlot, List[ClassReference]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # 5組クラスのセット
        self.grade5_classes = {
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        }
        
        # 学習ルール（特定の教師の制限）
        self.teacher_time_limits = {
            "井上": {("火", 5): 1},  # 火曜5限は最大1クラス
            "白石": {("火", 5): 1},  # 火曜5限は最大1クラス（理科実験室の制約）
        }
        
        # 統計情報
        self.stats = {
            'total_assignments': 0,
            'grade5_joint_classes': 0,
            'conflicts_prevented': 0,
            'rule_violations_prevented': 0
        }
    
    def initialize_from_schedule(self, schedule: Schedule, school: School):
        """既存のスケジュールから初期化"""
        self.logger.info("教師スケジュールを初期化中...")
        self.teacher_schedules.clear()
        
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and assignment.teacher:
                        self._register_assignment(
                            assignment.teacher.name, time_slot, class_ref
                        )
        
        self.logger.info(
            f"初期化完了: {len(self.teacher_schedules)}人の教師、"
            f"{self.stats['total_assignments']}件の割り当て"
        )
    
    def can_assign_teacher(self, teacher: Teacher, time_slot: TimeSlot,
                         class_ref: ClassReference) -> Tuple[bool, Optional[str]]:
        """教師を割り当て可能かチェック
        
        Returns:
            (可能か, エラーメッセージ)
        """
        if not teacher:
            return True, None
        
        teacher_name = teacher.name
        
        # 1. 学習ルールのチェック
        if teacher_name in self.teacher_time_limits:
            time_key = (time_slot.day, time_slot.period)
            if time_key in self.teacher_time_limits[teacher_name]:
                max_classes = self.teacher_time_limits[teacher_name][time_key]
                current_classes = self.teacher_schedules[teacher_name].get(time_slot, [])
                
                if len(current_classes) >= max_classes:
                    self.stats['rule_violations_prevented'] += 1
                    return False, (
                        f"{teacher_name}先生は{time_slot}に最大{max_classes}クラスまで"
                        f"（現在{len(current_classes)}クラス）"
                    )
        
        # 2. 既存の割り当てをチェック
        current_classes = self.teacher_schedules[teacher_name].get(time_slot, [])
        
        if not current_classes:
            return True, None
        
        # 3. 5組の合同授業チェック
        if class_ref in self.grade5_classes:
            # 既存の割り当てが全て5組なら、この5組も追加可能
            if all(c in self.grade5_classes for c in current_classes):
                return True, None
        
        # 4. 通常の重複チェック
        if current_classes:
            self.stats['conflicts_prevented'] += 1
            classes_str = ", ".join(str(c) for c in current_classes)
            return False, f"{teacher_name}先生は既に{time_slot}に{classes_str}を担当"
        
        return True, None
    
    def register_assignment(self, teacher: Teacher, time_slot: TimeSlot,
                          class_ref: ClassReference):
        """教師の割り当てを登録"""
        if teacher:
            self._register_assignment(teacher.name, time_slot, class_ref)
    
    def _register_assignment(self, teacher_name: str, time_slot: TimeSlot,
                           class_ref: ClassReference):
        """内部的な割り当て登録"""
        self.teacher_schedules[teacher_name][time_slot].append(class_ref)
        self.stats['total_assignments'] += 1
        
        # 5組の合同授業かチェック
        classes = self.teacher_schedules[teacher_name][time_slot]
        if len(classes) > 1 and all(c in self.grade5_classes for c in classes):
            self.stats['grade5_joint_classes'] += 1
    
    def unregister_assignment(self, teacher: Teacher, time_slot: TimeSlot,
                            class_ref: ClassReference):
        """教師の割り当てを解除"""
        if not teacher:
            return
        
        teacher_name = teacher.name
        if time_slot in self.teacher_schedules[teacher_name]:
            if class_ref in self.teacher_schedules[teacher_name][time_slot]:
                self.teacher_schedules[teacher_name][time_slot].remove(class_ref)
                self.stats['total_assignments'] -= 1
                
                # リストが空になったら削除
                if not self.teacher_schedules[teacher_name][time_slot]:
                    del self.teacher_schedules[teacher_name][time_slot]
    
    def get_teacher_load(self, teacher_name: str) -> Dict[str, int]:
        """教師の負荷情報を取得"""
        load_info = {
            'total_classes': 0,
            'by_day': defaultdict(int),
            'max_classes_per_slot': 0,
            'conflict_slots': []
        }
        
        if teacher_name not in self.teacher_schedules:
            return load_info
        
        for time_slot, classes in self.teacher_schedules[teacher_name].items():
            num_classes = len(classes)
            load_info['total_classes'] += num_classes
            load_info['by_day'][time_slot.day] += 1
            
            if num_classes > 1:
                # 5組の合同授業でない場合は競合
                if not all(c in self.grade5_classes for c in classes):
                    load_info['conflict_slots'].append(time_slot)
            
            load_info['max_classes_per_slot'] = max(
                load_info['max_classes_per_slot'], num_classes
            )
        
        return load_info
    
    def get_available_teachers(self, time_slot: TimeSlot, 
                             subject_teachers: List[Teacher]) -> List[Teacher]:
        """指定時間に利用可能な教師のリストを取得"""
        available = []
        
        for teacher in subject_teachers:
            can_assign, _ = self.can_assign_teacher(teacher, time_slot, None)
            if can_assign:
                available.append(teacher)
        
        return available
    
    def find_conflicts(self) -> List[Dict]:
        """現在の教師重複を検出"""
        conflicts = []
        
        for teacher_name, schedule in self.teacher_schedules.items():
            for time_slot, classes in schedule.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for c in classes if c in self.grade5_classes)
                    if grade5_count < len(classes):
                        conflicts.append({
                            'teacher': teacher_name,
                            'time_slot': time_slot,
                            'classes': classes,
                            'is_mixed': 0 < grade5_count < len(classes)
                        })
        
        return conflicts
    
    def suggest_teacher_for_slot(self, school: School, subject_name: str,
                                time_slot: TimeSlot, class_ref: ClassReference) -> Optional[Teacher]:
        """最適な教師を提案"""
        # 科目の担当可能教師を取得
        subject = next((s for s in school.subjects if s.name == subject_name), None)
        if not subject:
            return None
        
        possible_teachers = school.get_teachers_for_subject(subject)
        if not possible_teachers:
            return None
        
        # 各教師を評価
        teacher_scores = []
        for teacher in possible_teachers:
            can_assign, error = self.can_assign_teacher(teacher, time_slot, class_ref)
            if not can_assign:
                continue
            
            # スコア計算（負荷が低い教師を優先）
            load_info = self.get_teacher_load(teacher.name)
            score = 100
            score -= load_info['total_classes'] * 2
            score -= load_info['by_day'].get(time_slot.day, 0) * 5
            score -= len(load_info['conflict_slots']) * 10
            
            teacher_scores.append((teacher, score))
        
        if not teacher_scores:
            return None
        
        # 最高スコアの教師を返す
        teacher_scores.sort(key=lambda x: x[1], reverse=True)
        return teacher_scores[0][0]
    
    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        stats = self.stats.copy()
        
        # 教師別の統計も追加
        teacher_stats = []
        for teacher_name in self.teacher_schedules:
            load_info = self.get_teacher_load(teacher_name)
            teacher_stats.append({
                'name': teacher_name,
                'total_classes': load_info['total_classes'],
                'conflicts': len(load_info['conflict_slots'])
            })
        
        # 負荷順にソート
        teacher_stats.sort(key=lambda x: x['total_classes'], reverse=True)
        stats['top_loaded_teachers'] = teacher_stats[:10]
        
        return stats