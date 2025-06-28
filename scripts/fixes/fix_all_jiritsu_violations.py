#!/usr/bin/env python3
"""全ての交流学級の自立活動違反を修正するスクリプト"""

import csv
import sys
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

# 各交流学級の必要な自立活動時間数
REQUIRED_JIRITSU = {
    "1年6組": 2,
    "1年7組": 2,
    "2年6組": 2,
    "2年7組": 2,
    "3年6組": 2,
    "3年7組": 2
}

def get_period_name(index):
    """インデックスから曜日・時限を取得"""
    days = ["月", "火", "水", "木", "金"]
    day = days[index // 6]
    period = (index % 6) + 1
    return f"{day}{period}"

def load_schedule(filename):
    """時間割を読み込む"""
    schedule = {}
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        # ヘッダー行もスキップ（"基本時間割"など）
        next(reader)
        
        for row in reader:
            if len(row) >= 31 and row[0]:  # 修正: 31列以上
                class_name = row[0]
                # デバッグ: クラス名を確認
                if "6組" in class_name or "7組" in class_name:
                    print(f"DEBUG: Found exchange class: '{class_name}'")
                # row[1:]から30個取る（月1〜金6）
                schedule[class_name] = row[1:31] if len(row) >= 31 else row[1:]
    
    # 元のファイルの全内容も保持
    with open(filename, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
    
    return schedule, headers, all_lines

def analyze_jiritsu_violations(schedule):
    """自立活動の違反をチェック"""
    violations = {}
    current_jiritsu = {}
    
    # デバッグ: scheduleのキーを確認
    print(f"DEBUG: Schedule keys: {list(schedule.keys())[:5]}...")
    
    for exchange_class, parent_class in EXCHANGE_PAIRS.items():
        # キーの存在を別の方法でチェック
        exchange_found = any(exchange_class in key for key in schedule.keys())
        parent_found = any(parent_class in key for key in schedule.keys())
        
        if not exchange_found or not parent_found:
            print(f"警告: {exchange_class}または{parent_class}のデータが見つかりません")
            continue
        
        # 正確なキーを見つける
        exchange_key = next((k for k in schedule.keys() if exchange_class in k), None)
        parent_key = next((k for k in schedule.keys() if parent_class in k), None)
        
        if not exchange_key or not parent_key:
            continue
        
        exchange_schedule = schedule[exchange_key]
        parent_schedule = schedule[parent_key]
        
        violations[exchange_class] = []
        current_jiritsu[exchange_class] = 0
        
        # 現在の自立活動をチェック
        for i, subj in enumerate(exchange_schedule):
            if subj == "自立":
                current_jiritsu[exchange_class] += 1
                parent_subj = parent_schedule[i]
                if parent_subj not in ["数", "英"]:
                    violations[exchange_class].append({
                        'index': i,
                        'period': get_period_name(i),
                        'parent_subj': parent_subj
                    })
    
    return violations, current_jiritsu

def find_replacement_opportunities(schedule, exchange_class, parent_class):
    """交換可能な時間帯を探す"""
    opportunities = []
    
    if exchange_class not in schedule or parent_class not in schedule:
        return opportunities
    
    exchange_schedule = schedule[exchange_class]
    parent_schedule = schedule[parent_class]
    
    for i, parent_subj in enumerate(parent_schedule):
        if parent_subj in ["数", "英"]:
            exchange_subj = exchange_schedule[i]
            # 固定科目でない、かつ自立でない場合のみ交換可能
            if exchange_subj not in ["自立", "欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家", ""]:
                opportunities.append({
                    'index': i,
                    'period': get_period_name(i),
                    'exchange_subj': exchange_subj,
                    'parent_subj': parent_subj
                })
    
    return opportunities

def fix_jiritsu_activities(input_file, output_file):
    """自立活動の違反を修正"""
    schedule, headers, all_lines = load_schedule(input_file)
    
    print("交流学級の自立活動違反を分析中...\n")
    
    violations, current_jiritsu = analyze_jiritsu_violations(schedule)
    
    all_changes = []
    
    for exchange_class in EXCHANGE_PAIRS:
        if exchange_class not in schedule:
            continue
        
        parent_class = EXCHANGE_PAIRS[exchange_class]
        required = REQUIRED_JIRITSU[exchange_class]
        current = current_jiritsu.get(exchange_class, 0)
        exchange_violations = violations.get(exchange_class, [])
        
        print(f"{exchange_class} (親学級: {parent_class})")
        print(f"  現在の自立活動: {current}/{required}")
        
        if exchange_violations:
            print(f"  違反: {len(exchange_violations)}件")
            
            # 違反している自立活動と交換可能な時間帯を探す
            opportunities = find_replacement_opportunities(schedule, exchange_class, parent_class)
            
            # 違反と機会をペアリング
            for viol in exchange_violations:
                if opportunities:
                    # 最適な交換先を選ぶ
                    best_opp = opportunities.pop(0)
                    
                    print(f"    {viol['period']}: 自立 → {schedule[exchange_class][viol['index']]}")
                    print(f"    {best_opp['period']}: {best_opp['exchange_subj']} → 自立")
                    
                    # 変更を記録
                    all_changes.append({
                        'class': exchange_class,
                        'change1': {
                            'index': viol['index'],
                            'old': "自立",
                            'new': best_opp['exchange_subj']
                        },
                        'change2': {
                            'index': best_opp['index'],
                            'old': best_opp['exchange_subj'],
                            'new': "自立"
                        }
                    })
        
        # 不足分を追加
        deficit = required - current
        if deficit > 0:
            print(f"  不足: {deficit}コマ")
            opportunities = find_replacement_opportunities(schedule, exchange_class, parent_class)
            
            for i in range(min(deficit, len(opportunities))):
                opp = opportunities[i]
                print(f"    {opp['period']}: {opp['exchange_subj']} → 自立 (親={opp['parent_subj']})")
                
                all_changes.append({
                    'class': exchange_class,
                    'change1': {
                        'index': opp['index'],
                        'old': opp['exchange_subj'],
                        'new': "自立"
                    }
                })
        
        print()
    
    if all_changes:
        print(f"\n{len(all_changes)}件の変更を適用中...")
        
        # 変更を適用
        for change in all_changes:
            class_name = change['class']
            
            # change1を適用
            c1 = change['change1']
            schedule[class_name][c1['index']] = c1['new']
            
            # change2があれば適用
            if 'change2' in change:
                c2 = change['change2']
                schedule[class_name][c2['index']] = c2['new']
        
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
                        class_name = row[0].strip('"')
                        if class_name in schedule:
                            # 更新されたスケジュールを使用
                            new_row = [row[0], row[1]] + [f'"{s}"' for s in schedule[class_name]] + row[32:]
                            writer.writerow(new_row)
                        else:
                            writer.writerow(row)
                    else:
                        writer.writerow(row)
        
        print(f"\n修正完了: {output_file}")
        
        # 修正後の検証
        print("\n修正後の検証:")
        new_schedule, _, _ = load_schedule(output_file)
        new_violations, new_current = analyze_jiritsu_violations(new_schedule)
        
        for exchange_class in EXCHANGE_PAIRS:
            if exchange_class in new_current:
                required = REQUIRED_JIRITSU[exchange_class]
                current = new_current[exchange_class]
                viol_count = len(new_violations.get(exchange_class, []))
                status = "✓" if current == required and viol_count == 0 else "✗"
                print(f"  {exchange_class}: {current}/{required} (違反: {viol_count}) {status}")
    else:
        print("\n修正は必要ありません")

if __name__ == "__main__":
    input_file = "data/output/output.csv"
    output_file = "data/output/output_jiritsu_fixed.csv"
    
    fix_jiritsu_activities(input_file, output_file)