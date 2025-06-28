#!/usr/bin/env python3
"""火曜4限の分析スクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def load_teacher_mapping():
    """教師配置マッピングを読み込み"""
    mapping_path = Path(__file__).parent / "data" / "config" / "teacher_subject_mapping.csv"
    df = pd.read_csv(mapping_path)
    
    teacher_map = {}
    for _, row in df.iterrows():
        grade = int(row['学年'])
        class_num = int(row['組'])
        subject = row['教科']
        teacher = row['教員名']
        teacher_map[(grade, class_num, subject)] = teacher
    
    return teacher_map

def analyze_tuesday_4th():
    """火曜4限の配置状況を分析"""
    
    # データ読み込み
    data_dir = Path(__file__).parent / "data"
    output_path = data_dir / "output" / "output.csv"
    teacher_map = load_teacher_mapping()
    
    # CSVファイルを読み込み
    df = pd.read_csv(output_path, header=None)
    
    # ヘッダー行を処理
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # 火曜4限のインデックスを見つける
    tuesday_4th_idx = None
    for i, (day, period) in enumerate(zip(days, periods)):
        if day == "火" and str(period) == "4":
            tuesday_4th_idx = i + 1
            break
    
    print("=== 火曜4限（HF時間）の配置状況 ===\n")
    
    # 各クラスの火曜4限の授業を取得
    assignments = []
    teacher_conflicts = defaultdict(list)
    
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
            
        subject = df.iloc[row_idx, tuesday_4th_idx]
        if pd.isna(subject) or subject == "":
            continue
        
        # クラス名から学年と組を抽出
        if "年" in class_name and "組" in class_name:
            parts = class_name.split("年")
            grade = int(parts[0])
            class_num = int(parts[1].replace("組", ""))
            
            # 教師を特定
            teacher = teacher_map.get((grade, class_num, subject), f"{subject}担当")
            
            assignments.append({
                'class': class_name,
                'subject': subject,
                'teacher': teacher,
                'grade': grade
            })
            
            teacher_conflicts[teacher].append(class_name)
            
            print(f"{class_name}: {subject} ({teacher})")
    
    print("\n【問題点の分析】")
    
    # 1. HF時間に2年生の授業があるかチェック
    grade2_classes = [a for a in assignments if a['grade'] == 2]
    if grade2_classes:
        print("\n❌ HF時間（火曜4限）に2年生の授業が配置されています：")
        for a in grade2_classes:
            print(f"  - {a['class']}: {a['subject']} ({a['teacher']})")
        print("  ※ 2年の教員はHFに参加するため、授業配置は不可です")
    
    # 2. 同じ教師が複数クラスを担当しているかチェック
    print("\n【教師の重複チェック】")
    conflicts_found = False
    for teacher, classes in teacher_conflicts.items():
        if len(classes) > 1:
            # 5組の合同授業は除外
            non_grade5 = [c for c in classes if "5組" not in c]
            if len(non_grade5) > 1:
                conflicts_found = True
                print(f"❌ {teacher}先生が同時に複数クラスを担当: {', '.join(classes)}")
    
    if not conflicts_found:
        print("✅ 教師の重複はありません")
    
    # 3. 会議参加者の確認
    print("\n【HF（ホームフレンド）会議情報】")
    print("参加者: 2年団の全教員")
    print("時間: 火曜4限")
    print("影響: 2年生のクラスには授業を配置できません")
    
    # Follow-up.csvの内容を確認
    followup_path = data_dir / "input" / "Follow-up.csv"
    if followup_path.exists():
        print("\n【Follow-up.csvの会議情報】")
        with open(followup_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "HF" in content or "ホームフレンド" in content:
                lines = content.split('\n')
                for line in lines:
                    if "HF" in line or "ホームフレンド" in line:
                        print(f"  {line.strip()}")

if __name__ == "__main__":
    analyze_tuesday_4th()