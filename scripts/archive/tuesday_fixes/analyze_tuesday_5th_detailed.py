#!/usr/bin/env python3
"""火曜5限の詳細な教師競合分析"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def load_teacher_mapping():
    """教師配置マッピングを読み込み"""
    mapping_path = Path(__file__).parent / "data" / "config" / "teacher_subject_mapping.csv"
    df = pd.read_csv(mapping_path)
    
    # (学年, 組, 教科) -> 教師名 のマッピングを作成
    teacher_map = {}
    for _, row in df.iterrows():
        grade = int(row['学年'])
        class_num = int(row['組'])
        subject = row['教科']
        teacher = row['教員名']
        teacher_map[(grade, class_num, subject)] = teacher
    
    return teacher_map

def analyze_tuesday_5th_detailed():
    """火曜5限の教師競合を詳細分析"""
    
    # データ読み込み
    data_dir = Path(__file__).parent / "data"
    output_path = data_dir / "output" / "output.csv"
    teacher_map = load_teacher_mapping()
    
    # CSVファイルを読み込み
    df = pd.read_csv(output_path, header=None)
    
    # ヘッダー行を処理
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # 火曜5限のインデックスを見つける
    tuesday_5th_idx = None
    for i, (day, period) in enumerate(zip(days, periods)):
        if day == "火" and str(period) == "5":
            tuesday_5th_idx = i + 1
            break
    
    if tuesday_5th_idx is None:
        print("火曜5限が見つかりません")
        return
    
    print("=== 火曜5限の詳細な教師配置分析 ===\n")
    
    # 教師別の担当クラスを収集
    teacher_assignments = defaultdict(list)
    all_assignments = []
    
    # 各クラスの火曜5限の授業を取得
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
            
        subject = df.iloc[row_idx, tuesday_5th_idx]
        if pd.isna(subject) or subject == "":
            continue
        
        # クラス名から学年と組を抽出
        if "年" in class_name and "組" in class_name:
            parts = class_name.split("年")
            grade = int(parts[0])
            class_num = int(parts[1].replace("組", ""))
            
            # 教師を特定
            teacher = teacher_map.get((grade, class_num, subject), f"{subject}担当")
            
            teacher_assignments[teacher].append({
                'class': class_name,
                'subject': subject,
                'grade': grade,
                'class_num': class_num
            })
            
            all_assignments.append({
                'class': class_name,
                'subject': subject,
                'teacher': teacher
            })
    
    # 全配置を表示
    print("【全クラスの配置】")
    for assign in sorted(all_assignments, key=lambda x: (x['class'][0], x['class'][2])):
        print(f"{assign['class']}: {assign['subject']} ({assign['teacher']})")
    
    print("\n【教師別担当状況】")
    conflicts = []
    
    for teacher, assignments in sorted(teacher_assignments.items()):
        if len(assignments) == 1:
            continue  # 1クラスのみ担当の場合はスキップ
            
        print(f"\n{teacher}先生: {len(assignments)}クラス担当")
        
        # 5組のみかチェック
        all_grade5 = all(a['class_num'] == 5 for a in assignments)
        
        for a in assignments:
            print(f"  - {a['class']}: {a['subject']}")
        
        # 競合判定
        if not all_grade5 and len(assignments) > 1:
            conflicts.append((teacher, assignments))
            print("  → ❌ 競合あり（5組以外で複数クラス）")
        elif all_grade5:
            print("  → ✅ OK（5組の合同授業）")
    
    if conflicts:
        print("\n【検出された競合の詳細】")
        for teacher, assignments in conflicts:
            print(f"\n❌ {teacher}先生の競合:")
            class_list = [a['class'] for a in assignments]
            print(f"  同時担当: {', '.join(class_list)}")
            
            # 解決案の提示
            print("  解決案:")
            if teacher == "井上" and any(a['subject'] == "数" for a in assignments):
                print("    - 2年2組か2年3組の数学を別の時間に移動")
            elif teacher == "智田" and any(a['subject'] == "自立" for a in assignments):
                print("    - 1年7組か2年7組の自立活動を別の時間に移動")
                print("    - ただし、親学級が数学か英語の時間である必要があります")
    else:
        print("\n✅ 教師の競合は検出されませんでした")
    
    # 5組の確認
    print("\n【5組の合同授業確認】")
    grade5_subjects = {}
    for assign in all_assignments:
        if "5組" in assign['class']:
            grade5_subjects[assign['class']] = assign['subject']
    
    if len(set(grade5_subjects.values())) == 1:
        subject = list(grade5_subjects.values())[0]
        teacher = teacher_map.get((1, 5, subject), f"{subject}担当")
        print(f"✅ 5組は全学年で同じ教科「{subject}」({teacher}先生)")
    else:
        print(f"❌ 5組の教科が不一致: {grade5_subjects}")

if __name__ == "__main__":
    analyze_tuesday_5th_detailed()