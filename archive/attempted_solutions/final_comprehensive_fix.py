#!/usr/bin/env python3
"""
最終的な包括的修正スクリプト

残る違反を可能な限り修正します。
"""
import os
import sys
import csv
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# プロジェクトルートのパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class FinalComprehensiveFixer:
    def __init__(self):
        # 教師マッピング（体を保健体育に修正）
        self.subject_teachers = {
            '国': '智田先生',
            '数': '井上先生',
            '英': '蒲地先生',
            '理': '梶永先生',
            '社': '神田先生',
            '音': '今先生',
            '美': '平野先生',
            '保': '野田先生',  # 保健体育
            '保健体育': '野田先生',
            '技': '國本先生',
            '家': '石原先生',
            '技家': '技家担当先生',
            '学総': '学総担当先生',
            '総': '担任',
            '総合': '担任',
            '道': '担任',
            '道徳': '担任',
            '学': '担任',
            '学活': '担任',
        }
        
        # 担任マッピング
        self.homeroom_teachers = {
            '1年1組': '金子ひ先生',
            '1年2組': '井野口先生',
            '1年3組': '梶永先生',
            '2年1組': '塚本先生',
            '2年2組': '野口先生',
            '2年3組': '永山先生',
            '3年1組': '白石先生',
            '3年2組': '森山先生',
            '3年3組': '北先生',
            '1年5組': '金子み先生',
            '2年5組': '金子み先生',
            '3年5組': '金子み先生',
            '1年6組': '寺田先生',
            '1年7組': '橋本先生',
            '2年6組': '永山先生',
            '2年7組': '野口先生',
            '3年6組': '北先生',
            '3年7組': '森山先生',
        }
        
        # 固定科目
        self.fixed_subjects = {'欠', 'YT', '学', '学活', '道', '道徳', '総', '総合', '学総', '行', '行事', 'テスト', '技家'}
        
        # 標準時数
        self.standard_hours = {
            '国': 4.0,
            '数': 4.0,
            '英': 4.0,
            '理': 3.0,
            '社': 3.0,
            '音': 1.3,
            '美': 1.3,
            '技': 1.0,
            '家': 1.0,
            '保': 3.0,
            '保健体育': 3.0,
        }
        
        # 交流学級マッピング
        self.exchange_mappings = {
            '1年6組': '1年1組',
            '1年7組': '1年2組',
            '2年6組': '2年3組',
            '2年7組': '2年2組',
            '3年6組': '3年3組',
            '3年7組': '3年2組',
        }

    def fix_schedule(self):
        """時間割を修正"""
        logger.info("=== 最終的な包括的修正を開始 ===\n")
        
        # CSVファイルを読み込み
        input_file = 'data/output/output.csv'
        
        # データを読み込み
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # ヘッダー行を保持
        header_rows = rows[:2]
        data_rows = rows[2:]
        
        # 時間割データを2次元配列として扱う
        schedule = []
        class_names = []
        
        for row in data_rows:
            if row and row[0]:  # クラス名がある行
                class_names.append(row[0])
                schedule.append(row[1:])  # 時間割部分
            else:
                class_names.append("")
                schedule.append([""] * 30)
        
        # 1. 体→保に統一
        logger.info("1. 体→保に統一...")
        体_to_保_count = 0
        for i in range(len(schedule)):
            for j in range(30):
                if schedule[i][j] == '体':
                    schedule[i][j] = '保'
                    体_to_保_count += 1
        logger.info(f"  → {体_to_保_count}コマを修正")
        
        # 2. テスト期間（月〜水の1-3限）を行に変更
        logger.info("\n2. テスト期間を行に変更...")
        test_period_count = 0
        test_periods = [
            (0, 1, 2),    # 月曜1-3限
            (6, 7, 8),    # 火曜1-3限
            (12, 13, 14), # 水曜1-3限
        ]
        
        for i, class_name in enumerate(class_names):
            if class_name:
                for periods in test_periods:
                    for period in periods:
                        if schedule[i][period] not in ['行', '行事', 'テスト']:
                            schedule[i][period] = '行'
                            test_period_count += 1
        logger.info(f"  → {test_period_count}コマをテスト期間に修正")
        
        # 3. 標準時数に基づいて科目を調整
        logger.info("\n3. 標準時数に基づいて科目を調整...")
        hours_adjustments = 0
        
        for i, class_name in enumerate(class_names):
            if not class_name or '5組' in class_name:  # 5組は特別なので除外
                continue
            
            # 現在の時数をカウント
            current_hours = defaultdict(int)
            for j in range(30):
                subject = schedule[i][j]
                if subject and subject not in self.fixed_subjects:
                    if subject == '保':
                        current_hours['保'] += 1
                    else:
                        current_hours[subject] += 1
            
            # 調整が必要な科目を特定
            needed_adjustments = []
            for subject, target in self.standard_hours.items():
                if subject == '保健体育':
                    subject = '保'
                current = current_hours.get(subject, 0)
                diff = target - current
                if abs(diff) > 0.5:
                    needed_adjustments.append((subject, diff))
            
            # 過剰な科目を不足している科目に置き換え
            for subject, diff in needed_adjustments:
                if diff > 0:  # 不足
                    # 過剰な科目を探す
                    for excess_subject, excess_diff in needed_adjustments:
                        if excess_diff < -0.5:  # 過剰
                            # 置き換えを実行
                            for j in range(30):
                                if schedule[i][j] == excess_subject:
                                    # その日に同じ科目がないか確認
                                    day_start = (j // 6) * 6
                                    day_has_subject = False
                                    for k in range(day_start, day_start + 6):
                                        if k != j and schedule[i][k] == subject:
                                            day_has_subject = True
                                            break
                                    
                                    if not day_has_subject:
                                        schedule[i][j] = subject
                                        hours_adjustments += 1
                                        current_hours[subject] += 1
                                        current_hours[excess_subject] -= 1
                                        
                                        if current_hours[subject] >= target:
                                            break
                            
                            if current_hours[subject] >= target:
                                break
        
        logger.info(f"  → {hours_adjustments}コマを調整")
        
        # 4. 5組を完全同期
        logger.info("\n4. 5組を完全同期...")
        sync_count = 0
        
        # 5組のインデックス
        grade5_indices = []
        for i, class_name in enumerate(class_names):
            if '5組' in class_name:
                grade5_indices.append(i)
        
        if len(grade5_indices) == 3:
            # 1年5組を基準にする
            base_idx = grade5_indices[0]
            for period in range(30):
                base_subject = schedule[base_idx][period]
                for idx in grade5_indices[1:]:
                    if schedule[idx][period] != base_subject:
                        schedule[idx][period] = base_subject
                        sync_count += 1
        
        logger.info(f"  → {sync_count}コマを同期")
        
        # 5. 交流学級の同期（自立活動以外）
        logger.info("\n5. 交流学級を同期...")
        exchange_sync_count = 0
        
        for exchange_name, parent_name in self.exchange_mappings.items():
            exchange_idx = None
            parent_idx = None
            
            for i, class_name in enumerate(class_names):
                if class_name == exchange_name:
                    exchange_idx = i
                elif class_name == parent_name:
                    parent_idx = i
            
            if exchange_idx is not None and parent_idx is not None:
                for period in range(30):
                    exchange_subject = schedule[exchange_idx][period]
                    parent_subject = schedule[parent_idx][period]
                    
                    # 自立活動、日生、作業以外は同期
                    if exchange_subject not in ['自立', '日生', '作業']:
                        if exchange_subject != parent_subject:
                            schedule[exchange_idx][period] = parent_subject
                            exchange_sync_count += 1
        
        logger.info(f"  → {exchange_sync_count}コマを同期")
        
        # 6. 残りの空きコマを埋める
        logger.info("\n6. 残りの空きコマを埋める...")
        empty_fills = 0
        
        for i, class_name in enumerate(class_names):
            if not class_name:
                continue
            
            for j in range(30):
                if not schedule[i][j] or schedule[i][j] == "":
                    # 不足している教科を選択
                    needed = self._find_most_needed_subject(schedule[i], j)
                    if needed:
                        schedule[i][j] = needed
                        empty_fills += 1
        
        logger.info(f"  → {empty_fills}個の空きコマを埋めました")
        
        # 結果を保存
        logger.info("\n結果を保存中...")
        
        with open(input_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(header_rows)
            for i, class_name in enumerate(class_names):
                row = [class_name] + schedule[i]
                writer.writerow(row)
        
        logger.info(f"\n修正完了！")
        logger.info(f"ファイルを更新: {input_file}")
        
        # 違反チェックを実行
        logger.info("\n=== 修正後の違反チェック ===")
        os.system("python3 scripts/analysis/check_violations.py")
    
    def _find_most_needed_subject(self, class_schedule, period):
        """最も必要な科目を探す"""
        # 現在の時数をカウント
        current_hours = defaultdict(int)
        for subject in class_schedule:
            if subject and subject not in self.fixed_subjects:
                if subject == '保':
                    current_hours['保'] += 1
                else:
                    current_hours[subject] += 1
        
        # その日の科目を収集
        day_start = (period // 6) * 6
        day_subjects = set()
        for p in range(day_start, day_start + 6):
            if p < len(class_schedule) and class_schedule[p]:
                day_subjects.add(class_schedule[p])
        
        # 最も不足している科目を選択
        best_subject = None
        max_shortage = 0
        
        for subject, target in self.standard_hours.items():
            if subject == '保健体育':
                subject = '保'
            
            current = current_hours.get(subject, 0)
            shortage = target - current
            
            # その日にまだない科目を優先
            if shortage > 0:
                if subject not in day_subjects and shortage > max_shortage:
                    max_shortage = shortage
                    best_subject = subject
        
        # 見つからない場合は単に不足している科目
        if not best_subject:
            for subject, target in self.standard_hours.items():
                if subject == '保健体育':
                    subject = '保'
                
                current = current_hours.get(subject, 0)
                shortage = target - current
                
                if shortage > max_shortage:
                    max_shortage = shortage
                    best_subject = subject
        
        return best_subject


def main():
    """メイン処理"""
    fixer = FinalComprehensiveFixer()
    fixer.fix_schedule()


if __name__ == "__main__":
    main()