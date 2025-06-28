#!/usr/bin/env python3
"""体育館使用違反を修正するスクリプト（簡易版）

体育館は1つしかないため、同じ時間に複数のクラスが保健体育を実施することはできません。
ただし、5組（1-5, 2-5, 3-5）の合同体育は例外として許可されます。
"""

import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import PathConfig


def find_gym_usage_violations(schedule) -> list:
    """体育館使用違反を検出"""
    violations = []
    
    # 5組の合同体育クラス
    grade5_classes = {
        ClassReference(1, 5),
        ClassReference(2, 5),
        ClassReference(3, 5)
    }
    
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            
            # この時間に保健体育を実施しているクラスを収集
            pe_classes = []
            pe_assignments = []
            
            for time_assignment, assignment in schedule.get_all_assignments():
                if time_assignment == time_slot and assignment.subject.name == "保":
                    pe_classes.append(assignment.class_ref)
                    pe_assignments.append(assignment)
            
            # 2クラス以上が同時に保健体育を実施している場合
            if len(pe_classes) > 1:
                # 全て5組の合同体育かチェック
                all_grade5 = all(c in grade5_classes for c in pe_classes)
                
                if not all_grade5:
                    violations.append({
                        'time_slot': time_slot,
                        'classes': pe_classes,
                        'assignments': pe_assignments
                    })
    
    return violations


def find_alternative_slot(schedule, class_ref: ClassReference, avoid_slot: TimeSlot) -> TimeSlot:
    """代替スロットを探す"""
    for day in ["月", "火", "水", "木", "金"]:
        for period in range(1, 7):
            if day == "月" and period == 6:  # 固定制約
                continue
            
            time_slot = TimeSlot(day, period)
            
            # 元のスロットと同じ場合はスキップ
            if time_slot == avoid_slot:
                continue
            
            # 既に授業がある場合はスキップ
            if schedule.get_assignment(time_slot, class_ref):
                continue
            
            # ロックされている場合はスキップ
            if schedule.is_locked(time_slot, class_ref):
                continue
            
            # この時間に他のクラスが保健体育を実施していないかチェック
            pe_count = 0
            for _, assignment in schedule.get_all_assignments():
                if assignment.time_slot == time_slot and assignment.subject.name == "保":
                    pe_count += 1
            
            if pe_count > 0:
                continue
            
            # 日内重複チェック
            same_subject_count = 0
            for p in range(1, 7):
                check_slot = TimeSlot(day, p)
                assignment = schedule.get_assignment(check_slot, class_ref)
                if assignment and assignment.subject.name == "保":
                    same_subject_count += 1
            
            if same_subject_count > 0:
                continue
            
            return time_slot
    
    return None


def main():
    """メイン処理"""
    # パス設定
    path_config = PathConfig()
    
    # リポジトリ初期化
    repository = CSVScheduleRepository()
    
    # スケジュール読み込み
    print("スケジュールを読み込んでいます...")
    import os
    os.chdir(project_root)
    schedule = repository.load("data/output/output.csv")
    
    # 体育館使用違反を検出
    violations = find_gym_usage_violations(schedule)
    
    print(f"\n体育館使用違反を{len(violations)}件検出しました")
    
    if len(violations) == 0:
        print("修正が必要な体育館使用違反はありませんでした")
        return
    
    fixed_count = 0
    
    for violation in violations:
        time_slot = violation['time_slot']
        classes = violation['classes']
        
        print(f"\n{time_slot}: {len(classes)}クラスが同時に保健体育を実施")
        for cls in classes:
            print(f"  - {cls}")
        
        # 最初のクラス以外を移動
        for i in range(1, len(classes)):
            class_ref = classes[i]
            assignment = schedule.get_assignment(time_slot, class_ref)
            
            if not assignment:
                continue
            
            # 代替スロットを探す
            new_slot = find_alternative_slot(schedule, class_ref, time_slot)
            
            if new_slot:
                # 元のスロットの授業を削除
                schedule.remove_assignment(time_slot, class_ref)
                
                # 新しいスロットに配置
                try:
                    schedule.assign(new_slot, assignment)
                    print(f"  → {class_ref}の保健体育を{time_slot}から{new_slot}に移動")
                    fixed_count += 1
                    
                except ValueError as e:
                    print(f"  ! {class_ref}の移動に失敗: {e}")
                    # 元に戻す
                    schedule.assign(time_slot, assignment)
            else:
                print(f"  ! {class_ref}の保健体育の代替スロットが見つかりません")
    
    if fixed_count > 0:
        print(f"\n合計{fixed_count}件の体育館使用違反を修正しました")
        
        # スケジュールを保存
        print("\n修正したスケジュールを保存しています...")
        repository.save_schedule(schedule)
        print("保存完了: data/output/output.csv")
    else:
        print("\n修正できませんでした")


if __name__ == "__main__":
    main()