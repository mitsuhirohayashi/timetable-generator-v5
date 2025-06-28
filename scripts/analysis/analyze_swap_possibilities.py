#!/usr/bin/env python3
"""入れ替え可能性の詳細分析スクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def analyze_swap_possibilities():
    """入れ替え可能性を詳細分析"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output.csv"
    df = pd.read_csv(input_path, header=None)
    
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜4限と5限の入れ替え可能性分析 ===\n")
    
    # 火曜4限の2年生クラスの分析
    print("【火曜4限の2年生クラス】")
    grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
    
    for class_name in grade2_classes:
        print(f"\n{class_name}の分析:")
        
        # クラスの行を見つける
        class_row = None
        for idx in range(2, len(df)):
            if df.iloc[idx, 0] == class_name:
                class_row = idx
                break
        
        if class_row is None:
            continue
        
        # 火曜4限の授業
        tuesday_4th_col = None
        for col_idx in range(1, len(df.columns)):
            if days[col_idx - 1] == "火" and str(periods[col_idx - 1]) == "4":
                tuesday_4th_col = col_idx
                break
        
        tuesday_4th_subject = df.iloc[class_row, tuesday_4th_col]
        print(f"  火曜4限: {tuesday_4th_subject}")
        
        # 入れ替え可能な時間を探す
        swappable_slots = []
        
        for col_idx in range(1, len(df.columns)):
            day = days[col_idx - 1]
            period = str(periods[col_idx - 1])
            
            # 火曜4限自身、テスト期間、6限は除外
            if (day == "火" and period == "4") or \
               (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or \
               period == "6":
                continue
            
            subject = df.iloc[class_row, col_idx]
            
            # 固定科目でない通常授業
            if pd.notna(subject) and subject != "" and \
               subject not in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]:
                swappable_slots.append({
                    'day': day,
                    'period': period,
                    'subject': subject
                })
        
        print(f"  入れ替え可能なスロット: {len(swappable_slots)}個")
        for slot in swappable_slots[:5]:  # 最初の5個を表示
            print(f"    - {slot['day']}{slot['period']}限: {slot['subject']}")
    
    # 火曜5限の競合分析
    print("\n\n【火曜5限の競合詳細】")
    
    # 教師マッピングを簡易的に作成
    teacher_info = {
        ("2年1組", "英"): "箱崎",
        ("2年2組", "数"): "井上",
        ("2年3組", "数"): "井上",
        ("1年7組", "自立"): "智田",
        ("2年7組", "自立"): "智田",
        ("2年6組", "自立"): "財津",
        ("3年2組", "保"): "財津",
    }
    
    tuesday_5th_col = None
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == "火" and str(periods[col_idx - 1]) == "5":
            tuesday_5th_col = col_idx
            break
    
    # 競合教師の授業を確認
    conflicts = defaultdict(list)
    
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
        
        subject = df.iloc[row_idx, tuesday_5th_col]
        if pd.notna(subject) and subject != "":
            teacher = teacher_info.get((class_name, subject), f"{subject}担当")
            conflicts[teacher].append((class_name, subject))
    
    # 競合を表示
    for teacher, assignments in conflicts.items():
        if len(assignments) > 1:
            # 5組と自立活動は除外
            grade5 = all("5組" in c for c, s in assignments)
            jiritsu = all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments)
            
            if not grade5 and not jiritsu:
                print(f"\n{teacher}先生の競合:")
                for class_name, subject in assignments:
                    print(f"  - {class_name}: {subject}")
    
    # 解決提案
    print("\n\n=== 解決戦略の提案 ===")
    
    print("\n【戦略1】火曜4限のHF会議対応")
    print("- 2年生の火曜4限授業を以下の優先順位で移動:")
    print("  1. 木曜4限や金曜4限の空きスロット")
    print("  2. 木曜5限や金曜5限（6限以外）")
    print("  3. 他クラスとの授業交換")
    
    print("\n【戦略2】火曜5限の競合解決")
    print("- 井上先生: 2年2組か2年3組の数学を別時間へ")
    print("- 財津先生: 3年2組の保健体育を別時間へ")
    print("- 智田先生: 自立活動の同時実施として処理（移動不要）")
    
    print("\n【戦略3】複雑な連鎖入れ替え")
    print("- 例: A→B→C→Aのような3つ以上の授業の循環的入れ替え")
    print("- 制約: 教師競合、日内重複、体育館使用などを考慮")

if __name__ == "__main__":
    analyze_swap_possibilities()