#!/usr/bin/env python3
"""制約違反の包括的分析スクリプト"""
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
    print("=== 制約違反の包括的分析 ===\n")
    
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository(path_config.data_dir)
    school_repo = CSVSchoolRepository(path_config.data_dir)
    
    # 学校データ読み込み
    school = school_repo.load_school_data("config/base_timetable.csv")
    
    # 時間割読み込み
    schedule = schedule_repo.load_desired_schedule(
        str(path_config.default_output_csv),
        school
    )
    
    # 正常パターンの定義
    grade5_group = ["1年5組", "2年5組", "3年5組"]
    exchange_pairs = {
        "1年6組": "1年1組", "1年7組": "1年2組",
        "2年6組": "2年3組", "2年7組": "2年2組",
        "3年6組": "3年3組", "3年7組": "3年2組"
    }
    
    # 1. 教師重複の分析（5組合同授業を除く）
    print("【1. 教師重複違反の分析】")
    teacher_conflicts = 0
    real_teacher_conflicts = []
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            teacher_assignments = defaultdict(list)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject and assignment.teacher:
                    teacher_assignments[assignment.teacher].append({
                        "class": class_ref,
                        "subject": assignment.subject
                    })
            
            # 重複チェック
            for teacher, assignments in teacher_assignments.items():
                if len(assignments) > 1:
                    # 5組合同授業の除外
                    classes = [a["class"] for a in assignments]
                    if set(classes) == set(grade5_group):
                        continue
                    
                    teacher_conflicts += 1
                    real_teacher_conflicts.append({
                        "time": f"{day}{period}校時",
                        "teacher": teacher,
                        "assignments": assignments
                    })
    
    print(f"教師重複違反: {teacher_conflicts}件")
    for i, conflict in enumerate(real_teacher_conflicts[:5]):
        print(f"  - {conflict['time']} {conflict['teacher']}先生: "
              f"{', '.join([f'{a['class']}({a['subject']})' for a in conflict['assignments']])}")
    if len(real_teacher_conflicts) > 5:
        print(f"  ... 他 {len(real_teacher_conflicts) - 5} 件")
    
    # 2. 体育館使用の分析
    print("\n【2. 体育館使用違反の分析】")
    gym_conflicts = 0
    gym_conflict_details = []
    
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
                if set(pe_classes) == set(grade5_group):
                    continue
                
                # 交流学級ペアチェック
                is_valid_pair = False
                for exchange, parent in exchange_pairs.items():
                    if set(pe_classes) == {parent, exchange}:
                        is_valid_pair = True
                        break
                
                if not is_valid_pair:
                    # 各クラスを違反として数える
                    gym_conflicts += len(pe_classes)
                    gym_conflict_details.append({
                        "time": f"{day}{period}校時",
                        "classes": pe_classes
                    })
    
    print(f"体育館使用違反: {gym_conflicts}件")
    for detail in gym_conflict_details[:5]:
        print(f"  - {detail['time']}: {', '.join(detail['classes'])}が同時に体育")
    if len(gym_conflict_details) > 5:
        print(f"  ... 他 {len(gym_conflict_details) - 5} 件")
    
    # 3. 日内重複の分析
    print("\n【3. 日内重複違反の分析】")
    daily_duplicates = 0
    duplicate_details = []
    
    for class_ref in school.get_all_classes():
        for day in ["月", "火", "水", "木", "金"]:
            subject_count = defaultdict(int)
            subject_periods = defaultdict(list)
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if assignment and assignment.subject:
                    subject_count[assignment.subject] += 1
                    subject_periods[assignment.subject].append(period)
            
            for subject, count in subject_count.items():
                if count > 1:
                    # 学総は2コマ連続なら正常
                    if subject == "学総" and count == 2:
                        periods = subject_periods[subject]
                        if len(periods) == 2 and abs(periods[0] - periods[1]) == 1:
                            continue
                    
                    daily_duplicates += 1
                    duplicate_details.append({
                        "class": class_ref,
                        "day": day,
                        "subject": subject,
                        "count": count,
                        "periods": subject_periods[subject]
                    })
    
    print(f"日内重複違反: {daily_duplicates}件")
    for detail in duplicate_details[:5]:
        print(f"  - {detail['class']} {detail['day']}曜日: "
              f"{detail['subject']}が{detail['count']}回（{detail['periods']}校時）")
    if len(duplicate_details) > 5:
        print(f"  ... 他 {len(duplicate_details) - 5} 件")
    
    # 4. 標準時数違反の分析
    print("\n【4. 標準時数違反の分析】")
    hours_violations = 0
    
    for class_ref in ["1年1組", "1年2組", "1年3組", "2年1組", "2年2組", "2年3組", "3年1組", "3年2組", "3年3組"]:
        class_obj = school.get_class_by_reference(class_ref)
        if not class_obj:
            continue
            
        for subject in ["国", "数", "英", "理", "社", "音", "美", "保", "技", "家"]:
            standard_hours = class_obj.get_standard_hours(subject)
            if standard_hours == 0:
                continue
                
            # 実際の時数を計算
            actual_hours = 0
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject == subject:
                        actual_hours += 1
            
            if actual_hours != standard_hours:
                hours_violations += 1
    
    print(f"標準時数違反: {hours_violations}件")
    
    # 5. 空きスロットの分析
    print("\n【5. 空きスロットの分析】")
    empty_slots = 0
    empty_by_class = defaultdict(int)
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                # 空きコマチェック（固定科目は除外）
                if not assignment or not assignment.subject:
                    if not ((day == "月" and period == 6) or 
                           (day in ["火", "水", "金"] and period == 6)):
                        empty_slots += 1
                        empty_by_class[class_ref] += 1
    
    print(f"空きスロット: {empty_slots}件")
    for class_ref, count in list(empty_by_class.items())[:5]:
        print(f"  - {class_ref}: {count}コマ")
    
    # 総計
    print("\n【違反の総計】")
    print(f"1. 教師重複違反: {teacher_conflicts}件")
    print(f"2. 体育館使用違反: {gym_conflicts}件")
    print(f"3. 日内重複違反: {daily_duplicates}件")
    print(f"4. 標準時数違反: {hours_violations}件")
    print(f"5. 空きスロット: {empty_slots}件")
    print(f"合計: {teacher_conflicts + gym_conflicts + daily_duplicates + hours_violations}件（空きスロット除く）")
    
    # 原因分析
    print("\n【原因分析】")
    print("1. 教師重複が多い理由:")
    print("   - 5組合同授業以外でも同じ教師が複数クラスを担当している")
    print("   - 特に金子み先生が通常クラスと5組を同時に担当")
    print("\n2. 体育館使用違反の理由:")
    print("   - 実際の体育の授業が確認できていない（表示の問題？）")
    print("\n3. 標準時数違反の理由:")
    print("   - 空きスロットを埋める際に時数バランスが崩れた")
    print("   - 教師不在による授業削除の影響")


if __name__ == "__main__":
    main()