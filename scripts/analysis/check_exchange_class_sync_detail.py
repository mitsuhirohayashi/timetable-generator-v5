#!/usr/bin/env python3
"""交流学級の同期状況を詳細チェック"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def check_exchange_sync():
    """交流学級と親学級の同期をチェック"""
    print("=== 交流学級の同期状況チェック ===\n")
    
    # 交流学級マッピング
    exchange_mapping = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    # output.csvを読み込む
    with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # スケジュールデータを辞書形式に変換
    schedule_data = {}
    days = ["月", "火", "水", "木", "金"]
    
    for idx, row in enumerate(data):
        if idx < 2:  # ヘッダー行をスキップ
            continue
        
        class_name = row[0] if row else ""
        if not class_name or class_name.strip() == '':
            continue
        
        schedule_data[class_name] = {}
        col_idx = 1
        
        for day in days:
            for period in range(1, 7):
                if col_idx < len(row):
                    subject = row[col_idx].strip() if row[col_idx] else ""
                    schedule_data[class_name][(day, period)] = subject
                col_idx += 1
    
    # 同期違反をチェック
    violations = []
    
    for exchange_class, parent_class in exchange_mapping.items():
        print(f"\n{exchange_class} ← {parent_class}:")
        
        for day in days:
            for period in range(1, 7):
                slot = (day, period)
                
                exchange_subj = schedule_data.get(exchange_class, {}).get(slot, "")
                parent_subj = schedule_data.get(parent_class, {}).get(slot, "")
                
                # 空きスロットの場合
                if not exchange_subj and parent_subj:
                    print(f"  ⚠️  {day}曜{period}限: 交流学級が空き、親学級が{parent_subj}")
                    violations.append({
                        'exchange': exchange_class,
                        'parent': parent_class,
                        'day': day,
                        'period': period,
                        'exchange_subj': '(空き)',
                        'parent_subj': parent_subj
                    })
                
                # 自立活動以外で不一致の場合
                elif exchange_subj not in ["", "自立"] and parent_subj and exchange_subj != parent_subj:
                    print(f"  ❌ {day}曜{period}限: 交流学級が{exchange_subj}、親学級が{parent_subj}")
                    violations.append({
                        'exchange': exchange_class,
                        'parent': parent_class,
                        'day': day,
                        'period': period,
                        'exchange_subj': exchange_subj,
                        'parent_subj': parent_subj
                    })
                
                # 自立活動の場合は親学級をチェック
                elif exchange_subj == "自立":
                    if parent_subj not in ["数", "英"]:
                        print(f"  ❌ {day}曜{period}限: 自立活動時、親学級が{parent_subj}（数学か英語であるべき）")
    
    print(f"\n\n同期違反総数: {len(violations)}件")
    
    # 特に火曜6限と金曜6限をチェック
    print("\n【特別チェック：問題の時間帯】")
    print("\n1年6組 火曜6限:")
    print(f"  交流学級（1年6組）: {schedule_data.get('1年6組', {}).get(('火', 6), '(空き)')}")
    print(f"  親学級（1年1組）: {schedule_data.get('1年1組', {}).get(('火', 6), '(空き)')}")
    
    print("\n2年1組 金曜6限:")
    print(f"  2年1組: {schedule_data.get('2年1組', {}).get(('金', 6), '(空き)')}")


if __name__ == "__main__":
    check_exchange_sync()