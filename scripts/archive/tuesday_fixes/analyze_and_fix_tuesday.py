#!/usr/bin/env python3
"""火曜4限と5限の詳細分析と修正"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def analyze_empty_slots(df):
    """全クラスの空きスロットを分析"""
    print("\n=== 空きスロット分析 ===")
    
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    empty_slots_by_class = defaultdict(list)
    
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
            
        for col_idx in range(1, len(df.columns)):
            day = days[col_idx - 1]
            period = str(periods[col_idx - 1])
            
            # テスト期間（月火水の1-3限）は除外
            if (day in ["月", "火", "水"] and period in ["1", "2", "3"]):
                continue
                
            value = df.iloc[row_idx, col_idx]
            if pd.isna(value) or value == "":
                empty_slots_by_class[class_name].append((day, period))
    
    # 2年生と競合クラスの空きスロットを表示
    target_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組", "3年2組"]
    
    for class_name in target_classes:
        slots = empty_slots_by_class.get(class_name, [])
        print(f"\n{class_name}の空きスロット: {len(slots)}個")
        if slots:
            for day, period in slots[:5]:  # 最初の5個を表示
                print(f"  - {day}{period}限")

def find_swappable_slots(df, class_name, target_day, target_period):
    """指定クラスの授業と入れ替え可能なスロットを探す"""
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # クラスの行を見つける
    class_row = None
    for idx in range(2, len(df)):
        if df.iloc[idx, 0] == class_name:
            class_row = idx
            break
    
    if class_row is None:
        return []
    
    # 現在の授業を取得
    target_col = None
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == target_day and str(periods[col_idx - 1]) == str(target_period):
            target_col = col_idx
            break
    
    if target_col is None:
        return []
    
    target_subject = df.iloc[class_row, target_col]
    if pd.isna(target_subject) or target_subject == "":
        return []
    
    swappable = []
    
    # 他の時間の授業を確認
    for col_idx in range(1, len(df.columns)):
        day = days[col_idx - 1]
        period = str(periods[col_idx - 1])
        
        # 同じ時間はスキップ
        if day == target_day and period == str(target_period):
            continue
        
        # テスト期間はスキップ
        if (day in ["月", "火", "水"] and period in ["1", "2", "3"]):
            continue
        
        # 6限と固定科目はスキップ
        if period == "6":
            continue
            
        subject = df.iloc[class_row, col_idx]
        if pd.notna(subject) and subject != "" and subject not in ["欠", "YT", "道", "学", "総", "行", "学総"]:
            swappable.append({
                'day': day,
                'period': period,
                'subject': subject,
                'col_idx': col_idx
            })
    
    return swappable

def swap_assignments(df, class_name, day1, period1, day2, period2):
    """2つの時間の授業を入れ替え"""
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # インデックスを見つける
    col1 = None
    col2 = None
    class_row = None
    
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == day1 and str(periods[col_idx - 1]) == str(period1):
            col1 = col_idx
        if days[col_idx - 1] == day2 and str(periods[col_idx - 1]) == str(period2):
            col2 = col_idx
    
    for idx in range(2, len(df)):
        if df.iloc[idx, 0] == class_name:
            class_row = idx
            break
    
    if col1 and col2 and class_row:
        # 授業を入れ替え
        subject1 = df.iloc[class_row, col1]
        subject2 = df.iloc[class_row, col2]
        df.iloc[class_row, col1] = subject2
        df.iloc[class_row, col2] = subject1
        return True, subject1, subject2
    
    return False, None, None

def check_teacher_availability(df, teacher_mapping, day, period, exclude_classes=None):
    """指定時間の教師の可用性をチェック"""
    exclude_classes = exclude_classes or []
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # その時間のカラムインデックスを見つける
    target_col = None
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == day and str(periods[col_idx - 1]) == str(period):
            target_col = col_idx
            break
    
    if target_col is None:
        return {}
    
    teacher_assignments = defaultdict(list)
    
    # 全クラスのその時間の授業を確認
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "" or class_name in exclude_classes:
            continue
            
        subject = df.iloc[row_idx, target_col]
        if pd.notna(subject) and subject != "":
            # 教師を特定（簡易版）
            teacher = teacher_mapping.get((class_name, subject), f"{subject}担当")
            teacher_assignments[teacher].append(class_name)
    
    return teacher_assignments

def main():
    """メイン処理"""
    input_path = Path(__file__).parent / "data" / "output" / "output.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_fixed.csv"
    
    df = pd.read_csv(input_path, header=None)
    
    # 教師マッピング（簡易版）
    teacher_mapping = {
        ("2年1組", "社"): "蒲地",
        ("2年2組", "社"): "蒲地",
        ("2年3組", "英"): "箱崎",
        ("2年2組", "数"): "井上",
        ("2年3組", "数"): "井上",
        ("3年2組", "保"): "財津",
        # ... 他の教師マッピング
    }
    
    print("=== 火曜4限と5限の問題分析と修正 ===")
    
    # 空きスロットを分析
    analyze_empty_slots(df)
    
    print("\n\n=== 修正戦略 ===")
    
    # 1. 火曜4限のHF会議対応
    print("\n【戦略1】火曜4限の2年生授業を入れ替え")
    
    fixes = []
    grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
    
    for class_name in grade2_classes:
        swappable = find_swappable_slots(df, class_name, "火", "4")
        
        if swappable:
            # 最適な入れ替え先を探す
            best_swap = None
            
            for swap in swappable:
                # その時間に他の2年生クラスで同じ教科がないか確認
                teacher_check = check_teacher_availability(df, teacher_mapping, 
                                                         swap['day'], swap['period'], 
                                                         [class_name])
                
                # 教師の競合がない場合
                conflict = False
                for teacher, classes in teacher_check.items():
                    if len(classes) > 1 and not all("5組" in c for c in classes):
                        conflict = True
                        break
                
                if not conflict:
                    best_swap = swap
                    break
            
            if best_swap:
                success, subj1, subj2 = swap_assignments(df, class_name, "火", "4", 
                                                        best_swap['day'], best_swap['period'])
                if success:
                    fixes.append(f"{class_name}: 火曜4限の{subj1}と{best_swap['day']}{best_swap['period']}限の{subj2}を入れ替え")
                    print(f"  ✓ {class_name}: 火曜4限({subj1}) ⇔ {best_swap['day']}{best_swap['period']}限({subj2})")
    
    # 2. 火曜5限の競合修正
    print("\n【戦略2】火曜5限の競合修正")
    
    # 井上先生の競合（2年3組の数学）
    print("\n- 井上先生の競合修正（2年3組の数学を移動）")
    swappable = find_swappable_slots(df, "2年3組", "火", "5")
    
    best_swap = None
    for swap in swappable:
        # 井上先生が他のクラスを教えていない時間を探す
        if swap['day'] == "火" and swap['period'] == "5":
            continue
            
        # 簡易チェック
        best_swap = swap
        break
    
    if best_swap:
        success, subj1, subj2 = swap_assignments(df, "2年3組", "火", "5", 
                                                best_swap['day'], best_swap['period'])
        if success:
            fixes.append(f"2年3組: 火曜5限の{subj1}と{best_swap['day']}{best_swap['period']}限の{subj2}を入れ替え")
            print(f"  ✓ 2年3組: 火曜5限({subj1}) ⇔ {best_swap['day']}{best_swap['period']}限({subj2})")
    
    # 財津先生の競合（3年2組の保健体育）
    print("\n- 財津先生の競合修正（3年2組の保健体育を移動）")
    swappable = find_swappable_slots(df, "3年2組", "火", "5")
    
    best_swap = None
    for swap in swappable[:3]:  # 最初の3つを試す
        best_swap = swap
        break
    
    if best_swap:
        success, subj1, subj2 = swap_assignments(df, "3年2組", "火", "5", 
                                                best_swap['day'], best_swap['period'])
        if success:
            fixes.append(f"3年2組: 火曜5限の{subj1}と{best_swap['day']}{best_swap['period']}限の{subj2}を入れ替え")
            print(f"  ✓ 3年2組: 火曜5限({subj1}) ⇔ {best_swap['day']}{best_swap['period']}限({subj2})")
    
    # 結果を保存
    df.to_csv(output_path, index=False, header=False)
    
    print(f"\n\n=== 修正結果 ===")
    print(f"修正件数: {len(fixes)}件")
    for fix in fixes:
        print(f"  - {fix}")
    
    print(f"\n修正後のファイル: {output_path}")
    
    # 修正後の確認
    if len(fixes) > 0:
        print("\n修正されたファイルで再度違反をチェックしてください：")
        print("  python3 check_violations.py")

if __name__ == "__main__":
    main()