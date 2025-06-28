#!/usr/bin/env python3
"""全交流学級の自立活動を包括的に修正"""

import csv
import shutil
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

# 固定科目（変更不可）
FIXED_SUBJECTS = ["欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家", ""]

def get_period_info(index):
    """インデックスから曜日・時限を取得"""
    days = ["月", "火", "水", "木", "金"]
    day = days[index // 6]
    period = (index % 6) + 1
    return day, period, f"{day}{period}"

def analyze_and_fix_all():
    """全交流学級の自立活動を分析・修正"""
    
    # バックアップ作成
    shutil.copy("data/output/output_jiritsu_fixed.csv", "data/output/output_backup_comprehensive.csv")
    
    # CSVを読み込み
    with open("data/output/output_jiritsu_fixed.csv", 'r', encoding='utf-8') as f:
        lines = list(csv.reader(f))
    
    # クラスのインデックスを取得
    class_indices = {}
    for i, row in enumerate(lines):
        if row and row[0]:
            class_indices[row[0]] = i
    
    print("交流学級の自立活動を包括的に修正します\n")
    print("=" * 60)
    
    total_changes = 0
    
    for exchange_class, parent_class in EXCHANGE_PAIRS.items():
        if exchange_class not in class_indices or parent_class not in class_indices:
            print(f"\n{exchange_class}: データが見つかりません")
            continue
        
        idx_exchange = class_indices[exchange_class]
        idx_parent = class_indices[parent_class]
        
        schedule_exchange = lines[idx_exchange][1:31]
        schedule_parent = lines[idx_parent][1:31]
        
        print(f"\n{exchange_class} (親学級: {parent_class})")
        print("-" * 40)
        
        # 現在の自立活動をカウント
        current_jiritsu = []
        violations = []
        
        for i, subj in enumerate(schedule_exchange):
            if subj == "自立":
                day, period, name = get_period_info(i)
                parent_subj = schedule_parent[i]
                is_valid = parent_subj in ["数", "英"]
                current_jiritsu.append({
                    'index': i,
                    'name': name,
                    'parent_subj': parent_subj,
                    'is_valid': is_valid
                })
                if not is_valid:
                    violations.append(current_jiritsu[-1])
        
        required = REQUIRED_JIRITSU[exchange_class]
        current_count = len(current_jiritsu)
        
        print(f"現在の自立活動: {current_count}/{required}")
        
        # 違反を表示
        if violations:
            print(f"違反: {len(violations)}件")
            for v in violations:
                print(f"  {v['name']}: 親学級={v['parent_subj']} (数/英である必要)")
        
        # 修正が必要な場合
        changes_needed = len(violations) + max(0, required - current_count)
        
        if changes_needed > 0:
            # 配置可能なスロットを探す
            valid_slots = []
            for i, parent_subj in enumerate(schedule_parent):
                if parent_subj in ["数", "英"]:
                    exchange_subj = schedule_exchange[i]
                    if exchange_subj not in ["自立"] + FIXED_SUBJECTS:
                        day, period, name = get_period_info(i)
                        valid_slots.append({
                            'index': i,
                            'name': name,
                            'exchange_subj': exchange_subj,
                            'parent_subj': parent_subj
                        })
            
            print(f"\n利用可能なスロット: {len(valid_slots)}個")
            
            # 違反の修正
            slot_idx = 0
            for viol in violations:
                if slot_idx < len(valid_slots):
                    target = valid_slots[slot_idx]
                    
                    # スワップ
                    lines[idx_exchange][viol['index'] + 1] = target['exchange_subj']
                    lines[idx_exchange][target['index'] + 1] = "自立"
                    
                    print(f"  修正: {viol['name']}の自立 → {target['name']}へ移動")
                    slot_idx += 1
                    total_changes += 1
            
            # 不足分の追加
            deficit = required - current_count
            while deficit > 0 and slot_idx < len(valid_slots):
                target = valid_slots[slot_idx]
                
                # 自立活動を配置
                lines[idx_exchange][target['index'] + 1] = "自立"
                
                print(f"  追加: {target['name']}に自立を配置 (元: {target['exchange_subj']})")
                slot_idx += 1
                deficit -= 1
                total_changes += 1
            
            # 最終的な自立活動数を確認
            final_count = lines[idx_exchange][1:31].count("自立")
            print(f"\n修正後の自立活動: {final_count}/{required}")
            
            if final_count < required:
                print(f"  警告: まだ{required - final_count}コマ不足しています")
        else:
            print("修正の必要はありません ✓")
    
    # ファイルに保存
    if total_changes > 0:
        with open("data/output/output_comprehensive_jiritsu_fixed.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(lines)
        
        print(f"\n\n総計: {total_changes}件の修正を実行しました")
        print("出力ファイル: data/output/output_comprehensive_jiritsu_fixed.csv")
    else:
        print("\n\n修正の必要はありませんでした")

if __name__ == "__main__":
    analyze_and_fix_all()