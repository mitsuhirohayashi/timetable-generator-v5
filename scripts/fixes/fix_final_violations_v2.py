#!/usr/bin/env python3
"""最終的な制約違反を修正するスクリプト（改良版）"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import csv
from collections import defaultdict, Counter

def load_csv():
    """CSVファイルを読み込む"""
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    return rows

def save_csv(rows):
    """CSVファイルを保存"""
    with open("data/output/output.csv", 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

def fix_shiraishi_conflict(rows):
    """白石先生の火曜5限の重複を修正"""
    print("=== 白石先生の重複修正 ===")
    
    # ヘッダー行
    day_row = rows[0]
    period_row = rows[1]
    
    # 火曜5限の列を見つける
    tue5_col = None
    for i, (day, period) in enumerate(zip(day_row, period_row)):
        if day == "火" and period == "5":
            tue5_col = i
            break
    
    # 3年1組の火曜5限を確認
    for i, row in enumerate(rows):
        if len(row) > 0 and row[0] == "3年1組":
            if tue5_col < len(row) and row[tue5_col] == "理":
                # 別の時間の理と交換
                for j in range(1, len(row)):
                    if j != tue5_col and row[j] != "理" and row[j] not in ["欠", "YT", "技家", ""]:
                        # 交換可能な科目を見つけた
                        temp = row[j]
                        row[j] = "理"
                        row[tue5_col] = temp
                        print(f"3年1組: 火曜5限の理を{temp}に変更、{day_row[j]}曜{period_row[j]}限を理に変更")
                        break
            break

def fix_tue_duplicate(rows):
    """3年2組の火曜日の理の重複を修正"""
    print("\n=== 3年2組火曜日の重複修正 ===")
    
    # ヘッダー行
    day_row = rows[0]
    period_row = rows[1]
    
    # 3年2組を見つける
    for row_idx, row in enumerate(rows):
        if len(row) > 0 and row[0] == "3年2組":
            # 火曜日の理を収集
            tue_sciences = []
            for col_idx, (day, period) in enumerate(zip(day_row, period_row)):
                if day == "火" and col_idx < len(row) and row[col_idx] == "理":
                    tue_sciences.append((col_idx, period))
            
            if len(tue_sciences) >= 2:
                # 2つ目の理を別の科目に変更
                col_to_change = tue_sciences[1][0]
                # 不足している科目を見つける
                alt = find_needed_subject("3年2組", row)
                if alt:
                    row[col_to_change] = alt
                    print(f"3年2組の火曜{tue_sciences[1][1]}限: 理→{alt}")
            break

def fix_gym_mon6(rows):
    """月曜6限の体育館使用を修正"""
    print("\n=== 月曜6限の体育館使用修正 ===")
    
    # ヘッダー行
    day_row = rows[0]
    period_row = rows[1]
    
    # 月曜6限の列を見つける
    mon6_col = None
    for i, (day, period) in enumerate(zip(day_row, period_row)):
        if day == "月" and period == "6":
            mon6_col = i
            break
    
    # 月曜6限に保があるクラスを確認
    pe_classes = []
    for i, row in enumerate(rows):
        if len(row) > 0 and row[0] and "3年" in row[0]:
            if mon6_col < len(row) and row[mon6_col] == "保":
                pe_classes.append((i, row[0]))
    
    print(f"月曜6限に保健体育: {[c[1] for c in pe_classes]}")
    
    # 3年2組以外の保を別の科目に変更
    for row_idx, class_name in pe_classes:
        if class_name != "3年2組":
            # 不足している科目を見つける
            alt = find_needed_subject(class_name, rows[row_idx])
            if alt:
                rows[row_idx][mon6_col] = alt
                print(f"{class_name}の月曜6限: 保→{alt}")

def find_needed_subject(class_name, row):
    """不足している科目を見つける"""
    # 標準時数を取得
    base_hours = get_class_base_hours(class_name)
    
    # 現在の科目数をカウント
    current_counts = Counter()
    for cell in row[1:]:
        if cell and cell not in ["欠", "YT", ""]:
            current_counts[cell] += 1
    
    # 不足している科目を探す（日生を優先）
    if "日生" in base_hours and current_counts.get("日生", 0) < base_hours["日生"]:
        return "日生"
    
    # 主要科目で不足しているものを探す
    for subject in ["国", "数", "英", "理", "社"]:
        if subject in base_hours:
            target = base_hours[subject]
            current = current_counts.get(subject, 0)
            if current < target:
                return subject
    
    # その他の科目
    for subject, target in base_hours.items():
        if subject not in ["欠", "YT", "学", "道", "総", "学総", "保"]:
            current = current_counts.get(subject, 0)
            if current < target:
                return subject
    
    return None

def get_class_base_hours(class_name):
    """特定クラスの標準時数を取得"""
    base_hours = {}
    with open("data/config/base_timetable.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から科目を取得
    subjects = [cell.strip() for cell in rows[1][1:] if cell.strip()]
    
    # 該当クラスの標準時数を取得
    for row in rows[2:]:
        if len(row) > 0 and row[0] == class_name:
            for i, subject in enumerate(subjects):
                if i + 1 < len(row) and row[i + 1]:
                    try:
                        hours = float(row[i + 1])
                        if hours > 0:
                            base_hours[subject] = hours
                    except ValueError:
                        pass
            break
    
    return base_hours

def fill_remaining_empty_v2(rows):
    """残りの空きコマを埋める（改良版）"""
    print("\n=== 残りの空きコマを埋める ===")
    
    # ヘッダー行
    day_row = rows[0]
    period_row = rows[1]
    
    filled = 0
    for row_idx, row in enumerate(rows[2:], 2):
        if len(row) == 0 or not row[0]:
            continue
        
        class_name = row[0]
        if "3年6組" in class_name or "3年7組" in class_name:
            for col_idx in range(1, len(row)):
                if col_idx < len(row) and (not row[col_idx] or row[col_idx] == ""):
                    # 特別な時間枠はスキップ
                    if col_idx < len(day_row) and col_idx < len(period_row):
                        day = day_row[col_idx]
                        period = period_row[col_idx]
                        
                        # 固定時間はスキップ
                        if (day == "金" and period == "6") or (day == "月" and period == "6" and "3年" not in class_name):
                            continue
                        
                        # 不足科目を見つける
                        alt = find_needed_subject(class_name, row)
                        if alt:
                            row[col_idx] = alt
                            filled += 1
                            print(f"{class_name}の{day}曜{period}限: 空き→{alt}")
    
    print(f"合計{filled}個の空きコマを埋めました")

def main():
    """メイン処理"""
    print("最終的な制約違反の修正を開始します（改良版）")
    
    # CSVを読み込む
    rows = load_csv()
    
    # 各種修正を実行
    fix_shiraishi_conflict(rows)
    fix_tue_duplicate(rows)
    fix_gym_mon6(rows)
    fill_remaining_empty_v2(rows)
    
    # CSVを保存
    save_csv(rows)
    print("\n修正完了: data/output/output.csv を更新しました")

if __name__ == "__main__":
    main()