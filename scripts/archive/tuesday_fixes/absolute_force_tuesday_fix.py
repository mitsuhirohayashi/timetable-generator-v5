#!/usr/bin/env python3
"""火曜4限の2年生を絶対的に空にして、火曜5限の競合も解決"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def absolute_force_fix():
    """火曜問題を絶対的に解決"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_forced_empty.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_tuesday_complete.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜問題の絶対的解決（最終版） ===\n")
    
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
    
    tuesday_4th = get_cell("火", "4")
    
    print("【最終ステップ1】火曜4限の2年生を確実に空にする")
    
    # 2年生クラスの火曜4限を直接チェック
    grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
    
    for class_name in grade2_classes:
        class_row = get_class_row(class_name)
        if not class_row:
            continue
            
        current_subject = df.iloc[class_row, tuesday_4th]
        
        # 既に空か道徳なら何もしない
        if pd.isna(current_subject) or current_subject in ["", "道", "道徳"]:
            print(f"  ○ {class_name}: 既に{current_subject if pd.notna(current_subject) else '空き'}")
            continue
        
        # 道徳の時間を探す（通常は木曜4限）
        moral_col = None
        for col in range(1, len(df.columns)):
            if df.iloc[class_row, col] in ["道", "道徳"]:
                moral_col = col
                break
        
        if moral_col:
            # 道徳と交換
            moral_subject = df.iloc[class_row, moral_col]
            df.iloc[class_row, tuesday_4th] = moral_subject
            df.iloc[class_row, moral_col] = current_subject
            print(f"  ✓ {class_name}: 火曜4限({current_subject}) ⇔ {days[moral_col-1]}{periods[moral_col-1]}限(道徳)")
        else:
            # 道徳がない場合は空にする
            print(f"  ✓ {class_name}: 火曜4限({current_subject}) → 削除（空きに）")
            df.iloc[class_row, tuesday_4th] = ""
    
    print("\n【最終ステップ2】火曜5限の競合を解決")
    
    tuesday_5th = get_cell("火", "5")
    
    # 教師マッピング（詳細版）
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
    
    # 現在の火曜5限の配置を確認
    print("\n現在の火曜5限:")
    teacher_assignments = defaultdict(list)
    
    for i in range(2, len(df)):
        class_name = df.iloc[i, 0]
        if pd.isna(class_name):
            continue
        subject = df.iloc[i, tuesday_5th]
        if pd.notna(subject) and subject != "":
            teacher = teacher_map.get((class_name, subject), f"{subject}担当")
            teacher_assignments[teacher].append((class_name, subject))
            print(f"  {class_name}: {subject} ({teacher})")
    
    # 競合を解決
    print("\n競合解決:")
    
    # 具体的な競合解決
    fixes = [
        # 永田先生の理科競合（3年2組と3年3組）
        ("3年3組", "火", "5", "金", "4"),  # 3年3組の理を金4の数と交換
        
        # 蒲地先生の社会競合（2年2組と2年3組）  
        ("2年3組", "火", "5", "金", "3"),  # 2年3組の社を金3の社と交換（同じ科目）
        
        # 箱崎先生の英語競合（1年2組と2年1組）
        ("1年2組", "火", "5", "金", "4"),  # 1年2組の英を金4の数と交換
    ]
    
    for class_name, src_day, src_period, dst_day, dst_period in fixes:
        class_row = get_class_row(class_name)
        if not class_row:
            continue
            
        src_col = get_cell(src_day, src_period)
        dst_col = get_cell(dst_day, dst_period)
        
        if src_col and dst_col:
            src_subject = df.iloc[class_row, src_col]
            dst_subject = df.iloc[class_row, dst_col]
            
            # 固定科目でなければ交換
            if dst_subject not in ["欠", "YT", "道", "道徳", "学", "総", "行"]:
                df.iloc[class_row, src_col] = dst_subject
                df.iloc[class_row, dst_col] = src_subject
                print(f"  ✓ {class_name}: {src_day}{src_period}限({src_subject}) ⇔ {dst_day}{dst_period}限({dst_subject})")
    
    # 最終検証
    print("\n\n=== 最終検証 ===")
    
    # 火曜4限の2年生
    print("\n【火曜4限の2年生】")
    grade2_count = 0
    for class_name in grade2_classes:
        class_row = get_class_row(class_name)
        if class_row:
            subject = df.iloc[class_row, tuesday_4th]
            if pd.notna(subject) and subject not in ["", "欠", "YT", "道", "道徳", "学", "総", "行"]:
                print(f"  {class_name}: {subject}")
                grade2_count += 1
            else:
                print(f"  {class_name}: {subject if pd.notna(subject) else '空き'}")
    
    if grade2_count == 0:
        print("\n✅ HF会議対応完了！すべての2年生の火曜4限が空または道徳になりました")
    
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
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n完成ファイル: {output_path}")

if __name__ == "__main__":
    absolute_force_fix()