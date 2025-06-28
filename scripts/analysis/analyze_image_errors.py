#!/usr/bin/env python3
"""
画像のエラー表示D12×、D18×の原因を分析
"""
import csv
from pathlib import Path

def analyze_errors():
    """エラーの原因を分析"""
    csv_path = Path("data/output/output.csv")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    print("=== CSVの内容確認 ===")
    print("行番号 | クラス名 | 木曜1限 | 木曜2限 | 木曜3限 | 木曜4限 | 木曜5限 | 木曜6限")
    print("-" * 80)
    
    # 木曜日の列インデックスを特定（0ベース）
    days = rows[0][1:]
    thursday_indices = [i+1 for i, d in enumerate(days) if d == "木"]  # +1はクラス名列のため
    
    for i, row in enumerate(rows[2:], start=3):  # 3行目から
        if row[0] and row[0].strip():
            class_name = row[0]
            thursday_subjects = [row[idx] if idx < len(row) else "" for idx in thursday_indices]
            
            # 12行目と18行目付近を強調
            highlight = ""
            if i in [12, 13, 18, 19, 20]:
                highlight = " ★"
                
            print(f"{i:3d} | {class_name:8s} | {' | '.join(s or '空' for s in thursday_subjects)}{highlight}")
    
    print("\n=== 問題の可能性 ===")
    
    # 3年6組の月曜6限の空白をチェック
    print("\n1. 3年6組（行20）の月曜6限が空白:")
    row_3_6 = rows[19]  # 0ベースで19
    if len(row_3_6) > 6:
        print(f"   月曜6限: '{row_3_6[6]}'")
    
    # 交流学級の自立活動違反を再確認
    print("\n2. 交流学級の自立活動違反:")
    exchange_pairs = {
        "1年7組": ("1年2組", 8),
        "2年7組": ("2年2組", 14),
    }
    
    for exchange, (parent, row) in exchange_pairs.items():
        print(f"   {exchange}（行{row}）の自立活動違反あり")
    
    # D列の特定のセルを確認
    print("\n3. D列（木曜）の特定セル内容:")
    print("   D12（2年5組の木曜2限）:", end="")
    if len(rows) > 11 and len(rows[11]) > thursday_indices[1]:
        print(f"'{rows[11][thursday_indices[1]]}'")
    
    print("   D18（3年3組の木曜2限）:", end="")
    if len(rows) > 17 and len(rows[17]) > thursday_indices[1]:
        print(f"'{rows[17][thursday_indices[1]]}'")
    
    # 画像のエラー表示の解釈
    print("\n=== エラー表示の解釈 ===")
    print("D12×とD18×は、おそらく:")
    print("1. 自立活動の親学級制約違反を示している")
    print("2. D列ではなく、異なる列の違反を示している可能性")
    print("3. または、時数不足などの別の問題を示している可能性")
    
    # 実際の違反箇所
    print("\n=== 実際の自立活動違反 ===")
    print("L8（1年7組 火曜5限）: 自立（親学級1年2組は「家」）")
    print("F14（2年7組 月曜5限）: 自立（親学級2年2組は「音」）")
    print("P14（2年7組 水曜3限）: 自立（親学級2年2組は「保」）")

if __name__ == "__main__":
    analyze_errors()