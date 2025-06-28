#!/usr/bin/env python3
"""交流学級の不足している自立活動を修正するスクリプト"""

import csv
import sys
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

# 交流学級と親学級の対応
EXCHANGE_PAIRS = {
    "1年6組": "1年1組",
    "1年7組": "1年2組", 
    "2年6組": "2年3組",
    "2年7組": "2年2組",
    "3年6組": "3年3組",
    "3年7組": "3年2組"
}

# 各交流学級の必要な自立活動時間数
REQUIRED_JIRITSU = {
    "1年6組": 2,
    "1年7組": 2,
    "2年6組": 2,
    "2年7組": 2,
    "3年6組": 2,
    "3年7組": 2
}

def load_schedule(filename):
    """時間割を読み込む"""
    schedule = {}
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            if len(row) > 32:
                class_name = row[0].strip('"')  # Remove quotes
                schedule[class_name] = [s.strip('"') for s in row[2:32]]  # 月1から金6まで
    return schedule, headers

def count_jiritsu(schedule, class_name):
    """指定クラスの自立活動数をカウント"""
    if class_name not in schedule:
        return 0
    return schedule[class_name].count("自立")

def find_suitable_slots(schedule, exchange_class, parent_class):
    """親学級が数学または英語の時間帯を探す"""
    suitable = []
    if parent_class not in schedule:
        return suitable
    
    parent_schedule = schedule[parent_class]
    exchange_schedule = schedule.get(exchange_class, [""] * 30)
    
    for i, subject in enumerate(parent_schedule):
        if subject in ["数", "英"]:
            # 交流学級がその時間に自立活動以外の科目を持っているかチェック
            exchange_subject = exchange_schedule[i] if i < len(exchange_schedule) else ""
            if exchange_subject and exchange_subject != "自立":
                suitable.append((i, exchange_subject, subject))
    
    return suitable

def get_period_name(index):
    """インデックスから曜日・時限を取得"""
    days = ["月", "火", "水", "木", "金"]
    day = days[index // 6]
    period = (index % 6) + 1
    return f"{day}{period}"

def fix_jiritsu_activities(input_file, output_file):
    """不足している自立活動を修正"""
    schedule, headers = load_schedule(input_file)
    
    logging.info("交流学級の自立活動をチェック中...\n")
    
    changes = []
    
    for exchange_class, parent_class in EXCHANGE_PAIRS.items():
        current_jiritsu = count_jiritsu(schedule, exchange_class)
        required = REQUIRED_JIRITSU[exchange_class]
        
        if current_jiritsu < required:
            deficit = required - current_jiritsu
            logging.info(f"{exchange_class}: {current_jiritsu}/{required} (不足: {deficit})")
            
            # 親学級が数/英の時間帯を探す
            suitable_slots = find_suitable_slots(schedule, exchange_class, parent_class)
            
            if suitable_slots:
                logging.info(f"  親学級({parent_class})が数/英の時間帯:")
                for idx, (slot_idx, exchange_subj, parent_subj) in enumerate(suitable_slots[:deficit]):
                    period = get_period_name(slot_idx)
                    logging.info(f"    {period}: {exchange_class}={exchange_subj} → 自立 (親学級={parent_subj})")
                    
                    # 変更を記録
                    changes.append({
                        'class': exchange_class,
                        'period_idx': slot_idx,
                        'old_subject': exchange_subj,
                        'new_subject': '自立'
                    })
            else:
                logging.info(f"  警告: 適切な時間帯が見つかりません")
        else:
            logging.info(f"{exchange_class}: {current_jiritsu}/{required} ✓")
    
    if changes:
        logging.info(f"\n{len(changes)}件の変更を適用します...")
        
        # 変更を適用
        for change in changes:
            class_name = change['class']
            period_idx = change['period_idx']
            if class_name in schedule:
                schedule[class_name][period_idx] = change['new_subject']
        
        # ファイルに保存
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            # 元のファイルの順序を保持
            with open(input_file, 'r', encoding='utf-8') as orig:
                orig_reader = csv.reader(orig)
                next(orig_reader)  # ヘッダーをスキップ
                for row in orig_reader:
                    if len(row) > 32:
                        class_name = row[0]
                        if class_name in schedule:
                            new_row = row[:2] + schedule[class_name] + row[32:]
                            writer.writerow(new_row)
                        else:
                            writer.writerow(row)
        
        logging.info(f"\n修正完了: {output_file}")
    else:
        logging.info("\n修正は必要ありません")

if __name__ == "__main__":
    input_file = "data/output/output.csv"
    output_file = "data/output/output_fixed_jiritsu.csv"
    
    fix_jiritsu_activities(input_file, output_file)