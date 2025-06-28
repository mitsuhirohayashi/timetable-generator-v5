#!/usr/bin/env python3
"""残りの日内重複を修正する（5組と交流学級を考慮）"""

import csv
from typing import List, Dict, Tuple
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

def read_csv(filepath: str) -> List[List[str]]:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return list(csv.reader(f))

def write_csv(filepath: str, data: List[List[str]]):
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

def get_time_slot_info(col_idx: int) -> Tuple[str, int]:
    """列番号から曜日と時限を取得"""
    days = ['月', '火', '水', '木', '金']
    day_idx = (col_idx - 1) // 6
    period = ((col_idx - 1) % 6) + 1
    if day_idx < len(days):
        return days[day_idx], period
    return None, None

def find_safe_swap_target(
    output_data: List[List[str]], 
    row_idx: int, 
    dup_col_idx: int,
    dup_subject: str,
    is_grade5: bool = False
) -> Tuple[int, str]:
    """安全な交換対象を探す"""
    
    row = output_data[row_idx]
    class_name = row[0].strip()
    
    # 5組の場合は特別な処理が必要
    if is_grade5:
        # 5組は合同授業なので、他の日の授業と交換する
        for search_col_idx in range(1, min(31, len(row))):
            if search_col_idx == dup_col_idx:
                continue
                
            search_day, _ = get_time_slot_info(search_col_idx)
            dup_day, _ = get_time_slot_info(dup_col_idx)
            
            # 異なる日の授業を探す
            if search_day and search_day != dup_day:
                alt_subject = row[search_col_idx].strip()
                
                # 固定科目や特殊科目は交換しない
                if alt_subject and alt_subject not in ['', 'YT', '道', '欠', '自立', '日生', '作業', '生単']:
                    # 交換先の日に重複がないかチェック
                    if not check_daily_duplicate_in_day(row, search_col_idx, dup_subject):
                        return search_col_idx, alt_subject
    else:
        # 通常クラスの場合
        for search_col_idx in range(1, min(31, len(row))):
            if search_col_idx == dup_col_idx:
                continue
                
            alt_subject = row[search_col_idx].strip()
            
            # 固定科目や自立活動は交換しない
            if alt_subject and alt_subject not in ['', 'YT', '道', '欠', '自立'] and alt_subject != dup_subject:
                # 交換によって新たな重複が発生しないかチェック
                dup_day, _ = get_time_slot_info(dup_col_idx)
                search_day, _ = get_time_slot_info(search_col_idx)
                
                if not check_daily_duplicate_in_day(row, dup_col_idx, alt_subject) and \
                   not check_daily_duplicate_in_day(row, search_col_idx, dup_subject):
                    return search_col_idx, alt_subject
    
    return -1, None

def check_daily_duplicate_in_day(row: List[str], target_col_idx: int, subject: str) -> bool:
    """指定した日に特定の科目が既にあるかチェック"""
    target_day, _ = get_time_slot_info(target_col_idx)
    if not target_day:
        return False
    
    day_idx = (target_col_idx - 1) // 6
    
    for period in range(1, 7):
        check_col_idx = day_idx * 6 + period
        if check_col_idx != target_col_idx and check_col_idx < len(row):
            if row[check_col_idx].strip() == subject:
                return True
    
    return False

def fix_specific_duplicates(output_data: List[List[str]]) -> int:
    """特定の日内重複を修正"""
    fixed_count = 0
    
    # 修正対象の重複リスト
    duplicates_to_fix = [
        ('1年5組', '月', '英'),
        ('2年5組', '月', '英'),
        ('3年5組', '月', '英'),
        ('3年2組', '月', '英'),
        ('3年3組', '月', '国'),
        ('3年7組', '月', '英')
    ]
    
    for class_name, day, subject in duplicates_to_fix:
        # 該当クラスの行を探す
        for row_idx in range(2, len(output_data)):
            row = output_data[row_idx]
            if row and row[0] and row[0].strip() == class_name:
                # 該当する日の重複を探す
                day_idx = ['月', '火', '水', '木', '金'].index(day)
                occurrences = []
                
                for period in range(1, 7):
                    col_idx = day_idx * 6 + period
                    if col_idx < len(row) and row[col_idx].strip() == subject:
                        occurrences.append(col_idx)
                
                # 重複があれば修正
                if len(occurrences) >= 2:
                    # 2番目の出現を別の科目と交換
                    dup_col_idx = occurrences[1]
                    is_grade5 = '5組' in class_name
                    
                    swap_col_idx, swap_subject = find_safe_swap_target(
                        output_data, row_idx, dup_col_idx, subject, is_grade5
                    )
                    
                    if swap_col_idx > 0:
                        # 交換実行
                        row[dup_col_idx], row[swap_col_idx] = row[swap_col_idx], row[dup_col_idx]
                        fixed_count += 1
                        
                        swap_day, swap_period = get_time_slot_info(swap_col_idx)
                        dup_day, dup_period = get_time_slot_info(dup_col_idx)
                        
                        print(f"✅ {class_name}: {dup_day}曜{dup_period}限の「{subject}」と"
                              f"{swap_day}曜{swap_period}限の「{swap_subject}」を交換")
                    else:
                        print(f"⚠️  {class_name}の{day}曜日の「{subject}」重複: 安全な交換先が見つかりません")
                
                break
    
    return fixed_count

def main():
    # データ読み込み
    output_data = read_csv('data/output/output.csv')
    
    print('=== 残りの日内重複を修正 ===\n')
    
    # バックアップ作成
    import shutil
    shutil.copy('data/output/output.csv', 'data/output/output_before_final_fix.csv')
    print('✅ バックアップを作成しました: output_before_final_fix.csv\n')
    
    # 特定の重複を修正
    print('【日内重複の修正】')
    fixed_count = fix_specific_duplicates(output_data)
    print(f'\n→ {fixed_count}件の日内重複を修正しました\n')
    
    # 修正後のデータを保存
    write_csv('data/output/output.csv', output_data)
    print('✅ 修正後のデータを保存しました: output.csv\n')
    
    print('修正完了！ 詳細な分析で確認してください。')

if __name__ == "__main__":
    main()