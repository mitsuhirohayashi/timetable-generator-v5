#!/usr/bin/env python3
"""火曜問題の完全解決スクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def comprehensive_fix():
    """火曜問題を完全に解決"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_final_fixed.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_tuesday_resolved.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜問題の完全解決 ===\n")
    
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
    
    def is_fixed_subject(subject):
        """固定科目かチェック"""
        return subject in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト"]
    
    # 教師マッピング
    teacher_map = {
        ("2年1組", "英"): "箱崎",
        ("2年3組", "英"): "箱崎",
        ("3年1組", "社"): "北",
        ("3年2組", "社"): "北",
        ("2年2組", "数"): "井上",
        ("2年3組", "数"): "井上",
        ("2年6組", "自立"): "財津",
        ("3年2組", "保"): "財津",
        ("1年7組", "自立"): "智田",
        ("2年7組", "自立"): "智田",
    }
    
    tuesday_4th = get_cell("火", "4")
    tuesday_5th = get_cell("火", "5")
    
    print("【ステップ1】火曜4限の2年生授業を完全除去")
    
    # 残っている2年生クラスを確認
    grade2_remaining = []
    for i in range(2, len(df)):
        class_name = df.iloc[i, 0]
        if pd.notna(class_name) and "2年" in class_name:
            subject = df.iloc[i, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "欠", "YT", "道", "学", "総", "行"]:
                grade2_remaining.append((class_name, subject))
    
    print(f"残り{len(grade2_remaining)}クラス: {grade2_remaining}")
    
    # 2年2組の国 → 金曜5限の理と交換
    if "2年2組" in [c for c, s in grade2_remaining]:
        class_row = get_class_row("2年2組")
        target_col = get_cell("金", "5")
        if class_row and target_col:
            subj1 = df.iloc[class_row, tuesday_4th]
            subj2 = df.iloc[class_row, target_col]
            if not is_fixed_subject(subj2):
                df.iloc[class_row, tuesday_4th] = subj2
                df.iloc[class_row, target_col] = subj1
                print(f"  ✓ 2年2組: 火曜4限({subj1}) ⇔ 金5限({subj2})")
    
    # 2年5組の社 → 木曜2限の国と交換
    if "2年5組" in [c for c, s in grade2_remaining]:
        class_row = get_class_row("2年5組")
        target_col = get_cell("木", "2")
        if class_row and target_col:
            subj1 = df.iloc[class_row, tuesday_4th]
            subj2 = df.iloc[class_row, target_col]
            if not is_fixed_subject(subj2):
                df.iloc[class_row, tuesday_4th] = subj2
                df.iloc[class_row, target_col] = subj1
                print(f"  ✓ 2年5組: 火曜4限({subj1}) ⇔ 木2限({subj2})")
    
    # 2年6組の自立 → 金曜3限の社と交換
    if "2年6組" in [c for c, s in grade2_remaining]:
        class_row = get_class_row("2年6組")
        target_col = get_cell("金", "3")
        if class_row and target_col:
            subj1 = df.iloc[class_row, tuesday_4th]
            subj2 = df.iloc[class_row, target_col]
            if not is_fixed_subject(subj2):
                df.iloc[class_row, tuesday_4th] = subj2
                df.iloc[class_row, target_col] = subj1
                print(f"  ✓ 2年6組: 火曜4限({subj1}) ⇔ 金3限({subj2})")
    
    # 2年7組の理 → 金曜5限の保と交換
    if "2年7組" in [c for c, s in grade2_remaining]:
        class_row = get_class_row("2年7組")
        target_col = get_cell("金", "5")
        if class_row and target_col:
            subj1 = df.iloc[class_row, tuesday_4th]
            subj2 = df.iloc[class_row, target_col]
            if not is_fixed_subject(subj2):
                df.iloc[class_row, tuesday_4th] = subj2
                df.iloc[class_row, target_col] = subj1
                print(f"  ✓ 2年7組: 火曜4限({subj1}) ⇔ 金5限({subj2})")
    
    print("\n【ステップ2】火曜5限の競合解決")
    
    # 箱崎先生の競合（2年1組と2年3組の英語）
    # 2年3組の英語を木曜3限の英語と交換（同じ科目なので時数に影響なし）
    class_row = get_class_row("2年3組")
    if class_row:
        # 火曜5限を金曜3限の社と交換
        target_col = get_cell("金", "3")
        if target_col:
            subj1 = df.iloc[class_row, tuesday_5th]
            subj2 = df.iloc[class_row, target_col]
            if not is_fixed_subject(subj2):
                df.iloc[class_row, tuesday_5th] = subj2
                df.iloc[class_row, target_col] = subj1
                print(f"  ✓ 2年3組: 火曜5限({subj1}) ⇔ 金3限({subj2})")
    
    # 北先生の競合（3年1組と3年2組の社会）
    # 3年2組の社を金曜4限の理と交換
    class_row = get_class_row("3年2組")
    if class_row:
        target_col = get_cell("金", "4")
        if target_col:
            subj1 = df.iloc[class_row, tuesday_5th]
            subj2 = df.iloc[class_row, target_col]
            if not is_fixed_subject(subj2):
                df.iloc[class_row, tuesday_5th] = subj2
                df.iloc[class_row, target_col] = subj1
                print(f"  ✓ 3年2組: 火曜5限({subj1}) ⇔ 金4限({subj2})")
    
    # 最終検証
    print("\n【最終検証】")
    
    # 火曜4限の2年生
    print("\n火曜4限の2年生クラス:")
    grade2_count = 0
    for i in range(2, len(df)):
        class_name = df.iloc[i, 0]
        if pd.notna(class_name) and "2年" in class_name:
            subject = df.iloc[i, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "欠", "YT", "道", "学", "総", "行"]:
                print(f"  {class_name}: {subject}")
                grade2_count += 1
    
    if grade2_count == 0:
        print("  ✅ HF会議対応完了！")
    
    # 火曜5限の教師配置
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
    print(f"\n最終ファイル: {output_path}")

if __name__ == "__main__":
    comprehensive_fix()