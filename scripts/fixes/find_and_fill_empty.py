#!/usr/bin/env python3
"""空きコマを見つけて埋める"""

import csv

def find_empty_slots():
    """空きコマを見つける"""
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    day_row = rows[0]
    period_row = rows[1]
    
    empty_slots = []
    
    for row_idx, row in enumerate(rows[2:], 2):
        if len(row) > 0 and row[0]:
            class_name = row[0]
            for col_idx in range(1, len(row)):
                if col_idx < len(day_row) and col_idx < len(period_row):
                    if not row[col_idx] or row[col_idx] == "":
                        day = day_row[col_idx]
                        period = period_row[col_idx]
                        empty_slots.append({
                            'row_idx': row_idx,
                            'col_idx': col_idx,
                            'class': class_name,
                            'day': day,
                            'period': period
                        })
    
    return empty_slots, rows

def main():
    empty_slots, rows = find_empty_slots()
    
    print(f"=== 空きコマ: {len(empty_slots)}個 ===")
    for slot in empty_slots:
        print(f"{slot['class']} {slot['day']}曜{slot['period']}限")
    
    # 3年6組と3年7組の空きコマを埋める
    for slot in empty_slots:
        if slot['class'] == "3年6組":
            # 3年6組には音楽が不足
            rows[slot['row_idx']][slot['col_idx']] = "音"
            print(f"\n{slot['class']} {slot['day']}曜{slot['period']}限 → 音")
        elif slot['class'] == "3年7組":
            # 3年7組には保健体育が不足
            rows[slot['row_idx']][slot['col_idx']] = "保"
            print(f"\n{slot['class']} {slot['day']}曜{slot['period']}限 → 保")
    
    # ファイルに保存
    with open("data/output/output.csv", 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print("\ndata/output/output.csv を更新しました")

if __name__ == "__main__":
    main()