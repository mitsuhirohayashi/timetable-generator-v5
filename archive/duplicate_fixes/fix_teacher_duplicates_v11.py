#!/usr/bin/env python3
"""V11で生成した時間割の教師重複を修正"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import TimeSlot, Subject, Teacher
from src.domain.value_objects.assignment import Assignment
from collections import defaultdict
import random

# リポジトリを直接作成
school_repo = CSVSchoolRepository(path_config.data_dir)
school = school_repo.load_school_data("config/base_timetable.csv")
schedule_repo = CSVScheduleRepository(path_config.data_dir)

# output.csvを読み込み
schedule = schedule_repo.load("data/output/output.csv", school)

print("=== 教師重複の修正 ===")

# 修正対象の重複（手動で特定）
duplicates_to_fix = [
    ("月", 5, "梶永先生", [("1年1組", "数"), ("1年3組", "数")]),
    ("月", 5, "智田先生", [("2年1組", "理"), ("2年7組", "自立")]),
    ("月", 5, "北先生", [("3年2組", "社"), ("3年3組", "社")]),
    ("水", 3, "寺田先生", [("1年2組", "国"), ("2年1組", "国")]),
    ("木", 1, "白石先生", [("3年1組", "理"), ("3年2組", "理")])
]

# 修正実行
fixed_count = 0

for day, period, teacher_name, conflicts in duplicates_to_fix:
    print(f"\n{day}{period}限の{teacher_name}先生の重複を修正")
    time_slot = TimeSlot(day, period)
    
    # 2番目以降のクラスを別の時間に移動
    for i, (class_str, subject) in enumerate(conflicts):
        if i == 0:
            print(f"  {class_str}の{subject}は維持")
            continue
        
        # クラス参照を作成
        parts = class_str.replace("年", "-").replace("組", "").split("-")
        grade = int(parts[0])
        class_num = int(parts[1])
        class_ref = None
        for c in school.get_all_classes():
            if c.grade == grade and c.class_number == class_num:
                class_ref = c
                break
        
        if not class_ref:
            print(f"  {class_str}が見つかりません")
            continue
        
        # 現在の配置を削除
        schedule.remove_assignment(time_slot, class_ref)
        print(f"  {class_str}の{subject}を削除")
        
        # 空いている時間を探す
        found = False
        for alt_day in ["月", "火", "水", "木", "金"]:
            for alt_period in range(1, 7):
                alt_slot = TimeSlot(alt_day, alt_period)
                
                # 既に配置があるか確認
                if schedule.get_assignment(alt_slot, class_ref):
                    continue
                
                # この時間に教師が空いているか確認
                teacher_busy = False
                for c in school.get_all_classes():
                    a = schedule.get_assignment(alt_slot, c)
                    if a and a.teacher and a.teacher.name == teacher_name:
                        teacher_busy = True
                        break
                
                if not teacher_busy:
                    # 配置
                    assignment = Assignment(
                        class_ref=class_ref,
                        subject=Subject(subject),
                        teacher=Teacher(teacher_name)
                    )
                    try:
                        schedule.assign(alt_slot, assignment)
                        print(f"    → {alt_day}{alt_period}限に移動")
                        found = True
                        fixed_count += 1
                        break
                    except:
                        continue
            
            if found:
                break
        
        if not found:
            print(f"    → 移動先が見つかりません")

# 保存
if fixed_count > 0:
    schedule_repo.save_schedule(schedule, "output.csv")
    print(f"\n{fixed_count}件の重複を修正しました")
else:
    print("\n修正対象がありませんでした")