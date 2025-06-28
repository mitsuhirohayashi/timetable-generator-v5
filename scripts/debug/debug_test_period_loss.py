#!/usr/bin/env python3
"""テスト期間のデータ消失を調査するデバッグスクリプト"""

import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.value_objects.time_slot import TimeSlot
import pandas as pd

def check_test_periods_simple():
    """テスト期間のデータを確認（pandas使用）"""
    
    # テスト期間の定義（Follow-up.csvから）
    test_periods = [
        ("月", 1), ("月", 2), ("月", 3),  # 月曜1-3校時
        ("火", 1), ("火", 2), ("火", 3),  # 火曜1-3校時
        ("水", 1), ("水", 2)               # 水曜1-2校時
    ]
    
    print("=== テスト期間データ確認 ===\n")
    
    # input.csvを直接読み込み
    print("1. input.csv の内容:")
    print("-" * 50)
    
    input_df = pd.read_csv("data/input/input.csv")
    
    # ヘッダーから時間枠を抽出
    days = input_df.iloc[0, 1:].values
    periods = input_df.iloc[1, 1:].values
    
    for day, period in test_periods:
        time_slot = TimeSlot(day, period)
        print(f"\n{day}曜{period}限:")
        
        # 1年1組から3年7組まで確認
        for grade in [1, 2, 3]:
            for class_num in [1, 2, 3, 5, 6, 7]:
                from src.domain.value_objects.time_slot import ClassReference
                class_ref = ClassReference(grade, class_num)
                
                assignment = input_schedule.get_assignment(time_slot, class_ref)
                is_locked = input_schedule.is_locked(time_slot, class_ref)
                
                if assignment:
                    lock_status = "🔒" if is_locked else "🔓"
                    print(f"  {class_ref.full_name}: {assignment.subject.name} {lock_status}")
    
    # output.csvを読み込み
    print("\n\n2. output.csv の内容:")
    print("-" * 50)
    
    try:
        output_schedule = repo.load("output/output.csv")
        
        for day, period in test_periods:
            time_slot = TimeSlot(day, period)
            print(f"\n{day}曜{period}限:")
            
            # 1年1組から3年7組まで確認
            for grade in [1, 2, 3]:
                for class_num in [1, 2, 3, 5, 6, 7]:
                    class_ref = ClassReference(grade, class_num)
                    
                    assignment = output_schedule.get_assignment(time_slot, class_ref)
                    is_locked = output_schedule.is_locked(time_slot, class_ref)
                    
                    if assignment:
                        lock_status = "🔒" if is_locked else "🔓"
                        print(f"  {class_ref.full_name}: {assignment.subject.name} {lock_status}")
                    else:
                        print(f"  {class_ref.full_name}: [空き]")
    except Exception as e:
        print(f"output.csv の読み込みエラー: {e}")
    
    # 差分を表示
    print("\n\n3. 差分分析:")
    print("-" * 50)
    
    missing_count = 0
    for day, period in test_periods:
        time_slot = TimeSlot(day, period)
        
        for grade in [1, 2, 3]:
            for class_num in [1, 2, 3, 5, 6, 7]:
                class_ref = ClassReference(grade, class_num)
                
                input_assignment = input_schedule.get_assignment(time_slot, class_ref)
                output_assignment = output_schedule.get_assignment(time_slot, class_ref) if 'output_schedule' in locals() else None
                
                if input_assignment and not output_assignment:
                    missing_count += 1
                    print(f"❌ {day}曜{period}限 {class_ref.full_name}: {input_assignment.subject.name} が失われました")
    
    print(f"\n合計 {missing_count} 個のテスト期間データが失われています")

if __name__ == "__main__":
    check_test_periods()