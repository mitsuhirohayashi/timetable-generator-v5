#!/usr/bin/env python3
"""体育館使用違反の詳細分析スクリプト"""
import csv
import sys
from pathlib import Path
from collections import defaultdict

# プロジェクトのルートディレクトリをsys.pathに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 交流学級ペアの定義
EXCHANGE_PAIRS = {
    "1年6組": "1年1組",
    "1年7組": "1年2組", 
    "2年6組": "2年3組",
    "2年7組": "2年2組",
    "3年6組": "3年3組",
    "3年7組": "3年2組",
}

# 5組（合同授業）
GRADE5_CLASSES = ["1年5組", "2年5組", "3年5組"]

def load_timetable(file_path):
    """時間割CSVを読み込む"""
    timetable = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行
        period_row = next(reader)  # 時限行
        
        for row in reader:
            if not row[0] or row[0].strip() == "":
                continue
                
            class_name = row[0]
            timetable[class_name] = row[1:]
    
    return timetable

def analyze_pe_slots(timetable):
    """体育の時間帯を分析"""
    pe_slots = defaultdict(list)  # {(day, period): [classes]}
    days = ["月", "火", "水", "木", "金"]
    
    for class_name, schedule in timetable.items():
        for i, subject in enumerate(schedule):
            if subject == "保":
                day_idx = i // 6
                period = (i % 6) + 1
                day = days[day_idx]
                pe_slots[(day, period)].append(class_name)
    
    return pe_slots

def is_valid_pe_group(classes):
    """体育のグループが有効かチェック"""
    # 1グループのみの場合は有効
    if len(classes) <= 1:
        return True, "1グループのみ"
    
    # 5組の合同授業チェック
    if all(c in GRADE5_CLASSES for c in classes):
        return True, "5組合同授業"
    
    # 交流学級ペアチェック
    if len(classes) == 2:
        c1, c2 = classes
        if (c1 in EXCHANGE_PAIRS and EXCHANGE_PAIRS[c1] == c2) or \
           (c2 in EXCHANGE_PAIRS and EXCHANGE_PAIRS[c2] == c1):
            return True, f"交流学級ペア（{c1} + {c2}）"
    
    return False, "複数の独立したグループ"

def main():
    """メイン処理"""
    input_file = project_root / "data" / "output" / "output.csv"
    
    print("=== 体育館使用状況の詳細分析 ===\n")
    
    # 時間割を読み込む
    timetable = load_timetable(input_file)
    
    # 体育の時間帯を分析
    pe_slots = analyze_pe_slots(timetable)
    
    violations = []
    valid_groups = []
    
    # 各時間帯をチェック
    for (day, period), classes in sorted(pe_slots.items()):
        is_valid, reason = is_valid_pe_group(classes)
        
        if is_valid:
            valid_groups.append({
                'day': day,
                'period': period,
                'classes': classes,
                'reason': reason
            })
        else:
            violations.append({
                'day': day,
                'period': period,
                'classes': classes,
                'reason': reason
            })
    
    # 結果を表示
    print("【正常な体育実施】")
    for group in valid_groups:
        print(f"  {group['day']}{group['period']}時限: {', '.join(group['classes'])} - {group['reason']}")
    
    print(f"\n【体育館使用違反】({len(violations)}件)")
    for violation in violations:
        print(f"  ❌ {violation['day']}{violation['period']}時限: {', '.join(violation['classes'])} - {violation['reason']}")
        
        # 詳細分析
        for c in violation['classes']:
            if c in EXCHANGE_PAIRS:
                pair = EXCHANGE_PAIRS[c]
                if pair in violation['classes']:
                    print(f"     ※ {c}と{pair}は交流学級ペアです（正常）")
                else:
                    print(f"     ※ {c}の交流ペア{pair}が含まれていません")
    
    print("\n【交流学級ペアの体育同期状況】")
    for exchange, parent in EXCHANGE_PAIRS.items():
        if exchange in timetable and parent in timetable:
            exchange_pe = []
            parent_pe = []
            
            for i, (e_subj, p_subj) in enumerate(zip(timetable[exchange], timetable[parent])):
                day_idx = i // 6
                period = (i % 6) + 1
                day = ["月", "火", "水", "木", "金"][day_idx]
                
                if e_subj == "保":
                    exchange_pe.append(f"{day}{period}")
                if p_subj == "保":
                    parent_pe.append(f"{day}{period}")
            
            if set(exchange_pe) == set(parent_pe):
                print(f"  ✓ {exchange} & {parent}: 完全同期")
            else:
                print(f"  ❌ {exchange} & {parent}: 不同期")
                print(f"     {exchange}: {', '.join(exchange_pe)}")
                print(f"     {parent}: {', '.join(parent_pe)}")

if __name__ == "__main__":
    main()