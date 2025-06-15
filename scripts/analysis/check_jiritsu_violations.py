import csv

# Read the timetable
with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    rows = list(reader)

# Read class definitions to get parent-child mappings
jiritsu_rules = {}
with open('data/config/class_definitions.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        if len(row) >= 4 and row[2] == '交流学級':
            class_name = f"{row[0]}年{row[1]}組"
            # Extract parent class from 備考
            if '親学級は' in row[3]:
                parent_class = row[3].replace('親学級は', '').strip()
                jiritsu_rules[class_name] = parent_class

# Check for jiritsu violations
violations = []
days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]

for i, row in enumerate(rows[2:], start=2):  # Skip headers
    class_name = row[0]
    if class_name in jiritsu_rules:
        parent_class = jiritsu_rules[class_name]
        # Find parent class row
        parent_row = None
        parent_row_idx = None
        for j, r in enumerate(rows[2:], start=2):
            if r[0] == parent_class:
                parent_row = r
                parent_row_idx = j
                break
        
        if parent_row:
            # Check each time slot
            for col in range(1, 31):  # 30 time slots
                if col < len(row) and col < len(parent_row):
                    jiritsu_subject = row[col].strip()
                    parent_subject = parent_row[col].strip()
                    
                    # Check if jiritsu has 自立 when parent doesn't
                    if jiritsu_subject == '自立' and parent_subject != '自立' and parent_subject != '' and parent_subject != '欠' and parent_subject != 'YT':
                        day_idx = (col - 1) // 6
                        period = ((col - 1) % 6) + 1
                        day = days[day_idx] if day_idx < len(days) else '?'
                        violations.append({
                            'jiritsu_class': class_name,
                            'parent_class': parent_class,
                            'day': day,
                            'period': period,
                            'jiritsu_subject': jiritsu_subject,
                            'parent_subject': parent_subject,
                            'col': col
                        })

# Print violations
print(f'Found {len(violations)} jiritsu violations:')
for v in violations:
    print(f"  {v['jiritsu_class']} {v['day']}{v['period']}: 自立 (parent {v['parent_class']} has {v['parent_subject']})")

# For each violation, show what other subjects the parent class has
print("\nDetailed analysis of violations:")
for v in violations:
    print(f"\n{v['jiritsu_class']} {v['day']}{v['period']} - parent {v['parent_class']} has {v['parent_subject']}")
    
    # Find parent class row again
    parent_row = None
    for r in rows[2:]:
        if r[0] == v['parent_class']:
            parent_row = r
            break
    
    if parent_row:
        print("  Parent class schedule for potential swaps:")
        for d_idx, d in enumerate(days):
            print(f"    {d}: ", end='')
            for p in range(1, 7):
                col_idx = d_idx * 6 + p
                if col_idx < len(parent_row):
                    subject = parent_row[col_idx].strip()
                    if subject and subject != '欠' and subject != 'YT':
                        print(f"{p}={subject} ", end='')
            print()