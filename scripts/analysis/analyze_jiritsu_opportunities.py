#!/usr/bin/env python3
"""交流学級の自立活動配置可能性を分析"""

import csv
from collections import defaultdict

# 交流学級と親学級の対応
EXCHANGE_PAIRS = {
    "1年6組": "1年1組",
    "1年7組": "1年2組", 
    "2年6組": "2年3組",
    "2年7組": "2年2組",
    "3年6組": "3年3組",
    "3年7組": "3年2組"
}

def get_period_name(index):
    """インデックスから曜日・時限を取得"""
    days = ["月", "火", "水", "木", "金"]
    day = days[index // 6]
    period = (index % 6) + 1
    return f"{day}{period}"

def analyze_schedule(filename):
    """時間割を分析"""
    schedule = {}
    
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            if len(row) > 32:
                class_name = row[0].strip('"')
                schedule[class_name] = [s.strip('"') for s in row[2:32]]  # 月1から金6まで
    
    print("交流学級の自立活動配置分析\n")
    print("=" * 80)
    
    for exchange_class, parent_class in EXCHANGE_PAIRS.items():
        print(f"\n{exchange_class} (親学級: {parent_class})")
        print("-" * 40)
        
        if exchange_class not in schedule:
            print(f"  警告: {exchange_class}のデータが見つかりません")
            continue
            
        if parent_class not in schedule:
            print(f"  警告: {parent_class}のデータが見つかりません")
            continue
        
        exchange_schedule = schedule[exchange_class]
        parent_schedule = schedule[parent_class]
        
        # 現在の自立活動をカウント
        current_jiritsu = exchange_schedule.count("自立")
        print(f"  現在の自立活動: {current_jiritsu}コマ")
        
        # 現在の自立活動の位置を表示
        for i, subj in enumerate(exchange_schedule):
            if subj == "自立":
                period = get_period_name(i)
                parent_subj = parent_schedule[i]
                print(f"    {period}: 親学級={parent_subj}")
        
        # 親学級が数/英の時間を探す
        print(f"\n  配置可能な時間帯 (親学級が数/英):")
        opportunities = []
        for i, parent_subj in enumerate(parent_schedule):
            if parent_subj in ["数", "英"]:
                period = get_period_name(i)
                exchange_subj = exchange_schedule[i]
                if exchange_subj != "自立":
                    opportunities.append((period, exchange_subj, parent_subj))
                    print(f"    {period}: 交流={exchange_subj}, 親={parent_subj}")
        
        if not opportunities:
            print("    なし")
        
        print(f"\n  配置可能な時間帯数: {len(opportunities)}")

if __name__ == "__main__":
    analyze_schedule("data/output/output.csv")