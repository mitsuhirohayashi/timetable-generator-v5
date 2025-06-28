#!/usr/bin/env python3
"""高度な制約充足アルゴリズムによる時間割生成"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from src.domain.value_objects.assignment import Assignment
from src.domain.entities.schedule import Schedule
from collections import defaultdict, deque
import random
import json
import copy

class AdvancedConstraintSolver:
    """高度な制約充足ソルバー"""
    
    def __init__(self, school):
        self.school = school
        self.fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"}
        
        # 教師分析結果を読み込み
        self.load_teacher_analysis()
        
        # 時間割のドメインを構築
        self.domains = {}  # {(class_ref, time_slot): [possible_subjects]}
        self.teacher_schedule = defaultdict(dict)  # {teacher: {time_slot: class_ref}}
        
    def load_teacher_analysis(self):
        """教師分析結果を読み込み"""
        try:
            with open('teacher_analysis_results.json', 'r', encoding='utf-8') as f:
                self.teacher_analysis = json.load(f)
                self.problematic_teachers = self.teacher_analysis['problematic_teachers']
        except:
            self.problematic_teachers = {}
    
    def solve(self, initial_schedule):
        """高度な制約充足アルゴリズムで解決"""
        print("=== 高度な制約充足アルゴリズムによる解決 ===\n")
        
        # 1. 現在のスケジュールを分析
        self.analyze_current_schedule(initial_schedule)
        
        # 2. 制約グラフを構築
        constraint_graph = self.build_constraint_graph(initial_schedule)
        
        # 3. 最小残余値（MRV）ヒューリスティックで変数順序を決定
        variable_order = self.get_variable_ordering(constraint_graph)
        
        # 4. バックトラッキング検索で解を探索
        solution = self.backtrack_search(initial_schedule, variable_order, constraint_graph)
        
        return solution
    
    def analyze_current_schedule(self, schedule):
        """現在のスケジュールを分析"""
        print("現在のスケジュールを分析中...")
        
        # 教師の現在の割り当てを収集
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.teacher:
                self.teacher_schedule[assignment.teacher.name][time_slot] = assignment.class_ref
        
        # 各クラスの必要時数と配置済み時数を計算
        self.required_hours = {}
        self.placed_hours = defaultdict(lambda: defaultdict(int))
        
        for class_ref in self.school.get_all_classes():
            standard_hours = self.school.get_all_standard_hours(class_ref)
            self.required_hours[class_ref] = {
                subject.name: int(hours) for subject, hours in standard_hours.items()
            }
            
            # 配置済みの時数をカウント
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        self.placed_hours[class_ref][assignment.subject.name] += 1
    
    def build_constraint_graph(self, schedule):
        """制約グラフを構築"""
        print("制約グラフを構築中...")
        
        graph = defaultdict(list)
        
        # 各時間枠での制約を収集
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間に授業があるクラスを収集
                classes_at_time = []
                for class_ref in self.school.get_all_classes():
                    if not schedule.is_locked(time_slot, class_ref):
                        classes_at_time.append(class_ref)
                
                # 教師制約：同じ教師は同時に複数クラスを教えられない
                for i, class1 in enumerate(classes_at_time):
                    for class2 in classes_at_time[i+1:]:
                        graph[(class1, time_slot)].append((class2, time_slot))
                        graph[(class2, time_slot)].append((class1, time_slot))
        
        return graph
    
    def get_variable_ordering(self, constraint_graph):
        """MRVヒューリスティックで変数順序を決定"""
        print("変数順序を決定中...")
        
        # 教師の重複が多い時間枠を優先
        conflict_counts = defaultdict(int)
        
        for teacher, time_classes in self.teacher_schedule.items():
            for time_slot, class_ref in time_classes.items():
                # この時間に同じ教師が複数クラスを担当しているか
                classes_at_time = [c for t, c in time_classes.items() if t == time_slot]
                if len(classes_at_time) > 1:
                    for c in classes_at_time:
                        conflict_counts[(c, time_slot)] += 1
        
        # 衝突が多い順にソート
        variables = sorted(conflict_counts.keys(), key=lambda x: conflict_counts[x], reverse=True)
        
        # 衝突がない変数も追加
        for class_ref in self.school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    var = (class_ref, time_slot)
                    if var not in variables:
                        variables.append(var)
        
        return variables[:100]  # 最も問題のある100個の変数に限定
    
    def backtrack_search(self, schedule, variable_order, constraint_graph):
        """バックトラッキング検索"""
        print("\nバックトラッキング検索を開始...")
        
        # 作業用のスケジュールをコピー
        working_schedule = self.copy_schedule(schedule)
        
        # 再帰的に解を探索
        result = self._backtrack(working_schedule, variable_order, 0, constraint_graph)
        
        if result:
            print("解が見つかりました！")
        else:
            print("完全な解は見つかりませんでしたが、部分的な改善を適用します")
            result = working_schedule
        
        return result
    
    def _backtrack(self, schedule, variables, var_index, constraint_graph, depth=0, max_depth=50):
        """バックトラッキングの再帰関数"""
        if depth > max_depth or var_index >= len(variables):
            return schedule
        
        class_ref, time_slot = variables[var_index]
        
        # この変数がすでにロックされている場合はスキップ
        if schedule.is_locked(time_slot, class_ref):
            return self._backtrack(schedule, variables, var_index + 1, constraint_graph, depth)
        
        # 現在の割り当てを保存
        current_assignment = schedule.get_assignment(time_slot, class_ref)
        
        # この変数の可能な値（教師の再割り当て）を試す
        values = self.get_possible_values(schedule, class_ref, time_slot)
        
        for new_teacher in values:
            if self.is_consistent(schedule, class_ref, time_slot, new_teacher):
                # 割り当てを更新
                if current_assignment:
                    old_teacher = current_assignment.teacher
                    new_assignment = Assignment(
                        current_assignment.class_ref,
                        current_assignment.subject,
                        new_teacher
                    )
                    schedule.remove_assignment(time_slot, class_ref)
                    schedule.assign(time_slot, new_assignment)
                    
                    # 教師スケジュールを更新
                    if old_teacher and old_teacher.name in self.teacher_schedule:
                        if time_slot in self.teacher_schedule[old_teacher.name]:
                            del self.teacher_schedule[old_teacher.name][time_slot]
                    if new_teacher:
                        self.teacher_schedule[new_teacher.name][time_slot] = class_ref
                    
                    # 再帰的に次の変数を処理
                    result = self._backtrack(schedule, variables, var_index + 1, 
                                           constraint_graph, depth + 1)
                    if result:
                        return result
                    
                    # バックトラック
                    schedule.remove_assignment(time_slot, class_ref)
                    schedule.assign(time_slot, current_assignment)
                    if new_teacher and new_teacher.name in self.teacher_schedule:
                        if time_slot in self.teacher_schedule[new_teacher.name]:
                            del self.teacher_schedule[new_teacher.name][time_slot]
                    if old_teacher:
                        self.teacher_schedule[old_teacher.name][time_slot] = class_ref
        
        # この変数では解が見つからなかった
        return None
    
    def get_possible_values(self, schedule, class_ref, time_slot):
        """可能な教師のリストを取得"""
        assignment = schedule.get_assignment(time_slot, class_ref)
        if not assignment:
            return []
        
        subject = assignment.subject
        teachers = self.school.get_subject_teachers(subject)
        
        # 現在の教師を除外
        current_teacher = assignment.teacher
        available_teachers = []
        
        for teacher in teachers:
            if teacher != current_teacher:
                available_teachers.append(teacher)
        
        # Noneも候補に追加（教師なし）
        available_teachers.append(None)
        
        return available_teachers
    
    def is_consistent(self, schedule, class_ref, time_slot, new_teacher):
        """制約を満たすかチェック"""
        if not new_teacher:
            return True
        
        # この時間に同じ教師が他のクラスを担当していないか
        if time_slot in self.teacher_schedule.get(new_teacher.name, {}):
            other_class = self.teacher_schedule[new_teacher.name][time_slot]
            if other_class != class_ref:
                return False
        
        # 教師の不在をチェック
        if hasattr(self.school, 'is_teacher_unavailable'):
            if self.school.is_teacher_unavailable(time_slot.day, time_slot.period, new_teacher):
                return False
        
        return True
    
    def copy_schedule(self, schedule):
        """スケジュールのディープコピー"""
        new_schedule = Schedule()
        
        for time_slot, assignment in schedule.get_all_assignments():
            new_schedule.assign(time_slot, assignment)
            if schedule.is_locked(time_slot, assignment.class_ref):
                new_schedule.lock_cell(time_slot, assignment.class_ref)
        
        return new_schedule
    
    def apply_local_improvements(self, schedule):
        """局所的な改善を適用"""
        print("\n局所的な改善を適用中...")
        
        improvements = 0
        
        # 教師の重複を1つずつ解消
        for teacher, time_classes in list(self.teacher_schedule.items()):
            time_slot_classes = defaultdict(list)
            
            for time_slot, class_ref in time_classes.items():
                time_slot_classes[time_slot].append(class_ref)
            
            for time_slot, classes in time_slot_classes.items():
                if len(classes) > 1:
                    print(f"\n{time_slot}: {teacher}先生が{len(classes)}クラスで重複")
                    
                    # 最初のクラス以外を別の教師に変更
                    for class_ref in classes[1:]:
                        if self.reassign_teacher(schedule, class_ref, time_slot, teacher):
                            improvements += 1
        
        print(f"\n{improvements}件の改善を適用しました")
        return schedule
    
    def reassign_teacher(self, schedule, class_ref, time_slot, current_teacher_name):
        """教師を再割り当て"""
        assignment = schedule.get_assignment(time_slot, class_ref)
        if not assignment or schedule.is_locked(time_slot, class_ref):
            return False
        
        # 他の利用可能な教師を探す
        subject = assignment.subject
        teachers = self.school.get_subject_teachers(subject)
        
        for teacher in teachers:
            if teacher.name != current_teacher_name:
                if self.is_consistent(schedule, class_ref, time_slot, teacher):
                    # 再割り当て
                    new_assignment = Assignment(class_ref, subject, teacher)
                    schedule.remove_assignment(time_slot, class_ref)
                    schedule.assign(time_slot, new_assignment)
                    
                    # 教師スケジュールを更新
                    if current_teacher_name in self.teacher_schedule:
                        if time_slot in self.teacher_schedule[current_teacher_name]:
                            classes = self.teacher_schedule[current_teacher_name][time_slot]
                            if isinstance(classes, list) and class_ref in classes:
                                classes.remove(class_ref)
                            elif classes == class_ref:
                                del self.teacher_schedule[current_teacher_name][time_slot]
                    
                    self.teacher_schedule[teacher.name][time_slot] = class_ref
                    
                    print(f"  {class_ref}: {current_teacher_name}先生から{teacher.name}先生に変更")
                    return True
        
        return False

def main():
    print("=== 高度な制約充足アルゴリズムによる時間割修正 ===\n")
    
    # データ読み込み
    school_repo = CSVSchoolRepository(path_config.config_dir)
    school = school_repo.load_school_data("base_timetable.csv")
    
    schedule_repo = CSVScheduleRepository(path_config.output_dir)
    initial_schedule = schedule_repo.load_desired_schedule("output.csv", school)
    
    # ソルバーを実行
    solver = AdvancedConstraintSolver(school)
    
    # バックトラッキング検索
    improved_schedule = solver.solve(initial_schedule)
    
    # 局所的な改善
    final_schedule = solver.apply_local_improvements(improved_schedule)
    
    # 結果を保存
    writer = CSVScheduleWriterImproved()
    writer.write(final_schedule, path_config.output_dir / "output.csv")
    
    print("\n修正結果をoutput.csvに保存しました")

if __name__ == "__main__":
    main()