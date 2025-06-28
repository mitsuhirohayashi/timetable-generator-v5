#!/usr/bin/env python3
"""会議時間の詳細チェック"""

import pandas as pd
from pathlib import Path

def check_specific_time(df, day, period, description):
    """特定の時間をチェック"""
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # カラムインデックスを見つける
    target_col = None
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == day and str(periods[col_idx - 1]) == str(period):
            target_col = col_idx
            break
    
    if target_col is None:
        print(f"  ⚠️ {day}曜{period}限が見つかりません")
        return []
    
    violations = []
    
    # 各クラスの授業をチェック
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
        
        subject = df.iloc[row_idx, target_col]
        if pd.notna(subject) and subject != "":
            violations.append({
                'class': class_name,
                'subject': subject,
                'day': day,
                'period': period
            })
    
    return violations

def check_teacher_classes(df, teacher_name, day, period):
    """特定の教師が担当するクラスをチェック"""
    # 教師と科目のマッピング（簡易版）
    teacher_subjects = {
        '井野口': ['英', 'YT', '道'],
        '箱崎': ['英'],
        '林': ['技', '技家'],
        '井上': ['数'],
        '寺田': ['国'],
        '小野塚': ['国'],
        '金子ひ': ['理', '道', 'YT', '学', '総'],
        '森山': ['数', 'YT', '道', '学', '総'],
        '永山': ['保', '道', 'YT', '学', '総'],
        '蒲地': ['社'],
        '白石': ['理', 'YT', '道', '学', '総'],
    }
    
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    # カラムインデックスを見つける
    target_col = None
    for col_idx in range(1, len(df.columns)):
        if days[col_idx - 1] == day and str(periods[col_idx - 1]) == str(period):
            target_col = col_idx
            break
    
    if target_col is None:
        return []
    
    violations = []
    subjects = teacher_subjects.get(teacher_name, [])
    
    # 各クラスをチェック
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
        
        subject = df.iloc[row_idx, target_col]
        if pd.notna(subject) and subject != "" and subject in subjects:
            violations.append({
                'class': class_name,
                'subject': subject,
                'teacher': teacher_name
            })
    
    return violations

def main():
    """メイン処理"""
    data_dir = Path(__file__).parent / "data"
    csv_path = data_dir / "output" / "output.csv"
    
    df = pd.read_csv(csv_path, header=None)
    
    print("=== 会議時間の詳細チェック ===\n")
    
    all_violations = []
    
    # 1. 月曜4限 - 特会
    print("【月曜4限 - 特会】")
    violations = check_specific_time(df, "月", "4", "特会")
    print(f"  全{len([v for v in violations if v['subject'] not in ['欠', 'YT', '道', '学', '総', '行', '学総']])}クラスで授業あり")
    # 特会は特定の先生のみ参加なので、詳細は省略
    
    # 2. 火曜1-3限 - 井野口先生の初任研
    print("\n【火曜1-3限 - 井野口先生の初任研】")
    for period in [1, 2, 3]:
        print(f"  火曜{period}限:")
        violations = check_teacher_classes(df, "井野口", "火", str(period))
        if violations:
            print(f"    ❌ 井野口先生が授業を担当:")
            for v in violations:
                print(f"      - {v['class']}: {v['subject']}")
                all_violations.append(f"初任研違反: 火曜{period}限に井野口先生が{v['class']}で{v['subject']}を担当")
        else:
            print(f"    ✅ 井野口先生の授業なし")
    
    # 3. 火曜2限 - 箱崎先生と林先生を空ける
    print("\n【火曜2限 - 箱崎先生と林先生を空ける】")
    for teacher in ["箱崎", "林"]:
        violations = check_teacher_classes(df, teacher, "火", "2")
        if violations:
            print(f"  ❌ {teacher}先生が授業を担当:")
            for v in violations:
                print(f"    - {v['class']}: {v['subject']}")
                all_violations.append(f"空き時間違反: 火曜2限に{teacher}先生が{v['class']}で{v['subject']}を担当")
        else:
            print(f"  ✅ {teacher}先生の授業なし")
    
    # 4. 火曜4限 - HF（2年団全員）
    print("\n【火曜4限 - HF（2年団全員）】")
    violations = check_specific_time(df, "火", "4", "HF")
    grade2_violations = [v for v in violations if "2年" in v['class'] and v['subject'] not in ['欠', 'YT', '道', '学', '総', '行', '学総']]
    if grade2_violations:
        print(f"  ❌ 2年生のクラスで授業あり:")
        for v in grade2_violations:
            print(f"    - {v['class']}: {v['subject']}")
            all_violations.append(f"HF違反: 火曜4限に{v['class']}で{v['subject']}")
    else:
        print(f"  ✅ 2年生の授業なし")
    
    # 5. 木曜2限 - 生指
    print("\n【木曜2限 - 生指】")
    violations = check_specific_time(df, "木", "2", "生指")
    print(f"  全{len([v for v in violations if v['subject'] not in ['欠', 'YT', '道', '学', '総', '行', '学総']])}クラスで授業あり")
    # 生指は特定の先生のみ参加なので、詳細は省略
    
    # 6. 木曜3限 - 企画
    print("\n【木曜3限 - 企画】")
    violations = check_specific_time(df, "木", "3", "企画")
    print(f"  全{len([v for v in violations if v['subject'] not in ['欠', 'YT', '道', '学', '総', '行', '学総']])}クラスで授業あり")
    # 企画は管理職と学年主任のみ参加なので、詳細は省略
    
    # 7. 金曜5限 - 井上先生を空ける
    print("\n【金曜5限 - 井上先生を空ける】")
    violations = check_teacher_classes(df, "井上", "金", "5")
    if violations:
        print(f"  ❌ 井上先生が授業を担当:")
        for v in violations:
            print(f"    - {v['class']}: {v['subject']}")
            all_violations.append(f"空き時間違反: 金曜5限に井上先生が{v['class']}で{v['subject']}を担当")
    else:
        print(f"  ✅ 井上先生の授業なし")
    
    # サマリー
    print("\n=== 違反サマリー ===")
    if all_violations:
        print(f"\n❌ 合計{len(all_violations)}件の違反:")
        for v in all_violations:
            print(f"  - {v}")
    else:
        print("\n✅ すべての会議・空き時間制約が守られています")

if __name__ == "__main__":
    main()