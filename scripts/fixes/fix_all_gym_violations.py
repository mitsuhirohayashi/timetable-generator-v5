#!/usr/bin/env python3
"""体育館使用違反を包括的に修正するスクリプト"""

import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import csv
from collections import defaultdict
from src.domain.value_objects.time_slot import TimeSlot, ClassReference


def analyze_gym_usage():
    """体育館使用状況を分析"""
    # CSVファイルを読み込む
    csv_path = project_root / "data" / "output" / "output.csv"
    
    # 時間ごとの保健体育実施クラスを収集
    gym_usage = defaultdict(list)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行
        time_slots_row = next(reader)  # 時間スロット行
        
        # 各クラスの行を処理
        for row in reader:
            if not row or not row[0].strip():
                continue
            
            class_name = row[0]
            
            # 各時間スロットをチェック
            for i in range(2, len(row)):
                if i >= len(row):
                    break
                
                subject = row[i].strip()
                if subject == "保":
                    # 時間スロットを計算
                    day_index = (i - 2) // 6
                    period = ((i - 2) % 6) + 1
                    days = ["月", "火", "水", "木", "金"]
                    
                    if day_index < len(days):
                        time_slot = f"{days[day_index]}{period}限"
                        gym_usage[time_slot].append(class_name)
    
    return gym_usage


def find_violations(gym_usage):
    """体育館使用違反を検出"""
    violations = []
    grade5_classes = {"1年5組", "2年5組", "3年5組"}
    
    for time_slot, classes in gym_usage.items():
        if len(classes) > 1:
            # 5組の合同体育かチェック
            all_grade5 = all(cls in grade5_classes for cls in classes)
            
            if not all_grade5:
                violations.append({
                    'time_slot': time_slot,
                    'classes': classes,
                    'count': len(classes)
                })
    
    return violations


def suggest_fixes(violations, gym_usage):
    """修正案を提案"""
    print("\n=== 体育館使用違反の修正案 ===\n")
    
    # 使用率の低い時間スロットを見つける
    all_slots = []
    days = ["月", "火", "水", "木", "金"]
    for day in days:
        for period in range(1, 7):
            if day == "月" and period == 6:  # 固定制約
                continue
            all_slots.append(f"{day}{period}限")
    
    # 各時間スロットの使用状況
    usage_count = {slot: len(gym_usage.get(slot, [])) for slot in all_slots}
    
    # 違反ごとに修正案を提示
    for violation in violations:
        time_slot = violation['time_slot']
        classes = violation['classes']
        
        print(f"{time_slot}: {len(classes)}クラスが同時に体育館使用")
        for cls in classes:
            print(f"  - {cls}")
        
        # 空いている時間スロットを提案
        print("\n  推奨移動先:")
        empty_slots = [slot for slot, count in usage_count.items() if count == 0]
        low_usage_slots = [slot for slot, count in usage_count.items() if count == 1 and slot != time_slot]
        
        if empty_slots:
            print(f"    空き時間: {', '.join(empty_slots[:5])}")
        if low_usage_slots:
            print(f"    使用率低: {', '.join(low_usage_slots[:5])}")
        
        print()


def generate_fix_commands(violations):
    """修正のための手動編集ガイドを生成"""
    print("\n=== 手動修正ガイド ===\n")
    
    fix_count = 0
    for violation in violations:
        time_slot = violation['time_slot']
        classes = violation['classes']
        
        # 最初のクラス以外を移動対象とする
        for i in range(1, len(classes)):
            fix_count += 1
            print(f"{fix_count}. {classes[i]}の{time_slot}の保健体育を別の時間に移動")
    
    print(f"\n合計{fix_count}件の移動が必要です。")


def main():
    """メイン処理"""
    print("体育館使用状況を分析中...\n")
    
    # 体育館使用状況を分析
    gym_usage = analyze_gym_usage()
    
    # 時間ごとの使用状況を表示
    print("=== 時間ごとの体育館使用状況 ===")
    days = ["月", "火", "水", "木", "金"]
    for day in days:
        print(f"\n{day}曜日:")
        for period in range(1, 7):
            time_slot = f"{day}{period}限"
            classes = gym_usage.get(time_slot, [])
            if classes:
                print(f"  {period}限: {len(classes)}クラス ({', '.join(classes)})")
    
    # 違反を検出
    violations = find_violations(gym_usage)
    
    if violations:
        print(f"\n\n体育館使用違反: {len(violations)}件検出")
        
        # 修正案を提案
        suggest_fixes(violations, gym_usage)
        
        # 手動修正ガイドを生成
        generate_fix_commands(violations)
    else:
        print("\n\n体育館使用違反はありません。")


if __name__ == "__main__":
    main()