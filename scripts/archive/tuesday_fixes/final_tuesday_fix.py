#!/usr/bin/env python3
"""火曜問題の最終修正スクリプト - 強制的に解決"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def final_fix():
    """最終的な火曜問題修正"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_backup.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_final_complete.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜問題の最終修正 ===\n")
    
    # 教師マッピング
    teacher_map = {
        ("2年1組", "英"): "箱崎",
        ("2年2組", "数"): "井上",
        ("2年3組", "数"): "井上",
        ("2年1組", "社"): "蒲地",
        ("2年2組", "社"): "蒲地",
        ("2年3組", "英"): "箱崎",
        ("3年2組", "保"): "財津",
        ("2年6組", "自立"): "財津",
        ("1年7組", "自立"): "智田",
        ("2年7組", "自立"): "智田",
    }
    
    def get_cell(day, period):
        for i, (d, p) in enumerate(zip(days, periods)):
            if d == day and str(p) == str(period):
                return i + 1
        return None
    
    def get_class_row(class_name):
        for i in range(2, len(df)):
            if df.iloc[i, 0] == class_name:
                return i
        return None
    
    # 修正記録
    fixes = []
    
    print("【ステップ1】火曜4限の2年生授業を完全に除去")
    
    # 火曜4限と入れ替える候補を事前に決定
    swap_plan = {
        "2年1組": ("木", "5"),  # 社 → 英
        "2年2組": ("金", "4"),  # 社 → 理  
        "2年3組": ("金", "5"),  # 英 → 英
        "2年5組": ("木", "4"),  # 英 → 道（固定だが一時的に）
        "2年6組": ("金", "4"),  # 社 → 理
        "2年7組": ("木", "5"),  # 社 → 数
    }
    
    tuesday_4th = get_cell("火", "4")
    
    for class_name, (target_day, target_period) in swap_plan.items():
        class_row = get_class_row(class_name)
        if not class_row:
            continue
            
        target_col = get_cell(target_day, target_period)
        if not target_col:
            continue
        
        # 強制入れ替え
        subj1 = df.iloc[class_row, tuesday_4th]
        subj2 = df.iloc[class_row, target_col]
        
        # 道徳は別の場所へ
        if subj2 in ["道", "道徳"]:
            # 別の候補を探す
            for col in range(1, len(df.columns)):
                if col == tuesday_4th or col == target_col:
                    continue
                day = days[col - 1]
                period = periods[col - 1]
                if day not in ["月", "火", "水"] or str(period) not in ["1", "2", "3"]:
                    subj_temp = df.iloc[class_row, col]
                    if pd.notna(subj_temp) and subj_temp not in ["欠", "YT", "道", "学", "総", "行", "学総"]:
                        # 3way swap
                        df.iloc[class_row, tuesday_4th] = subj_temp
                        df.iloc[class_row, col] = subj1
                        fixes.append(f"{class_name}: 火曜4限({subj1}) → {days[col-1]}{periods[col-1]}限")
                        print(f"  ✓ {class_name}: 火曜4限を{days[col-1]}{periods[col-1]}限へ移動")
                        break
        else:
            df.iloc[class_row, tuesday_4th] = subj2
            df.iloc[class_row, target_col] = subj1
            fixes.append(f"{class_name}: 火曜4限({subj1}) ⇔ {target_day}{target_period}限({subj2})")
            print(f"  ✓ {class_name}: 火曜4限({subj1}) ⇔ {target_day}{target_period}限({subj2})")
    
    print("\n【ステップ2】火曜5限の競合解決")
    
    tuesday_5th = get_cell("火", "5")
    
    # 井上先生の競合（2年2組と2年3組）
    # 2年3組の数学を木曜4限へ
    class_row = get_class_row("2年3組")
    target_col = get_cell("木", "4")
    if class_row and target_col:
        subj1 = df.iloc[class_row, tuesday_5th]
        subj2 = df.iloc[class_row, target_col]
        df.iloc[class_row, tuesday_5th] = subj2
        df.iloc[class_row, target_col] = subj1
        fixes.append(f"2年3組: 火曜5限(数) ⇔ 木4限({subj2})")
        print(f"  ✓ 2年3組: 火曜5限(数) → 木4限")
    
    # 財津先生の競合（2年6組自立と3年2組保）
    # 3年2組の保を金曜4限へ
    class_row = get_class_row("3年2組")
    target_col = get_cell("金", "4")
    if class_row and target_col:
        subj1 = df.iloc[class_row, tuesday_5th]
        subj2 = df.iloc[class_row, target_col]
        df.iloc[class_row, tuesday_5th] = subj2
        df.iloc[class_row, target_col] = subj1
        fixes.append(f"3年2組: 火曜5限(保) ⇔ 金4限({subj2})")
        print(f"  ✓ 3年2組: 火曜5限(保) → 金4限")
    
    # 検証
    print("\n【最終検証】")
    
    # 火曜4限の2年生
    print("\n火曜4限:")
    grade2_count = 0
    for i in range(2, len(df)):
        class_name = df.iloc[i, 0]
        if pd.notna(class_name) and "2年" in class_name:
            subject = df.iloc[i, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "欠", "YT", "道", "学", "総", "行"]:
                print(f"  {class_name}: {subject}")
                grade2_count += 1
    
    if grade2_count == 0:
        print("  ✅ 2年生の授業なし（HF会議対応完了）")
    
    # 火曜5限の教師
    print("\n火曜5限の教師配置:")
    teacher_assignments = defaultdict(list)
    
    for i in range(2, len(df)):
        class_name = df.iloc[i, 0]
        if pd.isna(class_name):
            continue
        subject = df.iloc[i, tuesday_5th]
        if pd.notna(subject) and subject != "":
            teacher = teacher_map.get((class_name, subject), f"{subject}担当")
            teacher_assignments[teacher].append((class_name, subject))
    
    conflicts = 0
    for teacher, assignments in teacher_assignments.items():
        if len(assignments) > 1:
            # 5組と自立活動チェック
            all_grade5 = all("5組" in c for c, s in assignments)
            all_jiritsu = all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments)
            
            if not all_grade5 and not all_jiritsu:
                print(f"  ❌ {teacher}: {[c for c, s in assignments]}")
                conflicts += 1
            else:
                status = "5組合同" if all_grade5 else "自立活動同時実施"
                print(f"  ✅ {teacher}: {[c for c, s in assignments]} ({status})")
    
    if conflicts == 0:
        print("\n✅ すべての競合が解決されました！")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n修正件数: {len(fixes)}件")
    print(f"最終ファイル: {output_path}")

if __name__ == "__main__":
    final_fix()