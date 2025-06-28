#!/usr/bin/env python3
"""体育館使用制約違反を修正するスクリプト

交流学級ペアが体育の時間に必ず一緒に活動するように時間割を修正します。
"""
import csv
import logging
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをsys.pathに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, ClassReference

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 交流学級ペアの定義
EXCHANGE_PAIRS = {
    (1, 6): (1, 1),  # 1年6組 ↔ 1年1組
    (1, 7): (1, 2),  # 1年7組 ↔ 1年2組
    (2, 6): (2, 3),  # 2年6組 ↔ 2年3組
    (2, 7): (2, 2),  # 2年7組 ↔ 2年2組
    (3, 6): (3, 3),  # 3年6組 ↔ 3年3組
    (3, 7): (3, 2),  # 3年7組 ↔ 3年2組
}

def load_timetable(file_path):
    """時間割CSVを読み込む"""
    timetable = {}
    headers = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行
        period_row = next(reader)  # 時限行
        
        for row in reader:
            if not row[0] or row[0].strip() == "":
                continue
                
            class_name = row[0]
            timetable[class_name] = row[1:]
    
    return timetable, headers, period_row

def save_timetable(file_path, timetable, headers, period_row):
    """時間割をCSVに保存"""
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(period_row)
        
        for class_name in sorted(timetable.keys()):
            row = [class_name] + timetable[class_name]
            writer.writerow(row)

def parse_class_name(class_name):
    """クラス名から学年とクラス番号を抽出"""
    try:
        # "1年1組" -> (1, 1)
        parts = class_name.replace("年", "-").replace("組", "").split("-")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except:
        pass
    return None, None

def find_pe_conflicts(timetable):
    """体育の時間で交流学級ペアが同期していない箇所を見つける"""
    conflicts = []
    
    for exchange_pair, parent_pair in EXCHANGE_PAIRS.items():
        exchange_class = f"{exchange_pair[0]}年{exchange_pair[1]}組"
        parent_class = f"{parent_pair[0]}年{parent_pair[1]}組"
        
        if exchange_class not in timetable or parent_class not in timetable:
            continue
        
        exchange_schedule = timetable[exchange_class]
        parent_schedule = timetable[parent_class]
        
        for i, (exchange_subj, parent_subj) in enumerate(zip(exchange_schedule, parent_schedule)):
            # 交流学級が自立活動の場合はスキップ
            if exchange_subj in ["自立", "日生", "生単", "作業"]:
                continue
            
            # どちらかが体育の場合
            if exchange_subj == "保" or parent_subj == "保":
                # 両方が体育でない場合は問題
                if exchange_subj != parent_subj:
                    day_period = divmod(i, 6)
                    day = ["月", "火", "水", "木", "金"][day_period[0]]
                    period = day_period[1] + 1
                    conflicts.append({
                        'exchange_class': exchange_class,
                        'parent_class': parent_class,
                        'day': day,
                        'period': period,
                        'exchange_subject': exchange_subj,
                        'parent_subject': parent_subj,
                        'index': i
                    })
    
    return conflicts

def fix_pe_sync(timetable, conflicts):
    """体育の同期を修正"""
    fixes = []
    
    for conflict in conflicts:
        exchange_class = conflict['exchange_class']
        parent_class = conflict['parent_class']
        idx = conflict['index']
        
        exchange_subj = conflict['exchange_subject']
        parent_subj = conflict['parent_subject']
        
        # 親学級が体育の場合、交流学級も体育にする
        if parent_subj == "保" and exchange_subj != "保":
            # 交流学級の他の場所で体育を探す
            exchange_schedule = timetable[exchange_class]
            pe_indices = [i for i, subj in enumerate(exchange_schedule) if subj == "保"]
            
            if pe_indices:
                # 最初に見つかった体育と交換
                swap_idx = pe_indices[0]
                exchange_schedule[idx], exchange_schedule[swap_idx] = exchange_schedule[swap_idx], exchange_schedule[idx]
                fixes.append(f"{exchange_class}: {conflict['day']}{conflict['period']}時限目と{divmod(swap_idx, 6)[0]+1}日{divmod(swap_idx, 6)[1]+1}時限目を交換")
        
        # 交流学級が体育の場合、親学級も体育にする
        elif exchange_subj == "保" and parent_subj != "保":
            # 親学級の他の場所で体育を探す
            parent_schedule = timetable[parent_class]
            pe_indices = [i for i, subj in enumerate(parent_schedule) if subj == "保"]
            
            if pe_indices:
                # 最初に見つかった体育と交換
                swap_idx = pe_indices[0]
                parent_schedule[idx], parent_schedule[swap_idx] = parent_schedule[swap_idx], parent_schedule[idx]
                fixes.append(f"{parent_class}: {conflict['day']}{conflict['period']}時限目と{divmod(swap_idx, 6)[0]+1}日{divmod(swap_idx, 6)[1]+1}時限目を交換")
    
    return fixes

def main():
    """メイン処理"""
    input_file = project_root / "data" / "output" / "output.csv"
    output_file = project_root / "data" / "output" / "output.csv"
    
    logger.info("体育館使用制約修正スクリプトを開始")
    
    # 時間割を読み込む
    timetable, headers, period_row = load_timetable(input_file)
    logger.info(f"時間割を読み込みました: {len(timetable)}クラス")
    
    # 体育の同期問題を検出
    conflicts = find_pe_conflicts(timetable)
    
    if not conflicts:
        logger.info("✓ 交流学級の体育同期に問題はありません")
        return
    
    logger.warning(f"❌ {len(conflicts)}件の体育同期問題を検出:")
    for conflict in conflicts:
        logger.warning(f"  {conflict['exchange_class']}と{conflict['parent_class']}: "
                      f"{conflict['day']}{conflict['period']}時限 "
                      f"({conflict['exchange_subject']} vs {conflict['parent_subject']})")
    
    # 修正を実行
    fixes = fix_pe_sync(timetable, conflicts)
    
    if fixes:
        logger.info(f"\n✓ {len(fixes)}件の修正を実行:")
        for fix in fixes:
            logger.info(f"  {fix}")
        
        # 修正後の時間割を保存
        save_timetable(output_file, timetable, headers, period_row)
        logger.info(f"\n修正した時間割を保存しました: {output_file}")
    else:
        logger.warning("修正できませんでした（体育の時間が見つからない可能性があります）")

if __name__ == "__main__":
    main()