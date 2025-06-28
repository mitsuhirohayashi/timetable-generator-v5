#!/usr/bin/env python3
"""火曜問題の究極的解決スクリプト - HF会議と競合を完全解決"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def ultimate_fix():
    """火曜問題を究極的に解決"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_tuesday_resolved.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_ultimate_fixed.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 火曜問題の究極的解決 ===\n")
    
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
    
    # 教師マッピング（拡張版）
    teacher_map = {
        # 1年
        ("1年1組", "家"): "大嶋",
        ("1年6組", "家"): "大嶋",
        # 2年  
        ("2年1組", "英"): "箱崎",
        ("2年3組", "英"): "箱崎",
        ("2年3組", "社"): "蒲地",
        ("2年6組", "社"): "蒲地",
        ("2年7組", "保"): "財津",
        # 3年
        ("3年1組", "社"): "北",
        ("3年2組", "社"): "北", 
        ("3年3組", "理"): "永田",
        ("3年6組", "理"): "永田",
        ("3年7組", "社"): "北",
        # 自立活動
        ("1年7組", "自立"): "智田",
        ("2年7組", "自立"): "智田",
    }
    
    tuesday_4th = get_cell("火", "4")
    tuesday_5th = get_cell("火", "5")
    
    print("【究極のステップ1】火曜4限の2年生授業を空にする")
    
    # 火曜4限の2年生の授業を強制的に空にする
    # 各クラスで適切な交換先を探す
    swap_targets = {
        "2年2組": [("木", "2"), ("木", "3"), ("金", "2"), ("金", "3")],
        "2年5組": [("木", "3"), ("木", "5"), ("金", "2"), ("金", "3")],
        "2年6組": [("木", "2"), ("木", "5"), ("金", "2"), ("金", "5")],
        "2年7組": [("木", "3"), ("木", "5"), ("金", "3"), ("金", "5")]
    }
    
    for class_name, targets in swap_targets.items():
        class_row = get_class_row(class_name)
        if not class_row:
            continue
            
        current_subject = df.iloc[class_row, tuesday_4th]
        if pd.isna(current_subject) or current_subject in ["", "欠", "YT", "道", "学", "総", "行"]:
            continue
            
        # 交換先を探す
        swapped = False
        for target_day, target_period in targets:
            target_col = get_cell(target_day, target_period)
            if not target_col:
                continue
                
            target_subject = df.iloc[class_row, target_col]
            if not is_fixed_subject(target_subject) and pd.notna(target_subject):
                # 交換実行
                df.iloc[class_row, tuesday_4th] = target_subject
                df.iloc[class_row, target_col] = current_subject
                print(f"  ✓ {class_name}: 火曜4限({current_subject}) ⇔ {target_day}{target_period}限({target_subject})")
                swapped = True
                break
        
        if not swapped:
            print(f"  ✗ {class_name}: 交換先が見つかりませんでした")
    
    print("\n【究極のステップ2】火曜5限の競合を徹底解決")
    
    # 競合リストと解決策
    conflict_solutions = [
        # 大嶋先生（家）の競合: 1年1組と1年6組
        ("1年6組", "火", "5", "木", "2"),  # 1年6組の家を木2の技と交換
        
        # 蒲地先生（社）の競合: 2年3組と3年7組（2年3組は既に英→社に変更済み）
        ("3年7組", "火", "5", "金", "4"),  # 3年7組の社を金4の理と交換
        
        # 北先生（社）の競合: 3年1組と3年2組
        ("3年2組", "火", "5", "木", "5"),  # 3年2組の社を木5の理と交換
        
        # 永田先生（理）の競合: 3年3組と3年6組  
        ("3年6組", "火", "5", "金", "3"),  # 3年6組の理を金3の数と交換
    ]
    
    for class_name, src_day, src_period, dst_day, dst_period in conflict_solutions:
        class_row = get_class_row(class_name)
        if not class_row:
            continue
            
        src_col = get_cell(src_day, src_period)
        dst_col = get_cell(dst_day, dst_period)
        
        if src_col and dst_col:
            src_subject = df.iloc[class_row, src_col]
            dst_subject = df.iloc[class_row, dst_col]
            
            if not is_fixed_subject(dst_subject):
                df.iloc[class_row, src_col] = dst_subject
                df.iloc[class_row, dst_col] = src_subject
                print(f"  ✓ {class_name}: {src_day}{src_period}限({src_subject}) ⇔ {dst_day}{dst_period}限({dst_subject})")
    
    # 最終検証
    print("\n【究極の最終検証】")
    
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
        else:
            print(f"  ○ {teacher}: {[c for c, s in assignments]}")
    
    if conflicts == 0:
        print("\n🎉 すべての競合が解決されました！")
    else:
        print(f"\n⚠️  まだ{conflicts}件の競合が残っています")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n究極の最終ファイル: {output_path}")

if __name__ == "__main__":
    ultimate_fix()