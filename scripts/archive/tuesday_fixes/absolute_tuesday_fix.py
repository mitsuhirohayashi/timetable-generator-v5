#!/usr/bin/env python3
"""火曜問題の絶対的解決 - 2年生の火曜4限を完全に空にする"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def absolute_fix():
    """火曜問題を絶対的に解決"""
    
    # ファイル読み込み  
    input_path = Path(__file__).parent / "data" / "output" / "output_ultimate_fixed.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_absolute_fixed.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜問題の絶対的解決 ===\n")
    
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
        return subject in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト", ""]
    
    def find_empty_slot(class_row):
        """空きスロットを探す"""
        for col in range(1, len(df.columns)):
            day = days[col - 1]
            period = periods[col - 1]
            subject = df.iloc[class_row, col]
            
            # テスト期間、固定時間、6限は避ける
            if (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or \
               str(period) == "6":
                continue
                
            if pd.isna(subject) or subject == "":
                return col
        return None
    
    tuesday_4th = get_cell("火", "4")
    
    print("【絶対ステップ1】火曜4限の2年生授業を問答無用で移動")
    
    # 火曜4限の2年生を確認
    grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
    
    for class_name in grade2_classes:
        class_row = get_class_row(class_name)
        if not class_row:
            continue
            
        current_subject = df.iloc[class_row, tuesday_4th]
        
        # 既に空か固定科目なら何もしない
        if pd.isna(current_subject) or is_fixed_subject(current_subject):
            print(f"  ○ {class_name}: 既に{current_subject if pd.notna(current_subject) else '空き'}")
            continue
        
        # 移動先を探す - まず同じ週の他の場所
        moved = False
        for day in ["木", "金"]:
            for period in ["2", "3", "4", "5"]:
                if day == "火" and period == "4":
                    continue
                    
                target_col = get_cell(day, period)
                if not target_col:
                    continue
                    
                target_subject = df.iloc[class_row, target_col]
                
                # 空きスロットまたは交換可能な科目
                if pd.isna(target_subject) or target_subject == "":
                    # 空きスロットに移動
                    df.iloc[class_row, tuesday_4th] = ""
                    df.iloc[class_row, target_col] = current_subject
                    print(f"  ✓ {class_name}: 火曜4限({current_subject}) → {day}{period}限(空き)")
                    moved = True
                    break
                elif not is_fixed_subject(target_subject):
                    # 交換
                    df.iloc[class_row, tuesday_4th] = target_subject
                    df.iloc[class_row, target_col] = current_subject
                    print(f"  ✓ {class_name}: 火曜4限({current_subject}) ⇔ {day}{period}限({target_subject})")
                    moved = True
                    break
            
            if moved:
                break
        
        if not moved:
            # 最終手段：月曜も含めて探す
            for col in range(1, len(df.columns)):
                if col == tuesday_4th:
                    continue
                    
                day = days[col - 1]
                period = str(periods[col - 1])
                
                # テスト期間と6限は避ける
                if (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or period == "6":
                    continue
                    
                target_subject = df.iloc[class_row, col]
                if not is_fixed_subject(target_subject) and pd.notna(target_subject):
                    df.iloc[class_row, tuesday_4th] = target_subject
                    df.iloc[class_row, col] = current_subject
                    print(f"  ✓ {class_name}: 火曜4限({current_subject}) ⇔ {day}{period}限({target_subject})")
                    moved = True
                    break
            
            if not moved:
                print(f"  ✗ {class_name}: 移動先が見つかりません - 強制的に空にします")
                # 最終手段：空にする
                df.iloc[class_row, tuesday_4th] = ""
    
    print("\n【絶対ステップ2】火曜5限の残り競合を解決")
    
    tuesday_5th = get_cell("火", "5")
    
    # 教師マッピング
    teacher_map = {
        ("3年1組", "社"): "北",
        ("3年7組", "社"): "北",
        ("1年3組", "数"): "井上",
        ("2年2組", "数"): "井上", 
        ("3年6組", "数"): "永田",
    }
    
    # 北先生の競合解決: 3年7組の社を移動
    class_row = get_class_row("3年7組")
    if class_row:
        # 金曜2限の自立と交換
        target_col = get_cell("金", "2")
        if target_col:
            subj1 = df.iloc[class_row, tuesday_5th]
            subj2 = df.iloc[class_row, target_col]
            df.iloc[class_row, tuesday_5th] = subj2
            df.iloc[class_row, target_col] = subj1
            print(f"  ✓ 3年7組: 火曜5限({subj1}) ⇔ 金2限({subj2})")
    
    # 井上先生の競合解決: 2年2組の数を移動  
    class_row = get_class_row("2年2組")
    if class_row:
        # 木曜5限の社と交換
        target_col = get_cell("木", "5")
        if target_col:
            subj1 = df.iloc[class_row, tuesday_5th]
            subj2 = df.iloc[class_row, target_col]
            df.iloc[class_row, tuesday_5th] = subj2
            df.iloc[class_row, target_col] = subj1
            print(f"  ✓ 2年2組: 火曜5限({subj1}) ⇔ 木5限({subj2})")
    
    # 最終検証
    print("\n【絶対的最終検証】")
    
    # 火曜4限の2年生
    print("\n火曜4限の2年生クラス:")
    grade2_count = 0
    for class_name in grade2_classes:
        class_row = get_class_row(class_name)
        if class_row:
            subject = df.iloc[class_row, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "欠", "YT", "道", "学", "総", "行"]:
                print(f"  {class_name}: {subject}")
                grade2_count += 1
    
    if grade2_count == 0:
        print("  ✅ HF会議対応完了！2年生の授業なし")
    else:
        print(f"  ❌ まだ{grade2_count}クラスに授業が残っています")
    
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
    
    if conflicts == 0:
        print("\n🎉 すべての競合が解決されました！")
    else:
        print(f"\n⚠️  まだ{conflicts}件の競合が残っています")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n絶対的最終ファイル: {output_path}")

if __name__ == "__main__":
    absolute_fix()