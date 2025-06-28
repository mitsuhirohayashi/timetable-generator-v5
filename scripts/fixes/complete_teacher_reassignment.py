#!/usr/bin/env python3
"""教師割り当てを完全に再構築する究極のアプローチ"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from src.domain.value_objects.assignment import Assignment
from collections import defaultdict, deque
import pandas as pd
import json
import random
from typing import Dict, List, Set, Tuple, Optional

class CompleteTeacherReassignment:
    """教師割り当てを完全に再構築"""
    
    def __init__(self, schedule, school):
        self.schedule = schedule
        self.school = school
        self.fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト", "技家"}
        
        # 教師マッピングを再読み込み
        self.load_teacher_mapping()
        
    def load_teacher_mapping(self):
        """教師マッピングを直接読み込み"""
        print("教師マッピングを読み込み中...")
        
        mapping_path = path_config.config_dir / "teacher_subject_mapping.csv"
        df = pd.read_csv(mapping_path)
        
        # 教師が担当可能なクラスを収集
        self.teacher_can_teach = defaultdict(lambda: defaultdict(set))
        self.class_subject_teachers = defaultdict(lambda: defaultdict(list))
        
        for _, row in df.iterrows():
            teacher = row['教員名']
            subject = row['教科']
            grade = row['学年']
            class_num = row['組']
            class_ref = ClassReference(grade, class_num)
            
            self.teacher_can_teach[teacher][subject].add(class_ref)
            self.class_subject_teachers[class_ref][subject].append(teacher)
        
        print(f"教師数: {len(self.teacher_can_teach)}")
        print(f"クラス数: {len(self.class_subject_teachers)}")
    
    def reassign_all_teachers(self):
        """全ての教師割り当てを再構築"""
        print("\n=== 教師割り当ての完全再構築 ===")
        
        # 時間スロットごとに処理
        total_assignments = 0
        successful_assignments = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                print(f"\n{time_slot}を処理中...")
                
                # この時間の全ての授業を収集
                assignments_at_time = []
                for class_ref in self.school.get_all_classes():
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        assignments_at_time.append((class_ref, assignment))
                        total_assignments += 1
                
                # 教師を再割り当て
                teacher_assigned = defaultdict(bool)
                
                # 優先度の高い順に処理（学年順）
                assignments_at_time.sort(key=lambda x: (x[0].grade, x[0].class_number))
                
                for class_ref, assignment in assignments_at_time:
                    subject_name = assignment.subject.name
                    
                    # このクラス・科目を教えられる教師を取得
                    possible_teachers = self.class_subject_teachers[class_ref].get(subject_name, [])
                    
                    # まだこの時間に割り当てられていない教師を探す
                    assigned = False
                    for teacher_name in possible_teachers:
                        if not teacher_assigned[teacher_name]:
                            # 教師の不在をチェック
                            if self.is_teacher_available(teacher_name, time_slot):
                                # 教師を割り当て
                                teacher_obj = self.find_teacher_object(teacher_name)
                                if teacher_obj:
                                    new_assignment = Assignment(
                                        class_ref,
                                        assignment.subject,
                                        teacher_obj
                                    )
                                    self.schedule.remove_assignment(time_slot, class_ref)
                                    self.schedule.assign(time_slot, new_assignment)
                                    teacher_assigned[teacher_name] = True
                                    successful_assignments += 1
                                    assigned = True
                                    print(f"  {class_ref} {subject_name}: {teacher_name}を割り当て")
                                    break
                    
                    if not assigned:
                        # 教師が見つからない場合
                        print(f"  警告: {class_ref} {subject_name}に教師を割り当てられません")
                        # 教師なしで配置
                        new_assignment = Assignment(
                            class_ref,
                            assignment.subject,
                            None
                        )
                        self.schedule.remove_assignment(time_slot, class_ref)
                        self.schedule.assign(time_slot, new_assignment)
        
        print(f"\n総割り当て数: {total_assignments}")
        print(f"成功した割り当て: {successful_assignments}")
        print(f"教師なし: {total_assignments - successful_assignments}")
        
        return successful_assignments
    
    def is_teacher_available(self, teacher_name: str, time_slot: TimeSlot) -> bool:
        """教師がその時間に利用可能かチェック"""
        # Follow-up.csvの不在情報をチェック
        teacher_obj = self.find_teacher_object(teacher_name)
        if teacher_obj and hasattr(self.school, 'is_teacher_unavailable'):
            if self.school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher_obj):
                return False
        return True
    
    def find_teacher_object(self, teacher_name: str):
        """教師名から教師オブジェクトを取得"""
        for teacher in self.school.get_all_teachers():
            if teacher.name == teacher_name:
                return teacher
        return None
    
    def verify_no_conflicts(self):
        """教師の重複がないことを確認"""
        print("\n=== 教師重複チェック ===")
        
        conflicts = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                teacher_at_time = defaultdict(list)
                
                for class_ref in self.school.get_all_classes():
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_at_time[assignment.teacher.name].append(class_ref)
                
                for teacher_name, classes in teacher_at_time.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
                        is_grade5_joint = all(c in grade5_classes for c in classes)
                        
                        if not is_grade5_joint:
                            conflicts += 1
                            print(f"{time_slot}: {teacher_name}先生が{len(classes)}クラスで重複")
                            for c in classes:
                                print(f"  - {c}")
        
        if conflicts == 0:
            print("✓ 教師の重複はありません！")
        else:
            print(f"\n⚠️ {conflicts}件の教師重複が検出されました")
        
        return conflicts

def main():
    print("=== 教師割り当ての完全再構築 ===\n")
    
    # データ読み込み
    school_repo = CSVSchoolRepository(path_config.config_dir)
    school = school_repo.load_school_data("base_timetable.csv")
    
    schedule_repo = CSVScheduleRepository(path_config.output_dir)
    schedule = schedule_repo.load_desired_schedule("output.csv", school)
    
    # 再割り当てを実行
    reassigner = CompleteTeacherReassignment(schedule, school)
    
    # 全ての教師を再割り当て
    successful = reassigner.reassign_all_teachers()
    
    # 結果を検証
    conflicts = reassigner.verify_no_conflicts()
    
    # 結果を保存
    writer = CSVScheduleWriterImproved()
    writer.write(schedule, path_config.output_dir / "output.csv")
    
    print("\n修正結果をoutput.csvに保存しました")
    
    if conflicts == 0:
        print("\n✅ 教師割り当ての再構築が成功しました！")
    else:
        print(f"\n⚠️ まだ{conflicts}件の問題が残っています")

if __name__ == "__main__":
    main()