#!/usr/bin/env python3
"""教師重複を根本的に解決する高度なアプローチ"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from src.domain.value_objects.assignment import Assignment
from collections import defaultdict, deque
import json
import random
from typing import Dict, List, Set, Tuple, Optional

class RadicalTeacherFixer:
    """教師重複を根本的に解決するクラス"""
    
    def __init__(self, schedule, school):
        self.schedule = schedule
        self.school = school
        self.fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト", "技家"}
        
        # 教師分析結果を読み込み
        self.load_teacher_analysis()
        
        # 解決履歴
        self.solution_history = []
        
    def load_teacher_analysis(self):
        """教師分析結果を読み込み"""
        try:
            with open('teacher_analysis_results.json', 'r', encoding='utf-8') as f:
                self.teacher_analysis = json.load(f)
                self.problematic_teachers = self.teacher_analysis['problematic_teachers']
                print(f"問題のある教師数: {len(self.problematic_teachers)}人")
        except:
            self.problematic_teachers = {}
            print("教師分析結果が見つかりません")
    
    def analyze_current_state(self) -> Dict:
        """現在の状態を詳細分析"""
        print("\n=== 現在の状態分析 ===")
        
        # 教師ごとの時間割を収集
        teacher_schedule = defaultdict(lambda: defaultdict(list))
        
        for time_slot, assignment in self.schedule.get_all_assignments():
            if assignment.teacher:
                teacher_schedule[assignment.teacher.name][time_slot].append(
                    (assignment.class_ref, assignment.subject.name)
                )
        
        # 重複を検出
        conflicts = []
        for teacher_name, time_slots in teacher_schedule.items():
            for time_slot, classes in time_slots.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
                    is_grade5_joint = all(class_ref in grade5_classes for class_ref, _ in classes)
                    
                    if not is_grade5_joint:
                        conflicts.append({
                            'teacher': teacher_name,
                            'time_slot': time_slot,
                            'classes': classes,
                            'conflict_count': len(classes)
                        })
        
        print(f"検出された重複: {len(conflicts)}件")
        
        # 最も深刻な重複を表示
        conflicts.sort(key=lambda x: x['conflict_count'], reverse=True)
        for conflict in conflicts[:5]:
            print(f"  {conflict['time_slot']}: {conflict['teacher']}先生が{conflict['conflict_count']}クラスで重複")
        
        return {
            'teacher_schedule': teacher_schedule,
            'conflicts': conflicts,
            'total_conflicts': len(conflicts)
        }
    
    def find_alternative_teachers(self, subject_name: str, excluded_teacher: str) -> List[str]:
        """代替教師を探す"""
        subject = Subject(subject_name)
        all_teachers = self.school.get_subject_teachers(subject)
        
        if not all_teachers:
            return []
        
        # 除外する教師以外を返す
        alternatives = []
        for teacher in all_teachers:
            if teacher and teacher.name != excluded_teacher:
                alternatives.append(teacher.name)
        
        return alternatives
    
    def can_teacher_teach_at(self, teacher_name: str, time_slot: TimeSlot) -> bool:
        """教師がその時間に教えられるかチェック"""
        # 教師の不在をチェック
        teachers = [t for t in self.school.get_all_teachers() if t.name == teacher_name]
        if teachers and hasattr(self.school, 'is_teacher_unavailable'):
            if self.school.is_teacher_unavailable(time_slot.day, time_slot.period, teachers[0]):
                return False
        
        # すでに他のクラスを担当していないかチェック
        for class_ref in self.school.get_all_classes():
            assignment = self.schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                return False
        
        return True
    
    def reassign_teacher_for_class(self, time_slot: TimeSlot, class_ref: ClassReference, 
                                  new_teacher_name: Optional[str]) -> bool:
        """特定のクラスの教師を再割り当て"""
        assignment = self.schedule.get_assignment(time_slot, class_ref)
        if not assignment or self.schedule.is_locked(time_slot, class_ref):
            return False
        
        # 新しい教師を取得
        new_teacher = None
        if new_teacher_name:
            teachers = [t for t in self.school.get_all_teachers() if t.name == new_teacher_name]
            new_teacher = teachers[0] if teachers else None
        
        # 新しい割り当てを作成
        new_assignment = Assignment(
            assignment.class_ref,
            assignment.subject,
            new_teacher
        )
        
        # 再割り当て
        self.schedule.remove_assignment(time_slot, class_ref)
        self.schedule.assign(time_slot, new_assignment)
        
        old_teacher = assignment.teacher.name if assignment.teacher else "なし"
        new_teacher_display = new_teacher_name if new_teacher_name else "なし"
        print(f"    {class_ref}: {old_teacher} → {new_teacher_display}")
        
        return True
    
    def fix_single_conflict(self, conflict: Dict) -> bool:
        """単一の重複を解決"""
        time_slot = conflict['time_slot']
        teacher_name = conflict['teacher']
        classes = conflict['classes']
        
        print(f"\n{time_slot}: {teacher_name}先生の重複を解決中...")
        
        # 最初のクラスは残し、残りのクラスに代替教師を割り当てる
        keep_class = classes[0][0]  # 最初のクラスを維持
        subject_name = classes[0][1]
        
        # 代替教師を探す
        alternatives = self.find_alternative_teachers(subject_name, teacher_name)
        
        success_count = 0
        for i, (class_ref, subject) in enumerate(classes[1:], 1):
            # 代替教師を順に試す
            assigned = False
            
            for alt_teacher in alternatives:
                if self.can_teacher_teach_at(alt_teacher, time_slot):
                    if self.reassign_teacher_for_class(time_slot, class_ref, alt_teacher):
                        success_count += 1
                        assigned = True
                        break
            
            if not assigned:
                # 代替教師が見つからない場合、教師なしで配置
                if self.reassign_teacher_for_class(time_slot, class_ref, None):
                    success_count += 1
                    print(f"    警告: {class_ref}に代替教師が見つからず、教師なしで配置")
        
        return success_count > 0
    
    def move_conflicting_class(self, conflict: Dict, class_to_move: ClassReference) -> bool:
        """重複しているクラスを別の時間に移動"""
        time_slot = conflict['time_slot']
        assignment = self.schedule.get_assignment(time_slot, class_to_move)
        
        if not assignment or self.schedule.is_locked(time_slot, class_to_move):
            return False
        
        # 移動先を探す
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                new_slot = TimeSlot(day, period)
                
                if new_slot == time_slot:
                    continue
                
                # 空きスロットかチェック
                if not self.schedule.get_assignment(new_slot, class_to_move):
                    # 教師が空いているかチェック
                    if assignment.teacher and self.can_teacher_teach_at(assignment.teacher.name, new_slot):
                        # 移動実行
                        self.schedule.remove_assignment(time_slot, class_to_move)
                        self.schedule.assign(new_slot, assignment)
                        print(f"    {class_to_move}: {time_slot} → {new_slot}に移動")
                        return True
        
        return False
    
    def apply_radical_fix(self) -> int:
        """根本的な修正を適用"""
        print("\n=== 根本的な教師重複修正 ===")
        
        fixed_count = 0
        max_iterations = 10
        
        for iteration in range(max_iterations):
            print(f"\n反復 {iteration + 1}/{max_iterations}")
            
            # 現在の状態を分析
            state = self.analyze_current_state()
            conflicts = state['conflicts']
            
            if not conflicts:
                print("✓ 全ての教師重複が解消されました！")
                break
            
            # 各重複を処理
            iteration_fixed = 0
            for conflict in conflicts[:20]:  # 一度に20件まで処理
                if self.fix_single_conflict(conflict):
                    iteration_fixed += 1
                    fixed_count += 1
                else:
                    # 代替教師での解決が失敗した場合、授業を移動
                    classes = conflict['classes']
                    for class_ref, _ in classes[1:]:
                        if self.move_conflicting_class(conflict, class_ref):
                            iteration_fixed += 1
                            fixed_count += 1
                            break
            
            print(f"この反復で{iteration_fixed}件修正")
            
            if iteration_fixed == 0:
                print("進展がないため終了")
                break
        
        return fixed_count
    
    def verify_solution(self) -> Dict:
        """解決策を検証"""
        print("\n=== 解決策の検証 ===")
        
        final_state = self.analyze_current_state()
        
        print(f"\n残存する重複: {final_state['total_conflicts']}件")
        
        # 教師なしの授業をカウント
        no_teacher_count = 0
        for time_slot, assignment in self.schedule.get_all_assignments():
            if not assignment.teacher and assignment.subject.name not in self.fixed_subjects:
                no_teacher_count += 1
        
        print(f"教師なしの授業: {no_teacher_count}件")
        
        return {
            'remaining_conflicts': final_state['total_conflicts'],
            'no_teacher_assignments': no_teacher_count,
            'success': final_state['total_conflicts'] == 0
        }

def main():
    print("=== 教師重複の根本的解決 ===\n")
    
    # データ読み込み
    school_repo = CSVSchoolRepository(path_config.config_dir)
    school = school_repo.load_school_data("base_timetable.csv")
    
    schedule_repo = CSVScheduleRepository(path_config.output_dir)
    schedule = schedule_repo.load_desired_schedule("output.csv", school)
    
    # 修正を実行
    fixer = RadicalTeacherFixer(schedule, school)
    
    # 初期状態を分析
    initial_state = fixer.analyze_current_state()
    print(f"\n初期状態: {initial_state['total_conflicts']}件の教師重複")
    
    # 根本的な修正を適用
    fixed_count = fixer.apply_radical_fix()
    print(f"\n合計{fixed_count}件の修正を実行")
    
    # 結果を検証
    verification = fixer.verify_solution()
    
    if verification['success']:
        print("\n✅ 全ての教師重複が解消されました！")
    else:
        print(f"\n⚠️ {verification['remaining_conflicts']}件の重複が残っています")
        if verification['no_teacher_assignments'] > 0:
            print(f"   {verification['no_teacher_assignments']}件の授業に教師が割り当てられていません")
    
    # 結果を保存
    writer = CSVScheduleWriterImproved()
    writer.write(schedule, path_config.output_dir / "output.csv")
    
    print("\n修正結果をoutput.csvに保存しました")

if __name__ == "__main__":
    main()