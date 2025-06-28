#!/usr/bin/env python3
"""火曜5限の最後の競合を解決"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def final_resolution():
    """火曜5限の最後の競合を解決"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_tuesday_complete.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_final_resolved.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜5限の最後の競合解決 ===\n")
    
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
    
    tuesday_5th = get_cell("火", "5")
    
    print("【残りの競合】")
    print("1. 白石先生: 3年2組(理)と3年3組(理)")  
    print("2. 箱崎先生: 2年1組(英)と2年3組(英)")
    
    print("\n【解決策】")
    
    # 白石先生の競合解決：3年3組の理を移動
    class_row = get_class_row("3年3組")
    if class_row:
        # 金曜5限の数と交換
        target_col = get_cell("金", "5")
        if target_col:
            subj1 = df.iloc[class_row, tuesday_5th]
            subj2 = df.iloc[class_row, target_col]
            df.iloc[class_row, tuesday_5th] = subj2
            df.iloc[class_row, target_col] = subj1
            print(f"✓ 3年3組: 火曜5限(理) ⇔ 金5限(数)")
    
    # 箱崎先生の競合解決：2年3組の英を移動
    class_row = get_class_row("2年3組")
    if class_row:
        # 金曜2限の数と交換
        target_col = get_cell("金", "2")
        if target_col:
            subj1 = df.iloc[class_row, tuesday_5th]
            subj2 = df.iloc[class_row, target_col]
            df.iloc[class_row, tuesday_5th] = subj2
            df.iloc[class_row, target_col] = subj1
            print(f"✓ 2年3組: 火曜5限(英) ⇔ 金2限(数)")
    
    # 最終検証
    print("\n=== 最終検証 ===")
    
    # 教師マッピング
    teacher_map = {}
    mapping_path = Path(__file__).parent / "data" / "config" / "teacher_subject_mapping.csv"
    teacher_df = pd.read_csv(mapping_path)
    
    for _, row in teacher_df.iterrows():
        grade = int(row['学年'])
        class_num = int(row['組'])
        subject = row['教科']
        teacher = row['教員名']
        class_name = f"{grade}年{class_num}組"
        teacher_map[(class_name, subject)] = teacher
    
    # 火曜4限の2年生（確認）
    print("\n【火曜4限の2年生】")
    tuesday_4th = get_cell("火", "4")
    grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
    all_ok = True
    
    for class_name in grade2_classes:
        class_row = get_class_row(class_name)
        if class_row:
            subject = df.iloc[class_row, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "道", "道徳"]:
                print(f"  ❌ {class_name}: {subject}")
                all_ok = False
            else:
                print(f"  ✅ {class_name}: {subject if pd.notna(subject) else '空き'}")
    
    if all_ok:
        print("\n✅ HF会議対応完了！")
    
    # 火曜5限の教師配置
    print("\n【火曜5限の教師配置】")
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
    for teacher, assignments in sorted(teacher_assignments.items()):
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
        else:
            print(f"  ○ {teacher}: {[c for c, s in assignments]}")
    
    if conflicts == 0:
        print("\n🎉 すべての競合が解決されました！")
        print("\n【完了】")
        print("- 火曜4限: HF会議のため2年生の授業なし（道徳のみ）")
        print("- 火曜5限: すべての教師競合が解決")
    else:
        print(f"\n⚠️  まだ{conflicts}件の競合が残っています")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n最終出力: {output_path}")

if __name__ == "__main__":
    final_resolution()