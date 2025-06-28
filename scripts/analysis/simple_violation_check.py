#!/usr/bin/env python3

import csv
from collections import defaultdict

def check_violations():
    """シンプルな制約違反チェック"""
    
    # CSVファイルを読み込む
    with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダーをスキップ
    data_rows = rows[2:]  # 3行目から
    
    print("=== 時間割の問題点分析 ===\n")
    
    # 1. 空きスロットの確認
    empty_slots = []
    for row_idx, row in enumerate(data_rows):
        if not row or not row[0]:  # 空行またはクラス名なし
            continue
        class_name = row[0]
        for col_idx in range(1, 31):  # 月1〜金6
            if col_idx < len(row) and not row[col_idx].strip():
                day = ['月', '火', '水', '木', '金'][(col_idx-1)//6]
                period = ((col_idx-1) % 6) + 1
                empty_slots.append((class_name, day, period))
    
    print(f"【空きスロット】 {len(empty_slots)}個")
    for cls, day, period in empty_slots:
        print(f"  {cls}: {day}曜{period}限")
    
    # 2. 日内重複の確認
    print("\n【日内重複】")
    duplicates = []
    for row_idx, row in enumerate(data_rows):
        if not row or not row[0]:
            continue
        class_name = row[0]
        
        # 各曜日ごとにチェック
        for day_idx in range(5):  # 月〜金
            day_subjects = []
            for period in range(6):  # 1〜6限
                col_idx = day_idx * 6 + period + 1
                if col_idx < len(row) and row[col_idx].strip():
                    subject = row[col_idx].strip()
                    # YT、道、総、学活などは除外
                    if subject not in ['YT', '道', '総', '学', '学総', '行', '欠', '']:
                        day_subjects.append(subject)
            
            # 重複をチェック
            subject_count = defaultdict(int)
            for subj in day_subjects:
                subject_count[subj] += 1
            
            for subj, count in subject_count.items():
                if count > 1:
                    day = ['月', '火', '水', '木', '金'][day_idx]
                    duplicates.append((class_name, day, subj, count))
    
    if duplicates:
        for cls, day, subj, count in duplicates:
            print(f"  {cls}: {day}曜日に「{subj}」が{count}回")
    else:
        print("  なし")
    
    # 3. 教師配置の確認（教師情報がないため簡易チェック）
    print("\n【5組の合同授業確認】")
    # 5組（1-5, 2-5, 3-5）が同じ時間に同じ科目か確認
    grade5_classes = ['1年5組', '2年5組', '3年5組']
    grade5_rows = {}
    
    for row in data_rows:
        if row and row[0] in grade5_classes:
            grade5_rows[row[0]] = row
    
    if len(grade5_rows) == 3:
        mismatches = []
        for col_idx in range(1, 31):
            subjects = []
            for cls in grade5_classes:
                if col_idx < len(grade5_rows[cls]):
                    subjects.append(grade5_rows[cls][col_idx].strip())
                else:
                    subjects.append('')
            
            # 全て同じでない場合
            if len(set(subjects)) > 1 and any(subjects):
                day = ['月', '火', '水', '木', '金'][(col_idx-1)//6]
                period = ((col_idx-1) % 6) + 1
                mismatches.append((day, period, subjects))
        
        if mismatches:
            print("  5組で科目が異なる時間:")
            for day, period, subjects in mismatches[:5]:  # 最初の5個だけ表示
                print(f"    {day}曜{period}限: {dict(zip(grade5_classes, subjects))}")
        else:
            print("  5組は全て同じ科目で同期されています")
    
    # 4. 交流学級の同期確認
    print("\n【交流学級の同期確認】")
    exchange_pairs = [
        ('1年1組', '1年6組'),
        ('1年2組', '1年7組'),
        ('2年3組', '2年6組'),
        ('2年2組', '2年7組'),
        ('3年3組', '3年6組'),
        ('3年2組', '3年7組')
    ]
    
    class_rows = {row[0]: row for row in data_rows if row and row[0]}
    
    sync_issues = []
    for parent, exchange in exchange_pairs:
        if parent in class_rows and exchange in class_rows:
            parent_row = class_rows[parent]
            exchange_row = class_rows[exchange]
            
            for col_idx in range(1, 31):
                if col_idx < len(parent_row) and col_idx < len(exchange_row):
                    parent_subj = parent_row[col_idx].strip()
                    exchange_subj = exchange_row[col_idx].strip()
                    
                    # 交流学級が自立活動の場合は除外
                    if exchange_subj == '自立':
                        continue
                    
                    # 異なる場合（空きスロットも含む）
                    if parent_subj != exchange_subj:
                        day = ['月', '火', '水', '木', '金'][(col_idx-1)//6]
                        period = ((col_idx-1) % 6) + 1
                        sync_issues.append((parent, exchange, day, period, parent_subj, exchange_subj))
    
    if sync_issues:
        print("  交流学級が親学級と異なる授業:")
        for parent, exchange, day, period, p_subj, e_subj in sync_issues[:10]:  # 最初の10個
            print(f"    {day}曜{period}限: {parent}「{p_subj}」 vs {exchange}「{e_subj}」")
    else:
        print("  交流学級は正しく同期されています")

if __name__ == '__main__':
    check_violations()