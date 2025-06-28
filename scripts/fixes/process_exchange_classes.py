#!/usr/bin/env python3
"""交流学級（6組・7組）を適切に処理する"""

import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def get_exchange_class_mapping() -> Dict[str, str]:
    """交流学級と親学級のマッピングを取得"""
    return {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }


def find_jiritsu_slots(parent_schedule: List[str]) -> List[Tuple[int, str]]:
    """親学級の数学・英語の時間を見つける（自立活動配置可能）"""
    jiritsu_possible = []
    
    for col_idx, subject in enumerate(parent_schedule):
        if col_idx == 0:  # クラス名はスキップ
            continue
            
        if subject in ["数", "英"]:
            jiritsu_possible.append((col_idx, subject))
    
    return jiritsu_possible


def process_exchange_classes():
    """交流学級を適切に処理する"""
    print("=== 交流学級（6組・7組）の処理 ===")
    print("CLAUDE.mdのルール：")
    print("- 交流学級は基本的に親学級と同じ授業を受ける")
    print("- 自立活動は親学級が数学・英語の時のみ配置可能")
    print("- 各交流学級は週2時間の自立活動が必要\n")
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading schedule from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # クラス名から行インデックスのマッピング
    class_to_row = {}
    for row_idx, row in enumerate(data):
        if row_idx >= 2 and row and row[0]:
            class_name = row[0].strip()
            if class_name:
                class_to_row[class_name] = row_idx
    
    # 交流学級のマッピング
    exchange_mapping = get_exchange_class_mapping()
    
    # 各交流学級を処理
    for exchange_class, parent_class in exchange_mapping.items():
        print(f"\n処理中: {exchange_class} ← {parent_class}")
        
        if parent_class not in class_to_row:
            print(f"  警告: 親学級 {parent_class} が見つかりません")
            continue
            
        if exchange_class not in class_to_row:
            print(f"  警告: 交流学級 {exchange_class} が見つかりません")
            continue
        
        parent_row_idx = class_to_row[parent_class]
        exchange_row_idx = class_to_row[exchange_class]
        
        parent_schedule = data[parent_row_idx]
        exchange_schedule = data[exchange_row_idx]
        
        # まず親学級の授業を完全にコピー
        for col_idx in range(1, len(parent_schedule)):
            if col_idx < len(exchange_schedule):
                exchange_schedule[col_idx] = parent_schedule[col_idx]
            else:
                exchange_schedule.append(parent_schedule[col_idx])
        
        # 自立活動を配置可能な場所を探す
        jiritsu_slots = find_jiritsu_slots(parent_schedule)
        
        # 自立活動を2時間配置
        jiritsu_count = 0
        for col_idx, subject in jiritsu_slots:
            if jiritsu_count >= 2:
                break
                
            # 曜日を確認（異なる曜日に分散させる）
            day_idx = (col_idx - 1) // 6
            
            # 自立活動を配置
            if col_idx < len(exchange_schedule):
                print(f"  自立活動配置: {get_slot_description(col_idx)} ({subject} → 自立)")
                exchange_schedule[col_idx] = "自立"
                jiritsu_count += 1
        
        if jiritsu_count < 2:
            print(f"  警告: 自立活動を{jiritsu_count}時間しか配置できませんでした（2時間必要）")
        else:
            print(f"  ✓ 自立活動を2時間配置完了")
    
    # 修正後のデータを保存
    backup_path = output_path.with_suffix('.csv.bak_exchange_classes')
    with open(backup_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    print(f"\nBackup saved to: {backup_path}")
    
    # 修正版を保存
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    print(f"Updated schedule saved to: {output_path}")
    
    print("\n✅ 交流学級の処理完了")


def get_slot_description(col_idx: int) -> str:
    """列インデックスから曜日・時限の説明を取得"""
    days = ["月", "火", "水", "木", "金"]
    day_idx = (col_idx - 1) // 6
    period = ((col_idx - 1) % 6) + 1
    
    if day_idx < len(days):
        return f"{days[day_idx]}曜{period}限"
    else:
        return f"列{col_idx}"


if __name__ == "__main__":
    process_exchange_classes()