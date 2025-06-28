#!/usr/bin/env python3
"""最終クリーンアップ: 日内重複修正と残り空きスロット埋め"""

from pathlib import Path
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot, Subject
from src.domain.value_objects.assignment import Assignment
from collections import defaultdict

def main():
    # 初期化
    base_path = Path("data")
    school_repo = CSVSchoolRepository(base_path)
    schedule_repo = CSVScheduleRepository(base_path)
    
    # データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    schedule = schedule_repo.load("output/output.csv", school)
    
    print("=== 最終クリーンアップ ===\n")
    
    # 日内重複をチェック
    print("1. 日内重複の修正")
    duplicates = []
    
    for class_ref in school.get_all_classes():
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            # その日の科目をカウント
            subjects_in_day = defaultdict(int)
            slots_by_subject = defaultdict(list)
            
            for period in range(1, 7):
                slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(slot, class_ref)
                if assignment and assignment.subject:
                    # 固定科目は除外
                    if assignment.subject.name not in ["道", "道徳", "YT", "欠", "総", "総合", "学", "学活", "学総", "行", "行事", "テスト", "技家"]:
                        subjects_in_day[assignment.subject.name] += 1
                        slots_by_subject[assignment.subject.name].append(slot)
            
            # 重複をチェック
            for subject_name, count in subjects_in_day.items():
                if count > 1:
                    duplicates.append({
                        'class': class_ref,
                        'day': day,
                        'subject': subject_name,
                        'count': count,
                        'slots': slots_by_subject[subject_name]
                    })
    
    print(f"  見つかった重複: {len(duplicates)}件")
    
    # 重複を修正
    fixed_duplicates = 0
    for dup in duplicates:
        print(f"\n  {dup['class']} {dup['day']}曜日の{dup['subject']}が{dup['count']}回")
        
        # 最初の1つ以外を他の科目に変更
        for i, slot in enumerate(dup['slots'][1:]):
            # 不足している科目を探す
            shortage_subjects = []
            base_hours = school.get_all_standard_hours(dup['class'])
            
            for subject, required in base_hours.items():
                if subject.name in ["道", "道徳", "YT", "欠", "総", "総合", "学", "学活", "学総", "行", "行事", "テスト", "技家"]:
                    continue
                    
                # 現在の配置数をカウント
                current = 0
                for d in ["月", "火", "水", "木", "金"]:
                    for p in range(1, 7):
                        ts = TimeSlot(d, p)
                        a = schedule.get_assignment(ts, dup['class'])
                        if a and a.subject and a.subject.name == subject.name:
                            current += 1
                
                if current < required:
                    shortage_subjects.append((subject, required - current))
            
            # 不足している科目から選んで配置
            if shortage_subjects:
                # 不足が大きい順にソート
                shortage_subjects.sort(key=lambda x: x[1], reverse=True)
                
                for subject, shortage in shortage_subjects:
                    teacher = school.get_assigned_teacher(subject, dup['class'])
                    if teacher:
                        # その時間に教師が空いているかチェック
                        teacher_busy = False
                        for c in school.get_all_classes():
                            if c != dup['class']:
                                a = schedule.get_assignment(slot, c)
                                if a and a.teacher and a.teacher.name == teacher.name:
                                    teacher_busy = True
                                    break
                        
                        if not teacher_busy:
                            # 配置を変更
                            schedule.remove_assignment(slot, dup['class'])
                            new_assignment = Assignment(dup['class'], subject, teacher)
                            schedule.assign(slot, new_assignment)
                            print(f"    {slot}: {dup['subject']} → {subject.name}")
                            fixed_duplicates += 1
                            break
    
    print(f"\n  修正した重複: {fixed_duplicates}件")
    
    # 残りの空きスロットを埋める
    print("\n2. 残り空きスロットの埋め込み")
    empty_slots = []
    
    for class_ref in school.get_all_classes():
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                slot = TimeSlot(day, period)
                
                # 固定科目スロットはスキップ
                if slot.day == "月" and slot.period == 6:
                    continue
                if slot.day in ["火", "水", "金"] and slot.period == 6:
                    continue
                if slot.day == "木" and slot.period == 4:
                    continue
                
                assignment = schedule.get_assignment(slot, class_ref)
                if not assignment:
                    empty_slots.append((slot, class_ref))
    
    print(f"  空きスロット: {len(empty_slots)}個")
    
    filled = 0
    for slot, class_ref in empty_slots:
        print(f"\n  {class_ref} {slot}:")
        
        # 配置可能な科目を探す
        candidates = []
        base_hours = school.get_all_standard_hours(class_ref)
        
        for subject, required in base_hours.items():
            if subject.name in ["道", "道徳", "YT", "欠", "総", "総合", "学", "学活", "学総", "行", "行事", "テスト", "技家"]:
                continue
            
            teacher = school.get_assigned_teacher(subject, class_ref)
            if not teacher:
                continue
            
            # 教師が空いているか
            teacher_available = True
            for c in school.get_all_classes():
                a = schedule.get_assignment(slot, c)
                if a and a.teacher and a.teacher.name == teacher.name:
                    teacher_available = False
                    break
            
            if teacher_available:
                # その日に既に配置されていないか
                already_placed = False
                for p in range(1, 7):
                    ts = TimeSlot(slot.day, p)
                    a = schedule.get_assignment(ts, class_ref)
                    if a and a.subject and a.subject.name == subject.name:
                        already_placed = True
                        break
                
                if not already_placed:
                    candidates.append((subject, teacher))
        
        if candidates:
            # 最初の候補を配置
            subject, teacher = candidates[0]
            assignment = Assignment(class_ref, subject, teacher)
            schedule.assign(slot, assignment)
            print(f"    → {subject.name} ({teacher.name})")
            filled += 1
        else:
            print(f"    → 配置できる科目がありません")
    
    print(f"\n  埋めたスロット: {filled}個")
    
    # 保存
    if fixed_duplicates > 0 or filled > 0:
        schedule_repo.save_schedule(schedule, "output.csv")
        print(f"\n結果をdata/output/output.csvに保存しました")
        print(f"修正内容: 重複{fixed_duplicates}件、空きスロット{filled}個")
    else:
        print("\n修正は必要ありませんでした")

if __name__ == "__main__":
    main()