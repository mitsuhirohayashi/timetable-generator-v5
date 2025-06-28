#!/usr/bin/env python3
"""火曜5限の詳細分析スクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def analyze_tuesday_5th():
    """火曜5限の配置状況を詳細分析"""
    
    # データディレクトリのパス
    data_dir = Path(__file__).parent / "data"
    output_path = data_dir / "output" / "output.csv"
    
    # CSVファイルを読み込み
    df = pd.read_csv(output_path, header=None)
    
    # ヘッダー行を処理
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # 火曜5限のインデックスを見つける
    tuesday_5th_indices = []
    for i, (day, period) in enumerate(zip(days, periods)):
        if day == "火" and str(period) == "5":
            tuesday_5th_indices.append(i + 1)  # +1 because of class name column
    
    if not tuesday_5th_indices:
        print("火曜5限が見つかりません")
        return
    
    tuesday_5th_idx = tuesday_5th_indices[0]
    
    print("=== 火曜5限の配置状況 ===\n")
    
    # 教師別の担当クラスを収集
    teacher_assignments = defaultdict(list)
    subject_count = defaultdict(int)
    
    # 各クラスの火曜5限の授業を取得
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
            
        subject = df.iloc[row_idx, tuesday_5th_idx]
        if pd.isna(subject) or subject == "":
            continue
        
        print(f"{class_name}: {subject}")
        
        # 教科をカウント
        subject_count[subject] += 1
        
        # 教師情報を推定（簡易版）
        if subject == "数":
            if "2年" in class_name:
                teacher_assignments["井上"].append((class_name, subject))
            elif "3年" in class_name:
                teacher_assignments["数学担当"].append((class_name, subject))
        elif subject == "自立":
            if "7組" in class_name:
                teacher_assignments["智田"].append((class_name, subject))
            elif "6組" in class_name:
                teacher_assignments["財津"].append((class_name, subject))
        elif subject == "国":
            if "5組" in class_name:
                teacher_assignments["寺田"].append((class_name, subject))
        elif subject == "保":
            teacher_assignments["体育担当"].append((class_name, subject))
        elif subject == "英":
            teacher_assignments["英語担当"].append((class_name, subject))
    
    print("\n=== 教科別配置数 ===")
    for subject, count in sorted(subject_count.items(), key=lambda x: x[1], reverse=True):
        print(f"{subject}: {count}クラス")
    
    print("\n=== 教師別担当状況（推定） ===")
    conflicts = []
    for teacher, assignments in sorted(teacher_assignments.items()):
        print(f"\n{teacher}先生:")
        for class_name, subject in assignments:
            print(f"  - {class_name}: {subject}")
        
        # 5組以外で複数クラスを担当している場合は競合
        non_grade5_classes = [(c, s) for c, s in assignments if "5組" not in c]
        if len(non_grade5_classes) > 1:
            conflicts.append((teacher, non_grade5_classes))
    
    if conflicts:
        print("\n=== 検出された競合 ===")
        for teacher, classes in conflicts:
            class_list = ", ".join([f"{c}({s})" for c, s in classes])
            print(f"❌ {teacher}先生が同時に複数クラスを担当: {class_list}")
    else:
        print("\n✅ 教師の競合は検出されませんでした")
    
    # 交流学級のチェック
    print("\n=== 交流学級の同期状況 ===")
    exchange_pairs = [
        ("1年6組", "1年1組"),
        ("1年7組", "1年2組"),
        ("2年6組", "2年3組"),
        ("2年7組", "2年2組"),
        ("3年6組", "3年3組"),
        ("3年7組", "3年2組"),
    ]
    
    for exchange, parent in exchange_pairs:
        exchange_subject = None
        parent_subject = None
        
        for row_idx in range(2, len(df)):
            class_name = df.iloc[row_idx, 0]
            if class_name == exchange:
                exchange_subject = df.iloc[row_idx, tuesday_5th_idx]
            elif class_name == parent:
                parent_subject = df.iloc[row_idx, tuesday_5th_idx]
        
        if exchange_subject and parent_subject:
            if exchange_subject == "自立":
                if parent_subject in ["数", "英"]:
                    print(f"✅ {exchange}(自立) ← {parent}({parent_subject})")
                else:
                    print(f"❌ {exchange}(自立) ← {parent}({parent_subject}) ※数か英である必要があります")
            elif exchange_subject == parent_subject:
                print(f"✅ {exchange}({exchange_subject}) = {parent}({parent_subject})")
            else:
                print(f"❌ {exchange}({exchange_subject}) ≠ {parent}({parent_subject})")

if __name__ == "__main__":
    analyze_tuesday_5th()