#!/usr/bin/env python3
"""交流学級同期対応の手動空きスロット埋めスクリプト

QA.txtのルールに従い、交流学級と親学級の同期を保ちながら空きスロットを埋めます。
"""

import csv
import logging
from pathlib import Path
from collections import defaultdict
import re

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExchangeClassAwareFiller:
    """交流学級の同期を考慮した空きスロット埋め"""
    
    def __init__(self):
        # 交流学級マッピングをハードコード（QA.txtより）
        self.exchange_mappings = {
            (1, 6): (1, 1),  # 1年6組 ← 1年1組
            (1, 7): (1, 2),  # 1年7組 ← 1年2組
            (2, 6): (2, 3),  # 2年6組 ← 2年3組
            (2, 7): (2, 2),  # 2年7組 ← 2年2組
            (3, 6): (3, 3),  # 3年6組 ← 3年3組
            (3, 7): (3, 2),  # 3年7組 ← 3年2組
        }
        
        # 逆引きマッピングも作成
        self.parent_to_exchange = {}
        for exchange, parent in self.exchange_mappings.items():
            if parent not in self.parent_to_exchange:
                self.parent_to_exchange[parent] = []
            self.parent_to_exchange[parent].append(exchange)
    
    def parse_class_name(self, class_name):
        """クラス名から学年とクラス番号を抽出"""
        match = re.match(r'(\d+)年(\d+)組', class_name)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None
    
    def is_exchange_class(self, grade, class_num):
        """交流学級かどうか判定"""
        return (grade, class_num) in self.exchange_mappings
    
    def is_parent_class(self, grade, class_num):
        """親学級かどうか判定"""
        return (grade, class_num) in self.parent_to_exchange
    
    def get_paired_classes(self, grade, class_num):
        """ペアになるクラスを取得"""
        pairs = []
        
        # 交流学級の場合
        if self.is_exchange_class(grade, class_num):
            parent = self.exchange_mappings[(grade, class_num)]
            pairs.append(parent)
        
        # 親学級の場合
        if self.is_parent_class(grade, class_num):
            exchanges = self.parent_to_exchange[(grade, class_num)]
            pairs.extend(exchanges)
        
        return pairs
    
    def read_csv(self, file_path):
        """CSVファイルを読み込む"""
        rows = []
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(row)
        return rows
    
    def write_csv(self, file_path, rows):
        """CSVファイルに書き込む"""
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row)
    
    def find_class_row(self, rows, grade, class_num):
        """指定クラスの行を探す"""
        target_name = f"{grade}年{class_num}組"
        for idx, row in enumerate(rows):
            if row and row[0] == target_name:
                return idx
        return None
    
    def analyze_empty_slots(self, rows):
        """空きスロットを分析（交流学級を考慮）"""
        empty_slots = []
        processed_pairs = set()
        days = ['月', '火', '水', '木', '金']
        
        # ヘッダー行をスキップ
        for row_idx, row in enumerate(rows[2:], 2):
            if not row or not row[0]:  # 空行をスキップ
                continue
            
            class_name = row[0]
            grade, class_num = self.parse_class_name(class_name)
            if not grade:
                continue
            
            # ペアクラスを取得
            pairs = self.get_paired_classes(grade, class_num)
            
            for col_idx, cell in enumerate(row[1:], 1):
                if cell == '':
                    day_index = (col_idx-1) // 6
                    period = ((col_idx-1) % 6) + 1
                    day = days[day_index]
                    
                    # 交流学級の場合、自立活動の時間でないかチェック
                    if self.is_exchange_class(grade, class_num):
                        # 親学級の同じ時間を確認
                        parent = self.exchange_mappings[(grade, class_num)]
                        parent_row_idx = self.find_class_row(rows, parent[0], parent[1])
                        if parent_row_idx and rows[parent_row_idx][col_idx] in ['数', '英']:
                            logger.info(f"{class_name} {day}曜{period}限は自立活動の可能性があるためスキップ")
                            continue
                    
                    # ペアクラスも同時にチェック
                    all_empty = True
                    for pair_grade, pair_class in pairs:
                        pair_row_idx = self.find_class_row(rows, pair_grade, pair_class)
                        if pair_row_idx and rows[pair_row_idx][col_idx] != '':
                            all_empty = False
                            break
                    
                    if all_empty:
                        # ペアをまとめて処理するため、代表クラスのみ記録
                        pair_key = tuple(sorted([(grade, class_num)] + pairs))
                        if pair_key not in processed_pairs:
                            empty_slots.append({
                                'row': row_idx,
                                'col': col_idx,
                                'class': class_name,
                                'grade': grade,
                                'class_num': class_num,
                                'day': day,
                                'period': period,
                                'pairs': pairs
                            })
                            processed_pairs.add(pair_key)
        
        return empty_slots
    
    def count_subject_hours(self, rows, class_name):
        """各クラスの科目別時数をカウント"""
        hours = defaultdict(int)
        
        # クラスの行を探す
        class_row = None
        for row in rows[2:]:
            if row and row[0] == class_name:
                class_row = row
                break
        
        if not class_row:
            return hours
        
        # 科目をカウント（自立活動は除外）
        for cell in class_row[1:]:
            if cell and cell != '' and cell not in ['自立', '日生', '作業']:
                hours[cell] += 1
        
        return hours
    
    def get_standard_hours(self, class_name):
        """標準時数を取得（簡易版）"""
        # 学年を判定
        grade, class_num = self.parse_class_name(class_name)
        if not grade:
            return {}
        
        # 5組は特別
        if class_num == 5:
            return {
                '国': 4, '社': 1, '数': 4, '理': 3,
                '音': 1, '美': 1, '保': 2, '技': 1,
                '家': 1, '英': 2, '道': 1
            }
        
        # 通常学級と交流学級
        if grade == 1:
            return {
                '国': 4, '社': 3, '数': 4, '理': 3,
                '音': 1, '美': 1, '保': 3, '技': 1,
                '家': 1, '英': 4, '道': 1
            }
        elif grade == 2:
            return {
                '国': 4, '社': 3, '数': 3, '理': 4,
                '音': 1, '美': 1, '保': 3, '英': 4,
                '道': 1
            }
        else:  # 3年
            return {
                '国': 3, '社': 4, '数': 4, '理': 4,
                '音': 1, '美': 1, '保': 3, '英': 4,
                '道': 1
            }
    
    def suggest_subject(self, class_name, current_hours, day, period):
        """埋めるべき科目を提案"""
        standard = self.get_standard_hours(class_name)
        
        # 不足している科目をリストアップ
        shortage = {}
        for subject, required in standard.items():
            current = current_hours.get(subject, 0)
            if current < required:
                shortage[subject] = required - current
        
        if not shortage:
            # 全て満たしている場合は、主要5教科を追加
            major_subjects = ['国', '数', '英', '理', '社']
            for subj in major_subjects:
                if subj in standard:
                    return subj
            return None
        
        # 不足が多い順にソート
        sorted_shortage = sorted(shortage.items(), key=lambda x: x[1], reverse=True)
        
        # 最も不足している科目を返す
        return sorted_shortage[0][0]
    
    def fill_empty_slots(self, input_file, output_file):
        """空きスロットを埋める（交流学級同期対応）"""
        # CSVを読み込む
        rows = self.read_csv(input_file)
        
        # 空きスロットを分析
        empty_slots = self.analyze_empty_slots(rows)
        logger.info(f"空きスロット数: {len(empty_slots)}")
        
        # 各空きスロットを埋める
        filled_count = 0
        for slot in empty_slots:
            class_name = slot['class']
            
            # 現在の時数をカウント（代表クラスで計算）
            current_hours = self.count_subject_hours(rows, class_name)
            
            # 埋めるべき科目を提案
            subject = self.suggest_subject(class_name, current_hours, slot['day'], slot['period'])
            
            if subject:
                # 代表クラスに配置
                rows[slot['row']][slot['col']] = subject
                logger.info(f"{class_name} {slot['day']}曜{slot['period']}限 → {subject}")
                filled_count += 1
                
                # ペアクラスにも同じ科目を配置
                for pair_grade, pair_class in slot['pairs']:
                    pair_row_idx = self.find_class_row(rows, pair_grade, pair_class)
                    if pair_row_idx:
                        rows[pair_row_idx][slot['col']] = subject
                        logger.info(f"  └→ {pair_grade}年{pair_class}組も同期: {subject}")
                        filled_count += 1
        
        # 結果を保存
        self.write_csv(output_file, rows)
        logger.info(f"埋めたスロット数: {filled_count}")
        
        return filled_count

def main():
    """メイン処理"""
    input_file = Path('data/output/output.csv')
    output_file = Path('data/output/output_filled.csv')
    
    if not input_file.exists():
        logger.error(f"入力ファイルが見つかりません: {input_file}")
        return
    
    logger.info("=== 交流学級同期対応 空きスロット埋め処理開始 ===")
    logger.info("QA.txtのルールに従って処理します")
    
    filler = ExchangeClassAwareFiller()
    filled = filler.fill_empty_slots(input_file, output_file)
    
    logger.info(f"\n処理完了:")
    logger.info(f"- 埋めたスロット数: {filled}")
    logger.info(f"- 出力ファイル: {output_file}")
    
    # output.csvにコピー
    if filled > 0:
        import shutil
        shutil.copy2(output_file, input_file)
        logger.info(f"output.csvを更新しました")

if __name__ == "__main__":
    main()