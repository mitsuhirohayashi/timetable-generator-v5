#!/usr/bin/env python3
"""制約違反を体系的に修正"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from src.domain.value_objects.assignment import Assignment
from collections import defaultdict
import random

class SystematicFixer:
    def __init__(self, schedule, school):
        self.schedule = schedule
        self.school = school
        self.fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"}
        
    def analyze_teacher_workload(self):
        """教師の担当状況を分析"""
        teacher_classes = defaultdict(lambda: defaultdict(list))
        
        # 教師がどのクラスでどの科目を教えているか収集
        for class_ref in self.school.get_all_classes():
            # そのクラスの標準時数から科目を取得
            standard_hours = self.school.get_all_standard_hours(class_ref)
            for subject, hours in standard_hours.items():
                teachers = self.school.get_subject_teachers(subject)
                if teachers:
                    # 実際にこのクラスを担当している教師を特定する必要がある
                    # 今は最初の教師を使用（理想的ではない）
                    teacher = list(teachers)[0] if isinstance(teachers, set) else teachers[0]
                    teacher_classes[teacher.name][subject.name].append(class_ref)
        
        # 問題のある教師を特定（複数クラスを担当）
        problematic_teachers = {}
        for teacher_name, subjects in teacher_classes.items():
            for subject_name, classes in subjects.items():
                if len(classes) > 1:
                    problematic_teachers[teacher_name] = {
                        'subject': subject_name,
                        'classes': classes
                    }
        
        return problematic_teachers
    
    def fix_teacher_conflicts_systematically(self):
        """教師重複を体系的に修正"""
        print("=== 教師重複の体系的修正 ===\n")
        
        # 問題のある教師を分析
        problematic_teachers = self.analyze_teacher_workload()
        print(f"複数クラスを担当している教師: {len(problematic_teachers)}人")
        
        for teacher_name, info in problematic_teachers.items():
            print(f"\n{teacher_name}先生: {info['subject']}を{len(info['classes'])}クラスで担当")
            for class_ref in info['classes']:
                print(f"  - {class_ref}")
        
        # 各教師について、担当クラスの授業を異なる時間に配置
        fixed_count = 0
        for teacher_name, info in problematic_teachers.items():
            subject_name = info['subject']
            classes = info['classes']
            
            # この教師の科目の全ての時間を収集
            time_slots_by_class = defaultdict(list)
            for class_ref in classes:
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 7):
                        time_slot = TimeSlot(day, period)
                        assignment = self.schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.subject.name == subject_name:
                            time_slots_by_class[class_ref].append(time_slot)
            
            # 重複している時間を特定
            time_slot_classes = defaultdict(list)
            for class_ref, time_slots in time_slots_by_class.items():
                for time_slot in time_slots:
                    time_slot_classes[time_slot].append(class_ref)
            
            # 重複を解消
            for time_slot, conflict_classes in time_slot_classes.items():
                if len(conflict_classes) > 1:
                    print(f"\n{time_slot}: {teacher_name}先生の{subject_name}が{len(conflict_classes)}クラスで重複")
                    
                    # 最初のクラス以外を移動
                    for class_ref in conflict_classes[1:]:
                        if self.move_to_free_slot(class_ref, time_slot, subject_name):
                            fixed_count += 1
        
        return fixed_count
    
    def move_to_free_slot(self, class_ref, from_slot, subject_name):
        """授業を空きスロットに移動"""
        if self.schedule.is_locked(from_slot, class_ref):
            return False
        
        # 空きスロットを探す
        for day in ["月", "火", "水", "木", "金"]:
            # 日内重複を避ける
            daily_exists = False
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = self.schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == subject_name:
                    daily_exists = True
                    break
            
            if daily_exists and day != from_slot.day:
                continue
            
            for period in range(1, 7):
                to_slot = TimeSlot(day, period)
                
                if to_slot == from_slot:
                    continue
                
                if not self.schedule.get_assignment(to_slot, class_ref):
                    # 空きスロットに移動
                    assignment = self.schedule.get_assignment(from_slot, class_ref)
                    self.schedule.remove_assignment(from_slot, class_ref)
                    self.schedule.assign(to_slot, assignment)
                    print(f"  {class_ref}: {from_slot}から{to_slot}に移動")
                    return True
        
        # 空きスロットがない場合、交換を試みる
        return self.try_swap_with_other_subject(class_ref, from_slot)
    
    def try_swap_with_other_subject(self, class_ref, from_slot):
        """他の科目と交換"""
        from_assignment = self.schedule.get_assignment(from_slot, class_ref)
        if not from_assignment:
            return False
        
        # 交換候補を探す
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                to_slot = TimeSlot(day, period)
                
                if to_slot == from_slot:
                    continue
                
                to_assignment = self.schedule.get_assignment(to_slot, class_ref)
                if not to_assignment:
                    continue
                
                # 固定科目は交換しない
                if (to_assignment.subject.name in self.fixed_subjects or 
                    from_assignment.subject.name in self.fixed_subjects):
                    continue
                
                # ロックチェック
                if self.schedule.is_locked(to_slot, class_ref):
                    continue
                
                # 交換を実行
                self.schedule.remove_assignment(from_slot, class_ref)
                self.schedule.remove_assignment(to_slot, class_ref)
                self.schedule.assign(from_slot, to_assignment)
                self.schedule.assign(to_slot, from_assignment)
                print(f"  {class_ref}: {from_slot}の{from_assignment.subject.name}と{to_slot}の{to_assignment.subject.name}を交換")
                return True
        
        return False
    
    def fix_gym_conflicts(self):
        """体育館使用違反を修正"""
        print("\n=== 体育館使用違反の修正 ===")
        fixed_count = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間の体育クラスを収集
                pe_classes = []
                for class_ref in self.school.get_all_classes():
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(class_ref)
                
                # 5組の合同体育は許可
                grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
                grade5_pe = [c for c in pe_classes if c in grade5_classes]
                other_pe = [c for c in pe_classes if c not in grade5_classes]
                
                # 5組以外で複数のクラスがある場合
                if len(other_pe) > 1:
                    print(f"\n{time_slot}: {len(other_pe)}クラスが体育で重複")
                    
                    # 2番目以降のクラスを移動
                    for class_ref in other_pe[1:]:
                        if self.move_to_free_slot(class_ref, time_slot, "保"):
                            fixed_count += 1
                
                # 5組と他のクラスが同時の場合
                elif grade5_pe and other_pe:
                    print(f"\n{time_slot}: 5組と通常クラスが体育で重複")
                    
                    # 通常クラスを移動
                    for class_ref in other_pe:
                        if self.move_to_free_slot(class_ref, time_slot, "保"):
                            fixed_count += 1
        
        return fixed_count
    
    def fix_daily_duplicates(self):
        """日内重複を修正"""
        print("\n=== 日内重複の修正 ===")
        fixed_count = 0
        
        for class_ref in self.school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                # その日の科目をカウント
                subject_slots = defaultdict(list)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subject_slots[assignment.subject.name].append(time_slot)
                
                # 重複をチェック
                for subject_name, slots in subject_slots.items():
                    if len(slots) > 1 and subject_name not in self.fixed_subjects:
                        print(f"\n{class_ref}の{day}曜日: {subject_name}が{len(slots)}回重複")
                        
                        # 2つ目以降を他の日に移動
                        for slot in slots[1:]:
                            if self.move_to_free_slot(class_ref, slot, subject_name):
                                fixed_count += 1
        
        return fixed_count

def main():
    print("=== 制約違反の体系的修正 ===\n")
    
    # データ読み込み
    school_repo = CSVSchoolRepository(path_config.config_dir)
    school = school_repo.load_school_data("base_timetable.csv")
    
    schedule_repo = CSVScheduleRepository(path_config.output_dir)
    schedule = schedule_repo.load_desired_schedule("output.csv", school)
    
    # 修正実行
    fixer = SystematicFixer(schedule, school)
    
    # 教師重複を修正
    teacher_fixed = fixer.fix_teacher_conflicts_systematically()
    print(f"\n教師重複: {teacher_fixed}件修正")
    
    # 体育館使用違反を修正
    gym_fixed = fixer.fix_gym_conflicts()
    print(f"\n体育館使用: {gym_fixed}件修正")
    
    # 日内重複を修正
    daily_fixed = fixer.fix_daily_duplicates()
    print(f"\n日内重複: {daily_fixed}件修正")
    
    print(f"\n合計{teacher_fixed + gym_fixed + daily_fixed}件の違反を修正しました")
    
    # 結果を保存
    writer = CSVScheduleWriterImproved()
    writer.write(schedule, path_config.output_dir / "output.csv")
    
    print("\n修正結果をoutput.csvに保存しました")

if __name__ == "__main__":
    main()