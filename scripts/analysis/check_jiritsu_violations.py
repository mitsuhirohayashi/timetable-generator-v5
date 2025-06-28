import csv

# 交流学級と親学級の対応関係
exchange_pairs = {
    '1年6組': '1年1組',
    '1年7組': '1年2組',
    '2年6組': '2年3組',
    '2年7組': '2年2組',
    '3年6組': '3年3組',
    '3年7組': '3年2組'
}

# CSVファイルを読み込む
with open('data/output/output.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    data = list(reader)

# クラス名と行番号のマッピングを作成
class_row_map = {}
for i, row in enumerate(data):
    if row and row[0]:
        class_name = row[0]
        if class_name != '基本時間割' and class_name != '':
            class_row_map[class_name] = i

# 曜日と時限のマッピング
days = ['月', '火', '水', '木', '金']
periods = [1, 2, 3, 4, 5, 6]

# 違反をチェック
violations = []
jiritsu_count = 0

for exchange_class, parent_class in exchange_pairs.items():
    if exchange_class in class_row_map and parent_class in class_row_map:
        exchange_row = class_row_map[exchange_class]
        parent_row = class_row_map[parent_class]
        
        # 各時限をチェック
        for col_idx in range(1, 31):  # 1-30列（月1から金6まで）
            exchange_subject = data[exchange_row][col_idx]
            
            if exchange_subject == '自立':
                jiritsu_count += 1
                parent_subject = data[parent_row][col_idx]
                
                # 曜日と時限を計算
                day_idx = (col_idx - 1) // 6
                period_idx = (col_idx - 1) % 6
                day = days[day_idx]
                period = periods[period_idx]
                
                # 親学級が数学・英語以外の場合は違反
                if parent_subject not in ['数', '英']:
                    violations.append({
                        'exchange_class': exchange_class,
                        'parent_class': parent_class,
                        'day': day,
                        'period': period,
                        'parent_subject': parent_subject
                    })
                    print(f'違反: {exchange_class}が自立活動の{day}曜{period}限、{parent_class}は「{parent_subject}」（数学・英語以外）')
                else:
                    print(f'OK: {exchange_class}が自立活動の{day}曜{period}限、{parent_class}は「{parent_subject}」')

print(f'\n=== 集計結果 ===')
print(f'自立活動の総数: {jiritsu_count}')
print(f'違反数: {len(violations)}')

if violations:
    print('\n=== 違反詳細 ===')
    for v in violations:
        print(f'{v["exchange_class"]} ({v["day"]}{v["period"]}限) - 親学級{v["parent_class"]}が「{v["parent_subject"]}」')