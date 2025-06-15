#!/usr/bin/env python3
"""Check gym usage constraint details"""

import csv
from collections import defaultdict

# Read the current timetable
with open('data/output/output.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    periods = next(reader)
    data = list(reader)

# Define exchange class pairs
exchange_pairs = {
    '1年6組': '1年1組',
    '1年7組': '1年2組',
    '2年6組': '2年3組',
    '2年7組': '2年2組',
    '3年6組': '3年3組',
    '3年7組': '3年2組'
}

# Reverse mapping
parent_to_exchange = {v: k for k, v in exchange_pairs.items()}

# Find PE (保) classes for each time slot
print('体育館使用状況（交流学級ペアを考慮）:')
print('='*80)

days = ['月', '火', '水', '木', '金']
periods_per_day = 6
violations = []

for day_idx, day in enumerate(days):
    for period in range(1, 7):
        col_idx = day_idx * periods_per_day + period
        pe_classes = []
        
        for row in data:
            if row[0] and row[col_idx] == '保':
                pe_classes.append(row[0])
        
        if pe_classes:
            # Group PE classes by exchange pairs
            groups = defaultdict(list)
            ungrouped = []
            
            for class_name in pe_classes:
                if class_name in exchange_pairs:
                    # This is an exchange class
                    parent = exchange_pairs[class_name]
                    if parent in pe_classes:
                        groups[f'{class_name}+{parent}'].append(class_name)
                    else:
                        ungrouped.append(class_name)
                elif class_name in parent_to_exchange:
                    # This is a parent class
                    exchange = parent_to_exchange[class_name]
                    if exchange in pe_classes:
                        # Already handled above
                        pass
                    else:
                        ungrouped.append(class_name)
                else:
                    # Regular class (including Grade 5)
                    if '5組' in class_name:
                        groups['Grade5'].append(class_name)
                    else:
                        ungrouped.append(class_name)
            
            # Count groups
            total_groups = len(groups) + len(ungrouped)
            
            print(f'{day}{period}限: {", ".join(pe_classes)}')
            
            if groups:
                print(f'  交流ペア/グループ:')
                for group_name, members in groups.items():
                    print(f'    - {group_name}: {", ".join(members)}')
            
            if ungrouped:
                print(f'  個別クラス: {", ".join(ungrouped)}')
            
            print(f'  => 実質グループ数: {total_groups}')
            
            if total_groups > 1:
                violations.append(f'{day}{period}限: {total_groups}グループが同時使用')
                print(f'  ⚠️ 違反: 複数グループが体育館を同時使用')
            
            print()

if violations:
    print('\n体育館使用制約違反:')
    print('='*80)
    for v in violations:
        print(f'- {v}')