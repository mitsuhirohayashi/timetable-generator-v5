#!/usr/bin/env python3
"""
実際の教師担当に基づいて教師重複を分析する

教師-科目-クラスのマッピングを読み込んで、実際の重複を確認
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from collections import defaultdict
from typing import Dict, List, Tuple, Set

def load_teacher_mapping() -> Dict[Tuple[str, str], str]:
    """教師-科目-クラスのマッピングを読み込む"""
    df = pd.read_csv('data/config/teacher_subject_mapping.csv', encoding='utf-8')
    
    mapping = {}
    for _, row in df.iterrows():
        teacher = row['教員名']
        subject = row['教科']
        grade = row['学年']
        class_num = row['組']
        
        class_name = f"{grade}年{class_num}組"
        mapping[(subject, class_name)] = teacher
    
    return mapping

def load_schedule(filepath: str) -> pd.DataFrame:
    """CSVファイルから時間割を読み込む"""
    df = pd.read_csv(filepath, encoding='utf-8')
    return df

def analyze_all_teacher_conflicts(df: pd.DataFrame, teacher_mapping: Dict[Tuple[str, str], str]) -> Dict[str, Dict[Tuple[str, int], List[str]]]:
    """全教師の時間帯ごとの担当クラスを分析"""
    teacher_schedule = defaultdict(lambda: defaultdict(list))
    
    # 時間割の列を処理
    days = ['月', '火', '水', '木', '金']
    for day_idx, day in enumerate(days):
        for period in range(1, 7):
            col_idx = day_idx * 6 + period + 1  # +2 because of header columns
            
            for idx, row in df.iterrows():
                if idx < 2:  # Skip header rows
                    continue
                    
                class_name = row.iloc[0]
                if pd.isna(class_name) or class_name == '':
                    continue
                
                if col_idx < len(row):
                    subject = row.iloc[col_idx]
                    if pd.notna(subject) and subject != '':
                        # この科目とクラスの組み合わせから教師を特定
                        teacher = teacher_mapping.get((subject, class_name), "不明")
                        
                        # 5組の合同授業は特別扱い
                        if class_name in ['1年5組', '2年5組', '3年5組'] and teacher != "不明":
                            # 同じ科目・同じ教師なら合同授業として1つにカウント
                            grade5_key = f"5組合同({subject})"
                            if grade5_key not in teacher_schedule[teacher][(day, period)]:
                                teacher_schedule[teacher][(day, period)].append(grade5_key)
                        else:
                            teacher_schedule[teacher][(day, period)].append(f"{class_name}:{subject}")
    
    # 実際の重複のみを返す
    conflicts = {}
    for teacher, schedule in teacher_schedule.items():
        teacher_conflicts = {}
        for time_slot, classes in schedule.items():
            if len(classes) > 1:
                teacher_conflicts[time_slot] = classes
        
        if teacher_conflicts:
            conflicts[teacher] = teacher_conflicts
    
    return conflicts

def main():
    """メイン処理"""
    # 教師マッピングを読み込み
    print("教師-科目-クラスのマッピングを読み込み中...")
    teacher_mapping = load_teacher_mapping()
    
    # スケジュールを読み込み
    print("スケジュールを読み込み中...")
    df = load_schedule('data/output/output.csv')
    
    # 全教師の重複を分析
    conflicts = analyze_all_teacher_conflicts(df, teacher_mapping)
    
    if not conflicts:
        print("\n教師の重複はありません！")
        return
    
    # 重複を表示
    print("\n=== 教師の重複状況 ===")
    
    # 教師名でソート
    for teacher in sorted(conflicts.keys()):
        if teacher == "不明":
            continue
            
        print(f"\n{teacher}先生:")
        teacher_conflicts = conflicts[teacher]
        
        # 時間順でソート
        for (day, period), classes in sorted(teacher_conflicts.items()):
            print(f"  {day}曜{period}限: {', '.join(classes)}")
    
    # 不明な教師がいる場合
    if "不明" in conflicts:
        print("\n警告: 教師が不明な授業があります:")
        for (day, period), classes in sorted(conflicts["不明"].items()):
            print(f"  {day}曜{period}限: {', '.join(classes)}")
    
    # サマリー
    print(f"\n=== サマリー ===")
    print(f"重複がある教師数: {len([t for t in conflicts.keys() if t != '不明'])}")
    total_conflicts = sum(len(schedule) for schedule in conflicts.values())
    print(f"総重複時間数: {total_conflicts}")

if __name__ == "__main__":
    main()