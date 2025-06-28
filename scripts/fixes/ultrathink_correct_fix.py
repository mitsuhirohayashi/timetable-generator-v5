#!/usr/bin/env python3
"""Ultrathink時間割正しい修正スクリプト - 科目のみをCSVに記載"""

import sys
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkCorrectFixer:
    """正しいCSVフォーマットで時間割を修正するクラス"""
    
    def __init__(self):
        # 交流学級と親学級のマッピング
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組",
        }
        
        # 5組クラス
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        
        # 固定科目
        self.fixed_subjects = {
            "YT", "道", "学", "総", "欠", "行", "テスト", "技家",
            "日生", "作業", "生単", "学総"
        }
    
    def fix_all_violations(self):
        """全ての違反を修正"""
        logger.info("=== Ultrathink正しい修正を開始 ===\n")
        
        # CSVを読み込む
        input_path = project_root / "data" / "output" / "output.csv"
        logger.info(f"時間割を読み込み中: {input_path}")
        
        schedule_data = self.load_csv(input_path)
        
        # まずCSVフォーマットを修正（教師名を除去）
        logger.info("\nPhase 0: CSVフォーマットの修正")
        self.fix_csv_format(schedule_data)
        
        # 各種修正を実行
        logger.info("\nPhase 1: 交流学級の同期")
        self.sync_exchange_classes(schedule_data)
        
        logger.info("\nPhase 2: 5組の同期")
        self.sync_grade5_classes(schedule_data)
        
        logger.info("\nPhase 3: 教師重複の解消（科目を変更）")
        self.fix_teacher_conflicts(schedule_data)
        
        logger.info("\nPhase 4: 体育館使用の最適化")
        self.fix_gym_conflicts(schedule_data)
        
        logger.info("\nPhase 5: 日内重複の修正")
        self.fix_daily_duplicates(schedule_data)
        
        # 結果を保存
        output_path = project_root / "data" / "output" / "output.csv"
        self.save_csv(schedule_data, output_path)
        logger.info(f"\n修正済み時間割を保存: {output_path}")
    
    def load_csv(self, path: Path) -> List[List[str]]:
        """CSVを読み込む"""
        with open(path, 'r', encoding='utf-8-sig') as f:
            return list(csv.reader(f))
    
    def save_csv(self, data: List[List[str]], path: Path):
        """CSVを保存"""
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
    
    def fix_csv_format(self, data: List[List[str]]):
        """CSVフォーマットを修正（教師名を除去）"""
        fixed_count = 0
        
        for row_idx in range(2, len(data)):
            if not data[row_idx][0]:  # 空白行はスキップ
                continue
            
            for col_idx in range(1, len(data[row_idx])):
                cell_value = data[row_idx][col_idx]
                
                if not cell_value or not cell_value.strip():
                    continue
                
                # スペースがある場合、最初の部分（科目）のみを残す
                parts = cell_value.split()
                if len(parts) > 1:
                    data[row_idx][col_idx] = parts[0]
                    fixed_count += 1
        
        logger.info(f"  → {fixed_count}件のセルから教師名を除去")
    
    def sync_exchange_classes(self, data: List[List[str]]):
        """交流学級を親学級と同期"""
        synced_count = 0
        
        # クラス名とその行インデックスのマッピングを作成
        class_row_map = {}
        for row_idx in range(2, len(data)):
            if data[row_idx][0]:
                class_row_map[data[row_idx][0]] = row_idx
        
        # 交流学級を同期
        for exchange_class, parent_class in self.exchange_parent_map.items():
            if exchange_class not in class_row_map or parent_class not in class_row_map:
                continue
            
            exchange_row = class_row_map[exchange_class]
            parent_row = class_row_map[parent_class]
            
            # 各時限をチェック
            for col_idx in range(1, len(data[exchange_row])):
                exchange_cell = data[exchange_row][col_idx]
                parent_cell = data[parent_row][col_idx]
                
                # 自立活動以外で異なる場合は同期
                if exchange_cell and exchange_cell != "自立":
                    if exchange_cell != parent_cell and parent_cell:
                        data[exchange_row][col_idx] = parent_cell
                        synced_count += 1
                elif not exchange_cell and parent_cell:
                    # 交流学級が空きで親学級に授業がある場合
                    data[exchange_row][col_idx] = parent_cell
                    synced_count += 1
        
        logger.info(f"  → {synced_count}件の交流学級を同期")
    
    def sync_grade5_classes(self, data: List[List[str]]):
        """5組クラスを同期"""
        synced_count = 0
        
        # クラス名とその行インデックスのマッピングを作成
        class_row_map = {}
        for row_idx in range(2, len(data)):
            if data[row_idx][0]:
                class_row_map[data[row_idx][0]] = row_idx
        
        # 5組の行インデックスを取得
        grade5_rows = []
        for class_name in self.grade5_classes:
            if class_name in class_row_map:
                grade5_rows.append(class_row_map[class_name])
        
        if len(grade5_rows) != 3:
            return
        
        # 各時限で同期
        for col_idx in range(1, 31):  # 30時限分
            # 3クラスの内容を取得
            cells = [data[row][col_idx] if col_idx < len(data[row]) else "" for row in grade5_rows]
            
            # 最も多い内容を選択（空白でないもの優先）
            non_empty = [c for c in cells if c and c.strip()]
            if non_empty:
                # 最も頻出する内容を選択
                most_common = max(set(non_empty), key=non_empty.count)
                
                # 全クラスを同期
                for row_idx in grade5_rows:
                    if col_idx < len(data[row_idx]) and data[row_idx][col_idx] != most_common:
                        data[row_idx][col_idx] = most_common
                        synced_count += 1
        
        logger.info(f"  → {synced_count}件の5組授業を同期")
    
    def fix_teacher_conflicts(self, data: List[List[str]]):
        """教師重複を解消（同じ教師が複数クラスを担当する場合、科目を変更）"""
        fixed_count = 0
        
        # 科目と教師のマッピング（簡易版）
        subject_teacher = {
            "国": ["寺田", "小野塚", "金子み"],
            "社": ["蒲地", "北"],
            "数": ["梶永", "井上", "森山"],
            "理": ["金子ひ", "智田", "白石"],
            "英": ["井野口", "箱崎", "林田"],
            "音": ["塚本"],
            "美": ["青井", "金子み"],
            "保": ["永山", "野口", "財津"],
            "技": ["林"],
            "家": ["金子み"],
        }
        
        # 各時限で処理
        for col_idx in range(1, 31):  # 30時限分
            # その時限の科目とクラスを収集
            time_slot_assignments = []
            
            for row_idx in range(2, len(data)):
                if not data[row_idx][0] or col_idx >= len(data[row_idx]):
                    continue
                
                cell_value = data[row_idx][col_idx]
                if cell_value and cell_value not in self.fixed_subjects:
                    time_slot_assignments.append((row_idx, data[row_idx][0], cell_value))
            
            # 教師の重複をチェック
            teacher_classes = defaultdict(list)
            for row_idx, class_name, subject in time_slot_assignments:
                # その科目の主担当教師を取得
                if subject in subject_teacher and subject_teacher[subject]:
                    main_teacher = subject_teacher[subject][0]
                    teacher_classes[main_teacher].append((row_idx, class_name, subject))
            
            # 重複を修正
            for teacher, assignments in teacher_classes.items():
                if len(assignments) > 1:
                    # 5組の合同授業は除外
                    grade5_assignments = [(r, c, s) for r, c, s in assignments if c in self.grade5_classes]
                    if len(grade5_assignments) == 3 and len(assignments) == 3:
                        continue
                    
                    # 2番目以降のクラスの科目を変更
                    for row_idx, class_name, subject in assignments[1:]:
                        # その日に不足している科目を探す
                        new_subject = self.find_needed_subject_for_day(data, row_idx, col_idx)
                        if new_subject and new_subject != subject:
                            data[row_idx][col_idx] = new_subject
                            fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の教師重複を解消")
    
    def fix_gym_conflicts(self, data: List[List[str]]):
        """体育館使用の重複を解消"""
        fixed_count = 0
        
        # 各時限で体育の重複をチェック
        for col_idx in range(1, 31):  # 30時限分
            pe_classes = []
            
            # 体育を行っているクラスを収集
            for row_idx in range(2, len(data)):
                if not data[row_idx][0] or col_idx >= len(data[row_idx]):
                    continue
                
                cell_value = data[row_idx][col_idx]
                if cell_value == "保":
                    pe_classes.append((row_idx, data[row_idx][0]))
            
            # 正常なケースを除外
            remaining = list(pe_classes)
            
            # 5組合同
            grade5_pe = [(r, c) for r, c in pe_classes if c in self.grade5_classes]
            if len(grade5_pe) == 3:
                for item in grade5_pe:
                    if item in remaining:
                        remaining.remove(item)
            
            # 親・交流ペア
            for exchange, parent in self.exchange_parent_map.items():
                exchange_item = next((item for item in remaining if item[1] == exchange), None)
                parent_item = next((item for item in remaining if item[1] == parent), None)
                
                if exchange_item and parent_item:
                    remaining.remove(exchange_item)
                    remaining.remove(parent_item)
            
            # 残りが2つ以上の場合は修正
            if len(remaining) >= 2:
                # 最初のクラス以外を他の科目に変更
                for row_idx, class_name in remaining[1:]:
                    # その日に不足している科目を探す
                    new_subject = self.find_needed_subject_for_day(data, row_idx, col_idx)
                    if new_subject:
                        data[row_idx][col_idx] = new_subject
                        fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の体育館使用を最適化")
    
    def fix_daily_duplicates(self, data: List[List[str]]):
        """日内重複を修正"""
        fixed_count = 0
        
        # 各クラスの各日をチェック
        for row_idx in range(2, len(data)):
            if not data[row_idx][0]:
                continue
            
            class_name = data[row_idx][0]
            
            # 各日（月〜金）
            for day_idx in range(5):
                day_start = day_idx * 6 + 1
                day_end = day_start + 6
                
                # その日の科目をカウント
                subject_positions = defaultdict(list)
                
                for col_idx in range(day_start, min(day_end, len(data[row_idx]))):
                    cell_value = data[row_idx][col_idx]
                    if cell_value and cell_value not in self.fixed_subjects:
                        subject_positions[cell_value].append(col_idx)
                
                # 重複を修正
                for subject, positions in subject_positions.items():
                    if len(positions) > 1:
                        # 2つ目以降を変更
                        for col_idx in positions[1:]:
                            # その日に不足している科目を探す
                            new_subject = self.find_needed_subject_for_day(data, row_idx, col_idx)
                            if new_subject and new_subject != subject:
                                data[row_idx][col_idx] = new_subject
                                fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の日内重複を修正")
    
    def find_needed_subject_for_day(self, data: List[List[str]], row_idx: int,
                                  current_col: int) -> Optional[str]:
        """その日に必要な科目を探す"""
        # その日の科目を収集
        day_idx = (current_col - 1) // 6
        day_start = day_idx * 6 + 1
        day_end = day_start + 6
        
        day_subjects = set()
        for col_idx in range(day_start, min(day_end, len(data[row_idx]))):
            cell_value = data[row_idx][col_idx]
            if cell_value:
                day_subjects.add(cell_value)
        
        # 主要5教科を優先
        for subject in ["国", "数", "英", "理", "社"]:
            if subject not in day_subjects:
                return subject
        
        # 技能教科
        for subject in ["音", "美", "技", "家"]:
            if subject not in day_subjects:
                return subject
        
        # 保健体育（体育館が空いていれば）
        if "保" not in day_subjects:
            return "保"
        
        return None


def main():
    """メイン処理"""
    fixer = UltrathinkCorrectFixer()
    fixer.fix_all_violations()


if __name__ == "__main__":
    main()