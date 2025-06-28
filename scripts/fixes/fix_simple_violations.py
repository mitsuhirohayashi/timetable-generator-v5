#!/usr/bin/env python3
"""シンプルな違反修正スクリプト - CSVを直接編集"""

import csv
import os
import sys


def read_csv(filepath):
    """CSVファイルを読み込んでリストで返す"""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        return list(reader)


def write_csv(filepath, data):
    """データをCSVファイルに書き込む"""
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)


def fix_violations():
    """時間割の違反を修正"""
    print("=== 交流学級同期違反と日内重複違反の修正 ===")
    
    # CSVファイルを読み込む
    input_path = "data/output/output.csv"
    output_path = "data/output/output_fixed.csv"
    
    data = read_csv(input_path)
    
    # ヘッダー行をスキップ
    # data[0] = 基本時間割
    # data[1] = 曜日・時限
    
    # クラス名から行番号を特定
    class_to_row = {}
    for i, row in enumerate(data):
        if row and row[0]:
            class_name = row[0].strip()
            class_to_row[class_name] = i
    
    print("\n修正対象:")
    
    # 1. 交流学級同期違反の修正
    print("\n■ 交流学級同期違反の修正")
    
    # 3年3組と3年6組の行番号
    row_3_3 = class_to_row.get("3年3組")
    row_3_6 = class_to_row.get("3年6組")
    
    if row_3_3 and row_3_6:
        # 火曜5限（列11）の修正: 3-3=美 → 3-6も美に
        col_tue5 = 11
        if data[row_3_3][col_tue5] == "美":
            print(f"  火曜5限: 3-6を「{data[row_3_6][col_tue5]}」から「美」に変更")
            data[row_3_6][col_tue5] = "美"
        
        # 木曜2限（列20）の修正: 3-3=保 → 3-6も保に
        col_thu2 = 20
        if data[row_3_3][col_thu2] == "保":
            print(f"  木曜2限: 3-6を空欄から「保」に変更")
            data[row_3_6][col_thu2] = "保"
        
        # 金曜5限（列29）の修正: 3-3=保 → 3-6も保に
        col_fri5 = 29
        if data[row_3_3][col_fri5] == "保":
            print(f"  金曜5限: 3-6を空欄から「保」に変更")
            data[row_3_6][col_fri5] = "保"
    
    # 2. 日内重複違反の修正（3-3の月曜）
    print("\n■ 日内重複違反の修正")
    print("  3年3組の月曜日:")
    
    if row_3_3:
        # 月曜の全時限をチェック（列1-6）
        monday_subjects = []
        for period in range(1, 7):
            col = period
            subject = data[row_3_3][col]
            monday_subjects.append((period, subject))
            print(f"    {period}限: {subject}")
        
        # 英語の重複を確認
        english_periods = [(p, s) for p, s in monday_subjects if s == "英"]
        if len(english_periods) > 1:
            print(f"\n  英語が{len(english_periods)}回配置されています")
            
            # 6限（列6）の英語を国語に変更
            col_mon6 = 6
            print(f"  修正: 6限の「英」を「国」に変更")
            data[row_3_3][col_mon6] = "国"
            
            # 3-6も同様に変更（交流学級の同期）
            if row_3_6:
                data[row_3_6][col_mon6] = "国"
                print(f"  3-6も同期して「国」に変更")
    
    # ファイルに書き込む
    write_csv(output_path, data)
    
    print(f"\n修正完了！結果を {output_path} に保存しました。")
    print("\n※ 修正内容を確認後、以下のコマンドで上書きしてください:")
    print(f"  cp {output_path} {input_path}")
    print("\n※ その後、制約違反チェックを実行してください:")
    print("  python3 check_violations.py")


if __name__ == "__main__":
    fix_violations()