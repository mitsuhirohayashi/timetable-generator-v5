#!/usr/bin/env python3
"""
CSV分析スクリプト - 交流学級同期チェック
画像で示された赤いハイライト部分（特に3年6組・3年7組）の問題を分析
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import not needed for this simple analysis

def load_schedule_from_csv(file_path):
    """CSVファイルから時間割を読み込む"""
    schedule_data = {}
    all_rows = []  # デバッグ用
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # 曜日・時限のヘッダー
        next(reader)  # 時限番号の行
        
        row_count = 2  # ヘッダー2行をスキップしたので3行目から
        for row in reader:
            row_count += 1
            
            # 全ての行を記録（デバッグ用）
            if row and len(row) > 1:
                all_rows.append({
                    'row_number': row_count,
                    'class_name': row[0].strip() if row[0] else '(空)',
                    'first_subjects': row[1:7] if len(row) >= 7 else row[1:]
                })
            
            if not row or (not row[0] and all(not cell for cell in row)):  # 完全な空行はスキップ
                continue
                
            class_name = row[0].strip() if row[0] else ''
            if class_name and class_name != '':
                schedule_data[class_name] = {
                    'row_number': row_count,
                    'schedule': row[1:31] if len(row) >= 31 else row[1:]  # 月1〜金6の30コマ
                }
            elif len(row) > 1 and any(cell for cell in row[1:]):  # クラス名なしでデータがある行
                schedule_data[f'(無名行{row_count})'] = {
                    'row_number': row_count,
                    'schedule': row[1:31] if len(row) >= 31 else row[1:],
                    'is_unnamed': True
                }
    
    return schedule_data, all_rows

def get_time_slot_info(day_idx, period_idx):
    """インデックスから曜日・時限を取得"""
    days = ['月', '火', '水', '木', '金']
    slot_idx = day_idx * 6 + period_idx
    day = days[slot_idx // 6]
    period = (slot_idx % 6) + 1
    return f"{day}{period}"

def check_exchange_class_sync(schedule_data):
    """交流学級と親学級の同期をチェック"""
    # 交流学級と親学級のペア
    exchange_pairs = [
        ('1年6組', '1年1組'),
        ('1年7組', '1年2組'),
        ('2年6組', '2年3組'),
        ('2年7組', '2年2組'),
        ('3年6組', '3年3組'),
        ('3年7組', '3年2組')
    ]
    
    mismatches = []
    all_comparisons = []  # デバッグ用
    
    for exchange_class, parent_class in exchange_pairs:
        if exchange_class not in schedule_data or parent_class not in schedule_data:
            print(f"⚠️  {exchange_class} または {parent_class} がCSVに存在しません")
            continue
            
        exchange_schedule = schedule_data[exchange_class]['schedule']
        parent_schedule = schedule_data[parent_class]['schedule']
        
        # 各時限をチェック
        for i in range(min(len(exchange_schedule), len(parent_schedule))):
            exchange_subject = exchange_schedule[i].strip()
            parent_subject = parent_schedule[i].strip()
            
            time_info = get_time_slot_info(i // 6, i % 6)
            
            # 全ての比較を記録（デバッグ用）
            all_comparisons.append({
                'exchange_class': exchange_class,
                'parent_class': parent_class,
                'time': time_info,
                'exchange_subject': exchange_subject or '(空)',
                'parent_subject': parent_subject or '(空)'
            })
            
            # 自立活動の時は同期不要
            if exchange_subject == '自立':
                continue
                
            # 科目が異なる場合（空白も含む）
            if exchange_subject != parent_subject:
                mismatches.append({
                    'exchange_class': exchange_class,
                    'parent_class': parent_class,
                    'time': time_info,
                    'exchange_subject': exchange_subject or '(空)',
                    'parent_subject': parent_subject or '(空)'
                })
    
    return mismatches, all_comparisons

def check_daily_duplicates(schedule_data):
    """日内重複をチェック"""
    duplicates = []
    
    for class_name, data in schedule_data.items():
        schedule = data['schedule']
        
        # 各日をチェック
        for day_idx in range(5):  # 月〜金
            day_subjects = defaultdict(list)
            
            # その日の6時限分を収集
            for period_idx in range(6):
                slot_idx = day_idx * 6 + period_idx
                if slot_idx < len(schedule):
                    subject = schedule[slot_idx].strip()
                    if subject and subject not in ['', '欠', 'YT', '行']:
                        day_subjects[subject].append(period_idx + 1)
            
            # 重複をチェック
            for subject, periods in day_subjects.items():
                if len(periods) > 1:
                    days = ['月', '火', '水', '木', '金']
                    duplicates.append({
                        'class': class_name,
                        'day': days[day_idx],
                        'subject': subject,
                        'periods': periods
                    })
    
    return duplicates

def check_duplicate_rows(schedule_data):
    """重複行をチェック"""
    class_counts = defaultdict(list)
    
    for class_name, data in schedule_data.items():
        class_counts[class_name].append(data['row_number'])
    
    duplicates = []
    for class_name, row_numbers in class_counts.items():
        if len(row_numbers) > 1:
            duplicates.append({
                'class': class_name,
                'rows': row_numbers
            })
    
    return duplicates

def main():
    """メイン処理"""
    csv_path = project_root / 'data' / 'output' / 'output.csv'
    
    if not csv_path.exists():
        print(f"❌ ファイルが見つかりません: {csv_path}")
        return
    
    print("📊 CSV分析を開始します...")
    print(f"ファイル: {csv_path}")
    print("=" * 80)
    
    # スケジュールを読み込み
    schedule_data, all_rows = load_schedule_from_csv(csv_path)
    
    # デバッグ: 全行の概要を表示
    print("\n🔍 CSV行の概要")
    print("-" * 60)
    for row_info in all_rows:
        if row_info['class_name'] == '(空)' or 'は空行' in row_info['class_name']:
            print(f"  行{row_info['row_number']}: {row_info['class_name']} → {row_info['first_subjects'][:3]}...")
    
    # 1. 交流学級同期チェック
    print("\n🔍 交流学級同期チェック")
    print("-" * 60)
    mismatches, all_comparisons = check_exchange_class_sync(schedule_data)
    
    if mismatches:
        print(f"❌ {len(mismatches)}件の同期違反が見つかりました:")
        
        # クラスごとにグループ化
        by_class = defaultdict(list)
        for m in mismatches:
            by_class[m['exchange_class']].append(m)
        
        for exchange_class in sorted(by_class.keys()):
            violations = by_class[exchange_class]
            print(f"\n  【{exchange_class}】({len(violations)}件)")
            for v in violations:
                print(f"    {v['time']}: {v['exchange_subject']} ≠ {v['parent_class']}の{v['parent_subject']}")
    else:
        print("✅ 交流学級の同期は正常です")
        
    # デバッグ: 3年6組と3年7組の詳細比較を表示
    print("\n\n🔍 3年6組・3年7組の詳細比較（画像の赤いハイライト部分）")
    print("-" * 60)
    for comp in all_comparisons:
        if comp['exchange_class'] in ['3年6組', '3年7組']:
            if comp['exchange_subject'] != comp['parent_subject'] and comp['exchange_subject'] != '自立':
                print(f"  {comp['exchange_class']} vs {comp['parent_class']} @ {comp['time']}: " +
                      f"{comp['exchange_subject']} ≠ {comp['parent_subject']}")
    
    # 2. 日内重複チェック
    print("\n\n🔍 日内重複チェック")
    print("-" * 60)
    duplicates = check_daily_duplicates(schedule_data)
    
    if duplicates:
        print(f"❌ {len(duplicates)}件の日内重複が見つかりました:")
        for dup in duplicates:
            periods_str = ', '.join([f"{p}限" for p in dup['periods']])
            print(f"  {dup['class']} - {dup['day']}曜日: {dup['subject']} ({periods_str})")
    else:
        print("✅ 日内重複はありません")
    
    # 3. 重複行チェック
    print("\n\n🔍 重複行チェック")
    print("-" * 60)
    duplicate_rows = check_duplicate_rows(schedule_data)
    
    if duplicate_rows:
        print(f"❌ {len(duplicate_rows)}件のクラス重複が見つかりました:")
        for dup in duplicate_rows:
            print(f"  {dup['class']}: 行番号 {dup['rows']}")
    else:
        print("✅ クラスの重複はありません")
    
    # 無名行のチェック
    unnamed_rows = [k for k, v in schedule_data.items() if k.startswith('(無名行')]
    if unnamed_rows:
        print(f"\n❌ {len(unnamed_rows)}件の無名行が見つかりました:")
        for unnamed in unnamed_rows:
            row_data = schedule_data[unnamed]
            print(f"  {unnamed}: {row_data['schedule'][:6]}...")
    
    # 4. 特に問題が多いクラスの詳細表示
    print("\n\n📋 問題が多いクラスの詳細")
    print("-" * 60)
    
    # 3年6組と3年7組の詳細を表示（画像で赤いハイライトが多い）
    for class_name in ['3年6組', '3年7組']:
        if class_name in schedule_data:
            print(f"\n【{class_name}】")
            schedule = schedule_data[class_name]['schedule']
            
            # 時間割を表形式で表示
            days = ['月', '火', '水', '木', '金']
            for period in range(6):
                row = f"  {period + 1}限: "
                for day in range(5):
                    idx = day * 6 + period
                    if idx < len(schedule):
                        subject = schedule[idx].strip() or '---'
                        row += f"{days[day]}{subject:　<4}"
                print(row)
    
    # 5. 親学級との並列比較
    print("\n\n📋 親学級との並列比較")
    print("-" * 60)
    
    # 3年3組と3年6組の比較
    if '3年3組' in schedule_data and '3年6組' in schedule_data:
        print("\n【3年3組 vs 3年6組】")
        parent_schedule = schedule_data['3年3組']['schedule']
        exchange_schedule = schedule_data['3年6組']['schedule']
        
        days = ['月', '火', '水', '木', '金']
        for period in range(6):
            print(f"\n{period + 1}限:")
            for day in range(5):
                idx = day * 6 + period
                if idx < len(parent_schedule) and idx < len(exchange_schedule):
                    p_subject = parent_schedule[idx].strip() or '---'
                    e_subject = exchange_schedule[idx].strip() or '---'
                    match = "✅" if p_subject == e_subject or e_subject == '自立' else "❌"
                    print(f"  {days[day]}: 3年3組={p_subject:　<4} 3年6組={e_subject:　<4} {match}")
    
    # 3年2組と3年7組の比較
    if '3年2組' in schedule_data and '3年7組' in schedule_data:
        print("\n【3年2組 vs 3年7組】")
        parent_schedule = schedule_data['3年2組']['schedule']
        exchange_schedule = schedule_data['3年7組']['schedule']
        
        days = ['月', '火', '水', '木', '金']
        for period in range(6):
            print(f"\n{period + 1}限:")
            for day in range(5):
                idx = day * 6 + period
                if idx < len(parent_schedule) and idx < len(exchange_schedule):
                    p_subject = parent_schedule[idx].strip() or '---'
                    e_subject = exchange_schedule[idx].strip() or '---'
                    match = "✅" if p_subject == e_subject or e_subject == '自立' else "❌"
                    print(f"  {days[day]}: 3年2組={p_subject:　<4} 3年7組={e_subject:　<4} {match}")

if __name__ == '__main__':
    main()