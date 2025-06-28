#!/usr/bin/env python3
"""シンプルな自立活動修正スクリプト"""

import csv
import shutil

def get_period_info(index):
    """インデックスから曜日・時限を取得"""
    days = ["月", "火", "水", "木", "金"]
    day = days[index // 6]
    period = (index % 6) + 1
    return day, period, f"{day}{period}"

def main():
    # バックアップ作成
    shutil.copy("data/output/output.csv", "data/output/output_backup_jiritsu.csv")
    
    # CSVを読み込み
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        lines = list(csv.reader(f))
    
    # 3年6組と3年3組を探す
    idx_3_6 = None
    idx_3_3 = None
    
    for i, row in enumerate(lines):
        if row and row[0] == "3年6組":
            idx_3_6 = i
        elif row and row[0] == "3年3組":
            idx_3_3 = i
    
    if idx_3_6 is None or idx_3_3 is None:
        print("エラー: 必要なクラスが見つかりません")
        return
    
    print("3年6組の自立活動を修正します\n")
    
    # 現在の自立活動の位置を確認
    schedule_3_6 = lines[idx_3_6][1:31]  # 月1〜金6
    schedule_3_3 = lines[idx_3_3][1:31]
    
    jiritsu_positions = []
    for i, subj in enumerate(schedule_3_6):
        if subj == "自立":
            day, period, name = get_period_info(i)
            parent_subj = schedule_3_3[i]
            is_valid = parent_subj in ["数", "英"]
            jiritsu_positions.append({
                'index': i,
                'day': day,
                'period': period,
                'name': name,
                'parent_subj': parent_subj,
                'is_valid': is_valid
            })
            status = "✓" if is_valid else "✗"
            print(f"現在: {name} - 3年6組=自立, 3年3組={parent_subj} {status}")
    
    # 違反している自立活動を探す
    invalid_jiritsu = [j for j in jiritsu_positions if not j['is_valid']]
    
    if not invalid_jiritsu:
        print("\n修正の必要はありません")
        return
    
    # 3年3組が数学または英語の時間を探す
    valid_slots = []
    for i, parent_subj in enumerate(schedule_3_3):
        if parent_subj in ["数", "英"]:
            exchange_subj = schedule_3_6[i]
            # 固定科目でない場合のみ
            if exchange_subj not in ["自立", "欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家", ""]:
                day, period, name = get_period_info(i)
                valid_slots.append({
                    'index': i,
                    'name': name,
                    'exchange_subj': exchange_subj,
                    'parent_subj': parent_subj
                })
    
    print("\n利用可能なスロット:")
    for slot in valid_slots:
        print(f"  {slot['name']}: 3年6組={slot['exchange_subj']}, 3年3組={slot['parent_subj']}")
    
    # 修正実行
    print("\n修正内容:")
    changes_made = 0
    
    for invalid in invalid_jiritsu:
        if changes_made < len(valid_slots):
            # 交換先を選択
            target = valid_slots[changes_made]
            
            # スワップ
            old_subj = lines[idx_3_6][invalid['index'] + 1]
            new_subj = lines[idx_3_6][target['index'] + 1]
            
            lines[idx_3_6][invalid['index'] + 1] = new_subj
            lines[idx_3_6][target['index'] + 1] = "自立"
            
            print(f"  {invalid['name']}: 自立 → {new_subj}")
            print(f"  {target['name']}: {target['exchange_subj']} → 自立")
            
            changes_made += 1
    
    # ファイルに保存
    with open("data/output/output_jiritsu_fixed.csv", 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(lines)
    
    print(f"\n{changes_made}件の修正を実行しました")
    print("出力ファイル: data/output/output_jiritsu_fixed.csv")

if __name__ == "__main__":
    main()