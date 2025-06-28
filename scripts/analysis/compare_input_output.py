#!/usr/bin/env python3
"""input.csvとoutput.csvの詳細比較"""

import csv
from typing import List, Dict, Tuple

def read_csv(filepath: str) -> List[List[str]]:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return list(csv.reader(f))

def get_time_slot_name(col_idx: int) -> str:
    """列番号から時間枠名を取得"""
    days = ['月', '火', '水', '木', '金']
    day_idx = (col_idx - 1) // 6
    period = ((col_idx - 1) % 6) + 1
    if day_idx < len(days):
        return f'{days[day_idx]}曜{period}限'
    return f'列{col_idx}'

def main():
    # ファイルを読み込み
    input_data = read_csv('/Users/hayashimitsuhiro/Desktop/timetable_v5/data/input/input.csv')
    output_data = read_csv('/Users/hayashimitsuhiro/Desktop/timetable_v5/data/output/output.csv')

    print('=== input.csv と output.csv の詳細比較 ===\n')

    # 基本情報
    print('【基本情報】')
    print(f'入力ファイル: {len(input_data)}行 x {len(input_data[0]) if input_data else 0}列')
    print(f'出力ファイル: {len(output_data)}行 x {len(output_data[0]) if output_data else 0}列')
    print()

    # 配置禁止制約の確認
    print('【配置禁止制約（非保・非数・非理）の適用状況】')
    forbidden_count = 0
    applied_count = 0
    violations = []

    for row_idx in range(2, min(len(input_data), len(output_data))):
        if row_idx >= len(input_data) or row_idx >= len(output_data):
            continue
        
        input_row = input_data[row_idx]
        output_row = output_data[row_idx]
        
        if not input_row or not input_row[0]:
            continue
            
        class_name = input_row[0].strip()
        
        for col_idx in range(1, min(len(input_row), len(output_row))):
            input_val = input_row[col_idx].strip() if col_idx < len(input_row) else ''
            output_val = output_row[col_idx].strip() if col_idx < len(output_row) else ''
            
            # 配置禁止の確認
            if input_val.startswith('非'):
                forbidden_count += 1
                forbidden_subject = input_val[1:]
                time_slot = get_time_slot_name(col_idx)
                
                if output_val == forbidden_subject:
                    print(f'❌ 違反: {class_name} {time_slot} - 非{forbidden_subject}なのに{forbidden_subject}が配置')
                    violations.append((class_name, time_slot, forbidden_subject))
                else:
                    print(f'✅ OK: {class_name} {time_slot} - 非{forbidden_subject} → {output_val or "空き"}')
                    applied_count += 1

    print(f'\n配置禁止制約: {forbidden_count}件中 {applied_count}件適用')
    if violations:
        print(f'⚠️  違反: {len(violations)}件')
    print()

    # 変更点の分析
    print('【変更点の詳細分析】')
    changes = []
    fixed_subjects = ['YT', '道', '日生', '自立', '作業', '生単']

    for row_idx in range(2, min(len(input_data), len(output_data))):
        input_row = input_data[row_idx]
        output_row = output_data[row_idx]
        
        if not input_row or not input_row[0]:
            continue
            
        class_name = input_row[0].strip()
        
        for col_idx in range(1, min(len(input_row), len(output_row))):
            input_val = input_row[col_idx].strip() if col_idx < len(input_row) else ''
            output_val = output_row[col_idx].strip() if col_idx < len(output_row) else ''
            
            # 変更があった場合
            if input_val != output_val:
                time_slot = get_time_slot_name(col_idx)
                
                if input_val.startswith('非'):
                    change_type = '配置禁止適用'
                elif not input_val and output_val:
                    change_type = '空きスロット埋め'
                elif input_val and not output_val:
                    change_type = '授業削除'
                else:
                    change_type = '授業変更'
                
                changes.append({
                    'class': class_name,
                    'time': time_slot,
                    'from': input_val,
                    'to': output_val,
                    'type': change_type
                })

    # 変更種別ごとに集計
    change_types = {}
    for change in changes:
        t = change['type']
        if t not in change_types:
            change_types[t] = []
        change_types[t].append(change)

    # 結果表示
    for change_type, items in sorted(change_types.items()):
        print(f'\n{change_type}: {len(items)}件')
        for i, item in enumerate(items[:5]):  # 最初の5件を表示
            from_str = item["from"] if item["from"] else "空き"
            to_str = item["to"] if item["to"] else "空き"
            print(f'  {item["class"]} {item["time"]}: {from_str} → {to_str}')
        if len(items) > 5:
            print(f'  ... 他 {len(items) - 5} 件')

    # 固定科目の保護確認
    print('\n【固定科目の保護確認】')
    fixed_violations = []
    
    for row_idx in range(2, min(len(input_data), len(output_data))):
        input_row = input_data[row_idx]
        output_row = output_data[row_idx]
        
        if not input_row or not input_row[0]:
            continue
            
        class_name = input_row[0].strip()
        
        for col_idx in range(1, min(len(input_row), len(output_row))):
            input_val = input_row[col_idx].strip() if col_idx < len(input_row) else ''
            output_val = output_row[col_idx].strip() if col_idx < len(output_row) else ''
            
            # 固定科目が変更されていないか確認
            if input_val in fixed_subjects and input_val != output_val:
                time_slot = get_time_slot_name(col_idx)
                fixed_violations.append((class_name, time_slot, input_val, output_val))

    if fixed_violations:
        print('❌ 固定科目が変更されています:')
        for class_name, time_slot, from_val, to_val in fixed_violations:
            print(f'  {class_name} {time_slot}: {from_val} → {to_val}')
    else:
        print('✅ すべての固定科目（YT、道、日生、自立等）が保護されています')

    # 空きスロットの統計
    print('\n【空きスロットの統計】')
    input_empty = 0
    output_empty = 0
    
    for row_idx in range(2, len(input_data)):
        if row_idx >= len(output_data):
            break
            
        input_row = input_data[row_idx]
        output_row = output_data[row_idx]
        
        if not input_row or not input_row[0]:
            continue
        
        for col_idx in range(1, 31):  # 月〜金の6時限
            input_val = input_row[col_idx].strip() if col_idx < len(input_row) else ''
            output_val = output_row[col_idx].strip() if col_idx < len(output_row) else ''
            
            if not input_val or input_val.startswith('非'):
                input_empty += 1
            if not output_val:
                output_empty += 1
    
    print(f'入力の空きスロット: {input_empty}個')
    print(f'出力の空きスロット: {output_empty}個')
    print(f'埋められたスロット: {input_empty - output_empty}個')

if __name__ == "__main__":
    main()