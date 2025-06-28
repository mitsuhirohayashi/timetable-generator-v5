#!/usr/bin/env python3
"""
交流学級の自立活動違反をチェック

交流学級が自立活動を行う時、親学級が数学または英語でない場合を検出
"""
import csv
from pathlib import Path

def check_jiritsu_violations():
    """自立活動違反をチェック"""
    # 交流学級と親学級の対応
    exchange_pairs = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    # CSVファイルを読み込み
    csv_path = Path("data/output/output.csv")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行から曜日と時限を取得
    days = rows[0][1:]  # 最初の列はクラス名なので除く
    periods = rows[1][1:]
    
    # 各クラスのデータを辞書に格納
    class_schedules = {}
    for row in rows[2:]:
        if row[0] and row[0] not in ["", " "]:  # 空行をスキップ
            class_name = row[0]
            schedule = row[1:]
            class_schedules[class_name] = schedule
    
    # 違反をチェック
    violations = []
    
    for exchange_class, parent_class in exchange_pairs.items():
        if exchange_class not in class_schedules or parent_class not in class_schedules:
            continue
            
        exchange_schedule = class_schedules[exchange_class]
        parent_schedule = class_schedules[parent_class]
        
        for i, (day, period, exchange_subject) in enumerate(zip(days, periods, exchange_schedule)):
            if exchange_subject == "自立":
                parent_subject = parent_schedule[i]
                
                # セル位置を計算（A=1, B=2, ...）
                col_letter = chr(65 + (i + 1))  # A列はクラス名なので+1
                row_number = list(class_schedules.keys()).index(exchange_class) + 3  # ヘッダー2行 + 1
                cell_position = f"{col_letter}{row_number}"
                
                if parent_subject not in ["数", "英"]:
                    violations.append({
                        'exchange_class': exchange_class,
                        'parent_class': parent_class,
                        'day': day,
                        'period': period,
                        'parent_subject': parent_subject,
                        'cell': cell_position,
                        'column_index': i + 1
                    })
                    print(f"違反: {exchange_class} {day}曜{period}限が自立 "
                          f"(親学級{parent_class}は「{parent_subject}」) - セル{cell_position}")
    
    print(f"\n違反数: {len(violations)}")
    
    # D列（4列目）の違反を特定
    d_violations = [v for v in violations if v['column_index'] == 3]  # 0ベースなので3
    if d_violations:
        print("\nD列の違反:")
        for v in d_violations:
            print(f"  {v['cell']}: {v['exchange_class']} (親学級は{v['parent_subject']})")
    
    # エラー表示の位置を推測
    print("\nエラー位置の推測:")
    print("各違反の詳細:")
    for v in violations:
        print(f"  {v['cell']}: {v['exchange_class']} {v['day']}曜{v['period']}限 "
              f"(親学級{v['parent_class']}は{v['parent_subject']})")
    
    # 行番号から推測
    print("\n行番号ベースの推測:")
    for v in violations:
        row = int(v['cell'][1:])
        if row == 12:
            print(f"  行12のエラー: {v['exchange_class']} - {v['cell']}")
        if row == 18:
            print(f"  行18のエラー: {v['exchange_class']} - {v['cell']}")

if __name__ == "__main__":
    check_jiritsu_violations()