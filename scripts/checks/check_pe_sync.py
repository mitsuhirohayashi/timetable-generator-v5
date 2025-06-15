#!/usr/bin/env python3
"""Check PE synchronization between exchange class pairs"""

import csv

# Read the current timetable
with open('data/output/output.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    periods = next(reader)
    data = list(reader)

# Define exchange class pairs
exchange_pairs = [
    ('1年6組', '1年1組'),
    ('1年7組', '1年2組'),
    ('2年6組', '2年3組'),
    ('2年7組', '2年2組'),
    ('3年6組', '3年3組'),
    ('3年7組', '3年2組')
]

# Find PE (保) classes for each time slot
print('体育（保）の授業時間:')
print('='*80)

days = ['月', '火', '水', '木', '金']
periods_per_day = 6

for day_idx, day in enumerate(days):
    for period in range(1, 7):
        col_idx = day_idx * periods_per_day + period
        pe_classes = []
        
        for row in data:
            if row[0] and row[col_idx] == '保':
                pe_classes.append(row[0])
        
        if pe_classes:
            pe_list = ', '.join(pe_classes)
            print(f'{day}{period}限: {pe_list}')
            
            # Check if exchange pairs are synchronized
            for exchange, parent in exchange_pairs:
                if exchange in pe_classes or parent in pe_classes:
                    exchange_has_pe = exchange in pe_classes
                    parent_has_pe = parent in pe_classes
                    if exchange_has_pe != parent_has_pe:
                        print(f'  ⚠️ 非同期: {exchange}={exchange_has_pe}, {parent}={parent_has_pe}')

print()
print('交流学級ペアの体育同期状況:')
print('='*80)

# Check synchronization for each exchange pair
for exchange, parent in exchange_pairs:
    print(f'\n{exchange} ↔ {parent}:')
    
    # Find row indices
    exchange_idx = None
    parent_idx = None
    for i, row in enumerate(data):
        if row[0] == exchange:
            exchange_idx = i
        elif row[0] == parent:
            parent_idx = i
    
    if exchange_idx is None or parent_idx is None:
        continue
    
    # Check each time slot
    for day_idx, day in enumerate(days):
        for period in range(1, 7):
            col_idx = day_idx * periods_per_day + period
            
            exchange_subject = data[exchange_idx][col_idx] if exchange_idx < len(data) else ''
            parent_subject = data[parent_idx][col_idx] if parent_idx < len(data) else ''
            
            # Check if subjects match (excluding jiritsu activities)
            jiritsu_subjects = ['自立', '日生', '生単', '作業']
            
            if exchange_subject in jiritsu_subjects:
                continue  # Skip jiritsu activities
            
            if exchange_subject != parent_subject:
                print(f'  {day}{period}限: {exchange}={exchange_subject}, {parent}={parent_subject} ❌')
            elif exchange_subject == '保':
                print(f'  {day}{period}限: 体育同期 ✓')