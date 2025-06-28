#!/usr/bin/env python3
"""制約違反の詳細分析スクリプト"""
import sys
from pathlib import Path
from collections import defaultdict

# timetable_v5ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot

def main():
    """メイン処理"""
    print("=== 制約違反詳細分析 ===\n")
    
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    school_repo = CSVSchoolRepository(path_config.data_dir)
    
    # 学校データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 時間割読み込み
    print(f"時間割を読み込み中: {path_config.default_output_csv}")
    schedule = schedule_repo.load_desired_schedule(
        str(path_config.default_output_csv),
        school
    )
    
    # input.csvの読み込み
    print(f"元の時間割を読み込み中: {path_config.data_dir}/input/input.csv")
    original_schedule = schedule_repo.load_desired_schedule(
        str(Path(path_config.data_dir) / "input" / "input.csv"),
        school
    )
    
    # 1. 教師重複の詳細分析
    print("\n【教師重複の詳細分析】")
    teacher_conflicts = defaultdict(list)
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            teacher_assignments = defaultdict(list)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject and assignment.teacher:
                    teacher_assignments[assignment.teacher].append((class_ref, assignment.subject))
            
            # 重複チェック
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組合同授業の除外
                    grade5_classes = ["1年5組", "2年5組", "3年5組"]
                    if all(cls in grade5_classes for cls, _ in assignments):
                        continue
                    
                    teacher_conflicts[f"{day}{period}校時"].append({
                        "teacher": teacher,
                        "assignments": assignments
                    })
    
    for time, conflicts in teacher_conflicts.items():
        print(f"\n{time}:")
        for conflict in conflicts:
            print(f"  {conflict['teacher']}先生: {', '.join([f'{cls}({subj})' for cls, subj in conflict['assignments']])}")
    
    # 2. 体育館使用の詳細分析
    print("\n\n【体育館使用の詳細分析】")
    gym_conflicts = {}
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            pe_classes = []
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject == "保":
                    pe_classes.append(class_ref)
            
            if len(pe_classes) > 1:
                # 正常パターンの除外
                grade5_group = ["1年5組", "2年5組", "3年5組"]
                exchange_pairs = [
                    ("1年1組", "1年6組"), ("1年2組", "1年7組"),
                    ("2年3組", "2年6組"), ("2年2組", "2年7組"),
                    ("3年3組", "3年6組"), ("3年2組", "3年7組")
                ]
                
                # 5組合同授業チェック
                if set(pe_classes) == set(grade5_group):
                    continue
                
                # 交流学級ペアチェック
                is_valid_pair = False
                for parent, exchange in exchange_pairs:
                    if set(pe_classes) == {parent, exchange}:
                        is_valid_pair = True
                        break
                
                if not is_valid_pair:
                    gym_conflicts[f"{day}{period}校時"] = pe_classes
    
    for time, classes in gym_conflicts.items():
        print(f"\n{time}: {', '.join(classes)}が同時に体育")
    
    # 3. 空きスロットの詳細分析
    print("\n\n【空きスロットの詳細分析】")
    empty_by_class = defaultdict(list)
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                original_assignment = original_schedule.get_assignment(time_slot, class_ref)
                
                if not assignment or not assignment.subject:
                    # 固定科目は除外
                    if not ((day == "月" and period == 6) or 
                           (day in ["火", "水", "金"] and period == 6)):
                        empty_by_class[class_ref].append(f"{day}{period}")
                        
                        # 元々何があったか確認
                        if original_assignment and original_assignment.subject:
                            print(f"{class_ref} {day}{period}校時: 元は'{original_assignment.subject}'が配置されていた")
    
    print("\n【空きスロット集計】")
    for class_ref, slots in sorted(empty_by_class.items(), key=lambda x: str(x[0])):
        print(f"{class_ref}: {len(slots)}コマ ({', '.join(slots)})")
    
    # 4. 日内重複の詳細
    print("\n\n【日内重複の詳細分析】")
    daily_duplicates = []
    
    for class_ref in school.get_all_classes():
        for day in ["月", "火", "水", "木", "金"]:
            subject_count = defaultdict(int)
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if assignment and assignment.subject:
                    subject_count[assignment.subject] += 1
            
            for subject, count in subject_count.items():
                if count > 1:
                    daily_duplicates.append({
                        "class": class_ref,
                        "day": day,
                        "subject": subject,
                        "count": count
                    })
    
    for dup in daily_duplicates:
        print(f"{dup['class']} {dup['day']}曜日: {dup['subject']}が{dup['count']}回")
    
    # 5. 教師不在による削除の影響分析
    print("\n\n【入力ファイルとの差分分析】")
    deleted_assignments = []
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                original = original_schedule.get_assignment(time_slot, class_ref)
                current = schedule.get_assignment(time_slot, class_ref)
                
                # 元々授業があったが現在は空きコマになっている場合
                if original and original.subject and (not current or not current.subject):
                    deleted_assignments.append({
                        "time": f"{day}{period}校時",
                        "class": class_ref,
                        "original_subject": original.subject,
                        "original_teacher": original.teacher
                    })
    
    if deleted_assignments:
        print(f"\n削除された授業: {len(deleted_assignments)}件")
        for del_assign in deleted_assignments[:10]:  # 最初の10件を表示
            print(f"  {del_assign['time']} {del_assign['class']}: "
                  f"{del_assign['original_subject']}({del_assign['original_teacher'] or '教師未設定'})が削除")
        
        if len(deleted_assignments) > 10:
            print(f"  ... 他 {len(deleted_assignments) - 10} 件")


if __name__ == "__main__":
    main()