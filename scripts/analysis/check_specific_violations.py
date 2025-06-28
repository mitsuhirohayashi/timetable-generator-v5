#!/usr/bin/env python3
"""特定の違反を詳細確認するスクリプト"""

import pandas as pd
import csv

def load_timetable():
    """時間割データを読み込む"""
    timetable = {}
    with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行
        time_slots = next(reader)  # 時限行
        
        for row in reader:
            if not row or not row[0]:  # 空行スキップ
                continue
            class_name = row[0]
            timetable[class_name] = {}
            
            for i in range(1, len(row)):
                if i < len(headers) and i < len(time_slots):
                    day = headers[i]
                    period = time_slots[i]
                    subject = row[i] if i < len(row) else ""
                    
                    if day not in timetable[class_name]:
                        timetable[class_name][day] = {}
                    timetable[class_name][day][period] = subject
    
    return timetable

def check_specific_cases():
    """具体的なケースを確認"""
    timetable = load_timetable()
    
    print("=== 具体的な違反ケースの確認 ===\n")
    
    # 1. 月曜4限: 林田先生（英語）が3年1組と3年3組
    print("【月曜4限の英語】")
    print(f"3年1組: {timetable.get('3年1組', {}).get('月', {}).get('4', '空き')}")
    print(f"3年3組: {timetable.get('3年3組', {}).get('月', {}).get('4', '空き')}")
    print(f"→ 両方とも英語なら林田先生が重複\n")
    
    # 2. 月曜5限: 梶永先生（数学）が1年1組と1年3組
    print("【月曜5限の数学】")
    print(f"1年1組: {timetable.get('1年1組', {}).get('月', {}).get('5', '空き')}")
    print(f"1年3組: {timetable.get('1年3組', {}).get('月', {}).get('5', '空き')}")
    print(f"3年1組: {timetable.get('3年1組', {}).get('月', {}).get('5', '空き')}")
    print(f"→ 1年1組と1年3組が両方とも数学なら梶永先生が重複\n")
    
    # 3. 月曜5限: 北先生（社会）が3年2組と3年3組
    print("【月曜5限の社会】")
    print(f"3年2組: {timetable.get('3年2組', {}).get('月', {}).get('5', '空き')}")
    print(f"3年3組: {timetable.get('3年3組', {}).get('月', {}).get('5', '空き')}")
    print(f"→ 両方とも社会なら北先生が重複\n")
    
    # 4. 火曜5限: 井上先生（数学）が2年1組と2年2組
    print("【火曜5限の数学】")
    print(f"2年1組: {timetable.get('2年1組', {}).get('火', {}).get('5', '空き')}")
    print(f"2年2組: {timetable.get('2年2組', {}).get('火', {}).get('5', '空き')}")
    print(f"→ 両方とも数学なら井上先生が重複（QA.txtのルールで最大1クラスまで）\n")
    
    # 5. 5組の合同授業（正常なケース）の確認
    print("【5組の合同授業（月曜2限）】")
    print(f"1年5組: {timetable.get('1年5組', {}).get('月', {}).get('2', '空き')}")
    print(f"2年5組: {timetable.get('2年5組', {}).get('月', {}).get('2', '空き')}")
    print(f"3年5組: {timetable.get('3年5組', {}).get('月', {}).get('2', '空き')}")
    print(f"→ 全て同じ科目なら合同授業として正常\n")
    
    # 6. テスト期間（月曜1-3限）の確認
    print("【テスト期間（月曜1限）】")
    print("1年生:")
    print(f"  1年1組: {timetable.get('1年1組', {}).get('月', {}).get('1', '空き')}")
    print(f"  1年2組: {timetable.get('1年2組', {}).get('月', {}).get('1', '空き')}")
    print(f"  1年3組: {timetable.get('1年3組', {}).get('月', {}).get('1', '空き')}")
    print(f"→ 全て同じ科目ならテスト巡回として正常\n")
    
    # 7. 3年6組の空きコマ
    print("【3年6組の空きコマ】")
    print(f"木曜2限: {timetable.get('3年6組', {}).get('木', {}).get('2', '空き')}")
    print(f"金曜5限: {timetable.get('3年6組', {}).get('金', {}).get('5', '空き')}")

if __name__ == "__main__":
    check_specific_cases()