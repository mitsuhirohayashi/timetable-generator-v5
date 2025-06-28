#!/usr/bin/env python3
"""体育館使用制約違反を修正"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def analyze_gym_conflicts():
    """体育館使用の重複を分析"""
    output_path = path_config.output_dir / "output.csv"
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 体育館使用スケジュール: (day, period) -> [(class, row_idx), ...]
    gym_schedule = defaultdict(list)
    
    days = ["月", "火", "水", "木", "金"]
    
    for row_idx, row in enumerate(data):
        if row_idx < 2:  # ヘッダー行をスキップ
            continue
            
        class_name = row[0] if row else ""
        
        # 空白行をスキップ
        if not class_name or class_name.strip() == '':
            continue
        
        # 各時間の科目を確認
        for col_idx in range(1, min(31, len(row))):
            subject = row[col_idx] if col_idx < len(row) else ""
            
            # 保健体育の場合
            if subject == "保":
                # 列番号から曜日と校時を計算
                day_idx = (col_idx - 1) // 6
                period = ((col_idx - 1) % 6) + 1
                
                if day_idx < len(days):
                    day = days[day_idx]
                    gym_schedule[(day, period)].append((class_name, row_idx))
    
    # 重複を検出
    conflicts = []
    for (day, period), classes in gym_schedule.items():
        if len(classes) > 1:
            # 5組の合同授業は除外
            grade5_classes = [c for c, _ in classes if c.endswith("5組")]
            if len(grade5_classes) == len(classes):
                continue
            
            # 交流学級ペアは除外
            exchange_pairs = [
                ("1年1組", "1年6組"),
                ("1年2組", "1年7組"),
                ("2年3組", "2年6組"),
                ("2年2組", "2年7組"),
                ("3年3組", "3年6組"),
                ("3年2組", "3年7組")
            ]
            
            # ペアかどうかチェック
            class_names = [c for c, _ in classes]
            is_pair = False
            for parent, exchange in exchange_pairs:
                if set(class_names) == {parent, exchange}:
                    is_pair = True
                    break
            
            if not is_pair:
                conflicts.append({
                    'day': day,
                    'period': period,
                    'classes': classes
                })
    
    return conflicts


def fix_gym_conflicts():
    """体育館使用制約違反を修正"""
    print("=== 体育館使用制約違反の修正 ===\n")
    
    # 重複を分析
    conflicts = analyze_gym_conflicts()
    
    if not conflicts:
        print("体育館使用制約違反は見つかりませんでした")
        return 0
    
    print(f"体育館使用制約違反を{len(conflicts)}件検出しました")
    
    # 現在のoutput.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # 修正件数
    fixed_count = 0
    
    # 各重複を修正
    for conflict in conflicts[:5]:  # 最初の5件のみ修正
        day = conflict['day']
        period = conflict['period']
        classes = conflict['classes']
        
        print(f"\n■ {day}曜{period}限の体育館使用重複:")
        print(f"  対象クラス: {', '.join([c for c, _ in classes])}")
        
        # 列インデックスを計算
        day_idx = ["月", "火", "水", "木", "金"].index(day)
        col_idx = day_idx * 6 + period
        
        # 最初のクラス以外を別の科目に変更
        for i, (class_name, row_idx) in enumerate(classes[1:], 1):
            # その日の使用済み科目を確認
            used_subjects = []
            for p in range(1, 7):
                col = day_idx * 6 + p
                if col < len(data[row_idx]):
                    used_subjects.append(data[row_idx][col])
            
            # 使用可能な科目を探す（保健体育以外）
            available = ["国", "社", "数", "理", "英", "音", "美", "技", "家"]
            available = [s for s in available if s not in used_subjects]
            
            if available:
                new_subject = available[0]
                print(f"  修正: {class_name}の保 → {new_subject}")
                data[row_idx][col_idx] = new_subject
                fixed_count += 1
                
                # 交流学級がある場合は同期
                exchange_map = {
                    "1年1組": "1年6組", "1年6組": "1年1組",
                    "1年2組": "1年7組", "1年7組": "1年2組",
                    "2年3組": "2年6組", "2年6組": "2年3組",
                    "2年2組": "2年7組", "2年7組": "2年2組",
                    "3年3組": "3年6組", "3年6組": "3年3組",
                    "3年2組": "3年7組", "3年7組": "3年2組"
                }
                
                if class_name in exchange_map:
                    exchange_class = exchange_map[class_name]
                    # 交流学級の行を探す
                    for ex_idx, ex_row in enumerate(data):
                        if ex_idx >= 2 and ex_row and ex_row[0] == exchange_class:
                            data[ex_idx][col_idx] = new_subject
                            print(f"  同期: {exchange_class}も{new_subject}に変更")
                            break
    
    # 修正後のデータを保存
    if fixed_count > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_gym')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nFixed {fixed_count} gym conflicts")
        print(f"Updated schedule saved to: {output_path}")
    
    return fixed_count


if __name__ == "__main__":
    fixed_count = fix_gym_conflicts()
    print(f"\nTotal conflicts fixed: {fixed_count}")
    print("\n制約違反チェックを再実行してください:")
    print("  python3 check_violations.py")