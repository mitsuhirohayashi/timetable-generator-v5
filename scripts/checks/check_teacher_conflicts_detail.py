#!/usr/bin/env python3
"""教師重複制約の詳細チェックスクリプト"""

import pandas as pd
import json
import os

# データファイルを読み込む
schedule_df = pd.read_csv('data/output/output.csv', header=None)
teacher_df = pd.read_csv('data/config/teacher_subject_mapping.csv')

# 時間割データを整形
days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]

# 制約除外ルールを読み込む
exclusion_rules = {}
try:
    rules_path = os.path.join('data', 'config', 'constraint_exclusion_rules.json')
    if os.path.exists(rules_path):
        with open(rules_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            exclusion_rules = data.get('exclusion_rules', {})
            print(f"制約除外ルールを読み込みました: {rules_path}")
except Exception as e:
    print(f"制約除外ルールの読み込みに失敗: {e}")

# テスト期間を取得
test_periods = set()
if 'test_periods' in exclusion_rules:
    for period_info in exclusion_rules['test_periods'].get('periods', []):
        day = period_info['day']
        for period in period_info['periods']:
            test_periods.add((day, period))

print(f"テスト期間: {test_periods}")
print()

# 特定の時間の教師重複をチェック
def check_specific_conflicts():
    print("=== 特定の教師重複の詳細チェック ===\n")
    
    # 1. 月曜5限の社会科（北先生）
    print("1. 月曜5限の社会科（北先生）:")
    col_idx = 0 * 6 + 4 + 1  # 月曜5限のカラムインデックス
    
    # 3年2組と3年3組の状況
    class_3_2_subject = schedule_df.iloc[16, col_idx]  # 3年2組
    class_3_3_subject = schedule_df.iloc[17, col_idx]  # 3年3組
    
    print(f"  - 3年2組: {class_3_2_subject}")
    print(f"  - 3年3組: {class_3_3_subject}")
    
    # 教師を確認
    teacher_3_2 = teacher_df[(teacher_df['学年'] == 3) & (teacher_df['組'] == 2) & (teacher_df['教科'] == '社')]['教員名'].values[0]
    teacher_3_3 = teacher_df[(teacher_df['学年'] == 3) & (teacher_df['組'] == 3) & (teacher_df['教科'] == '社')]['教員名'].values[0]
    
    print(f"  - 3年2組の社会教師: {teacher_3_2}")
    print(f"  - 3年3組の社会教師: {teacher_3_3}")
    print(f"  -> 教師重複: {'はい' if teacher_3_2 == teacher_3_3 else 'いいえ'}")
    
    # テスト期間かどうか
    is_test = ('月', 5) in test_periods
    print(f"  -> テスト期間: {'はい' if is_test else 'いいえ'}")
    
    print()
    
    # 2. 火曜5限の数学（井上先生）
    print("2. 火曜5限の数学（井上先生）:")
    col_idx = 1 * 6 + 4 + 1  # 火曜5限のカラムインデックス
    
    # 2年1組と2年2組の状況
    class_2_1_subject = schedule_df.iloc[8, col_idx]   # 2年1組
    class_2_2_subject = schedule_df.iloc[9, col_idx]   # 2年2組
    
    print(f"  - 2年1組: {class_2_1_subject}")
    print(f"  - 2年2組: {class_2_2_subject}")
    
    # 教師を確認
    teacher_2_1 = teacher_df[(teacher_df['学年'] == 2) & (teacher_df['組'] == 1) & (teacher_df['教科'] == '数')]['教員名'].values[0]
    teacher_2_2 = teacher_df[(teacher_df['学年'] == 2) & (teacher_df['組'] == 2) & (teacher_df['教科'] == '数')]['教員名'].values[0]
    
    print(f"  - 2年1組の数学教師: {teacher_2_1}")
    print(f"  - 2年2組の数学教師: {teacher_2_2}")
    print(f"  -> 教師重複: {'はい' if teacher_2_1 == teacher_2_2 else 'いいえ'}")
    
    # テスト期間かどうか
    is_test = ('火', 5) in test_periods
    print(f"  -> テスト期間: {'はい' if is_test else 'いいえ'}")
    
    # 学習ルールをチェック
    print("\n  学習ルールのチェック:")
    print("  QA.txtから: 井上先生は火曜5限に最大1クラスまで")
    print("  -> この学習ルールに違反しています")

# 5組の合同授業をチェック
def check_grade5_joint_classes():
    print("\n\n=== 5組の合同授業チェック ===")
    
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    
    for day_idx, day in enumerate(days):
        for period_idx, period in enumerate(periods):
            col_idx = day_idx * 6 + period_idx + 1
            
            # 5組の授業を収集
            subjects = []
            for i, class_name in enumerate(grade5_classes):
                row_idx = [5, 11, 18][i]  # 1-5, 2-5, 3-5の行インデックス
                subject = schedule_df.iloc[row_idx, col_idx]
                subjects.append(subject)
            
            # 全て同じ科目かチェック
            if len(set(subjects)) == 1 and subjects[0] not in ['欠', '']:
                # 教師を確認
                teachers = []
                for i in range(3):
                    grade = i + 1
                    subject_name = subjects[0]
                    teacher_match = teacher_df[
                        (teacher_df['学年'] == grade) & 
                        (teacher_df['組'] == 5) & 
                        (teacher_df['教科'] == subject_name)
                    ]
                    if len(teacher_match) > 0:
                        teachers.append(teacher_match['教員名'].values[0])
                
                if len(set(teachers)) == 1:
                    print(f"{day}曜{period}限: {subjects[0]} - {teachers[0]}先生（5組合同授業）")

# メイン処理
if __name__ == "__main__":
    check_specific_conflicts()
    check_grade5_joint_classes()