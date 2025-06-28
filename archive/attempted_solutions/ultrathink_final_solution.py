#!/usr/bin/env python3
"""
Ultrathink Final Solution - 最終解決策
慎重に各スロットを確認しながら修正
"""
import csv
from pathlib import Path
import shutil
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional

class UltrathinkFinalSolution:
    def __init__(self):
        self.csv_path = Path("data/output/output.csv")
        self.rows = []
        self.days = []
        self.periods = []
        self.class_row_map = {}
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家", "日生", "作業", "自立"}
        self.modifications = []
        
    def load_csv(self):
        """CSVファイルを読み込み"""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            self.rows = list(reader)
        
        self.days = self.rows[0][1:]
        self.periods = self.rows[1][1:]
        
        for i, row in enumerate(self.rows):
            if row and row[0] and row[0].strip():
                self.class_row_map[row[0]] = i
    
    def save_csv(self):
        """CSVファイルを保存"""
        with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(self.rows)
    
    def backup_csv(self):
        """バックアップを作成"""
        backup_path = Path("data/output/output_backup_ultrathink_final.csv")
        shutil.copy(self.csv_path, backup_path)
        print(f"バックアップを作成: {backup_path}")
    
    def get_day_subjects(self, class_name: str, day_name: str) -> Dict[str, List[int]]:
        """特定の曜日の科目と時限を取得"""
        if class_name not in self.class_row_map:
            return {}
        
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        subject_slots = defaultdict(list)
        
        for i, (day, period) in enumerate(zip(self.days, self.periods)):
            if day == day_name and i < len(schedule):
                subject = schedule[i]
                if subject and subject not in self.fixed_subjects:
                    subject_slots[subject].append(i)
        
        return subject_slots
    
    def get_available_subjects(self, class_name: str, day_name: str, 
                             exclude_subjects: Set[str]) -> List[str]:
        """その曜日に配置可能な科目を取得"""
        if class_name not in self.class_row_map:
            return []
        
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        
        # 全体のスケジュールから利用可能な科目を収集
        all_subjects = set()
        for subject in schedule:
            if subject and subject not in self.fixed_subjects:
                all_subjects.add(subject)
        
        # その曜日に既にある科目を除外
        day_subjects = self.get_day_subjects(class_name, day_name)
        available = []
        
        for subject in all_subjects:
            if subject not in exclude_subjects and subject not in day_subjects:
                available.append(subject)
        
        return available
    
    def swap_subjects(self, class_name: str, slot1: int, slot2: int):
        """2つのスロットの科目を交換"""
        if class_name not in self.class_row_map:
            return
        
        row_idx = self.class_row_map[class_name]
        
        # 交換
        subject1 = self.rows[row_idx][slot1 + 1]
        subject2 = self.rows[row_idx][slot2 + 1]
        
        self.rows[row_idx][slot1 + 1] = subject2
        self.rows[row_idx][slot2 + 1] = subject1
        
        day1 = self.days[slot1]
        period1 = self.periods[slot1]
        day2 = self.days[slot2]
        period2 = self.periods[slot2]
        
        mod = f"{class_name}: {day1}曜{period1}限({subject1})↔{day2}曜{period2}限({subject2})"
        self.modifications.append(mod)
        print(f"  {mod}")
    
    def fix_duplicates_carefully(self):
        """慎重に日内重複を修正"""
        print("\n=== 日内重複の慎重な修正 ===")
        
        # 現在の重複状況を確認
        duplicate_info = []
        
        for class_name, row_idx in self.class_row_map.items():
            if class_name == "基本時間割" or not class_name.strip():
                continue
            
            for day_name in ["月", "火", "水", "木", "金"]:
                day_subjects = self.get_day_subjects(class_name, day_name)
                
                for subject, slots in day_subjects.items():
                    if len(slots) > 1:
                        duplicate_info.append((class_name, day_name, subject, slots))
        
        # 各重複を個別に処理
        for class_name, day_name, subject, slots in duplicate_info:
            print(f"\n{class_name} {day_name}曜日の{subject}重複:")
            
            # 最初の出現は保持
            keep_slot = slots[0]
            
            for duplicate_slot in slots[1:]:
                # 他の曜日で交換可能なスロットを探す
                found_swap = False
                
                # 他の曜日を検索
                for other_day in ["月", "火", "水", "木", "金"]:
                    if other_day == day_name:
                        continue
                    
                    # その曜日の科目を取得
                    other_day_subjects = self.get_day_subjects(class_name, other_day)
                    
                    # 交換候補を探す
                    for other_subject, other_slots in other_day_subjects.items():
                        # この科目が元の曜日にない場合
                        if other_subject not in self.get_day_subjects(class_name, day_name):
                            # 交換実行
                            self.swap_subjects(class_name, duplicate_slot, other_slots[0])
                            found_swap = True
                            break
                    
                    if found_swap:
                        break
                
                if not found_swap:
                    print(f"  警告: {day_name}曜{self.periods[duplicate_slot]}限の交換相手が見つかりません")
    
    def fix_jiritsu_constraints(self):
        """自立活動制約を修正"""
        print("\n=== 自立活動制約の修正 ===")
        
        exchange_pairs = {
            "1年7組": "1年2組",
            "2年7組": "2年2組",
        }
        
        for exchange_class, parent_class in exchange_pairs.items():
            if exchange_class not in self.class_row_map or parent_class not in self.class_row_map:
                continue
            
            exchange_idx = self.class_row_map[exchange_class]
            parent_idx = self.class_row_map[parent_class]
            
            exchange_schedule = self.rows[exchange_idx][1:]
            
            for i, subject in enumerate(exchange_schedule):
                if subject == "自立":
                    parent_subject = self.rows[parent_idx][i + 1]
                    
                    if parent_subject not in ["数", "英"]:
                        # 親学級を数学か英語に変更する必要がある
                        day = self.days[i]
                        period = self.periods[i]
                        
                        # その曜日の他の時限で数学か英語を探す
                        found_swap = False
                        
                        for j, (d, p) in enumerate(zip(self.days, self.periods)):
                            if d == day and j != i:
                                other_subject = self.rows[parent_idx][j + 1]
                                if other_subject in ["数", "英"]:
                                    # 交換
                                    self.swap_subjects(parent_class, i, j)
                                    found_swap = True
                                    break
                        
                        if not found_swap:
                            # 他の曜日から数学か英語を持ってくる
                            for j, subject_j in enumerate(self.rows[parent_idx][1:]):
                                if subject_j in ["数", "英"]:
                                    self.swap_subjects(parent_class, i, j)
                                    break
    
    def verify_and_summary(self):
        """最終検証とサマリー"""
        print("\n=== 最終検証 ===")
        
        # 日内重複チェック
        print("\n1. 日内重複:")
        has_duplicates = False
        
        for class_name, row_idx in self.class_row_map.items():
            if class_name == "基本時間割" or not class_name.strip():
                continue
            
            for day_name in ["月", "火", "水", "木", "金"]:
                day_subjects = self.get_day_subjects(class_name, day_name)
                
                for subject, slots in day_subjects.items():
                    if len(slots) > 1:
                        periods = [self.periods[s] for s in slots]
                        print(f"  × {class_name}: {day_name}曜日に{subject}が{len(slots)}回（{', '.join(periods)}限）")
                        has_duplicates = True
        
        if not has_duplicates:
            print("  ✓ 日内重複なし")
        
        # 時数チェック
        print("\n2. 時数:")
        for class_name in ["2年5組", "3年3組"]:
            if class_name in self.class_row_map:
                row = self.class_row_map[class_name]
                schedule = self.rows[row][1:]
                
                counts = {
                    "国": schedule.count("国"),
                    "数": schedule.count("数"),
                    "英": schedule.count("英"),
                    "理": schedule.count("理"),
                    "社": schedule.count("社")
                }
                
                print(f"  {class_name}: {counts}")
    
    def run(self):
        """メイン処理"""
        print("=== Ultrathink Final Solution ===")
        print("最終的な解決策を実行します")
        
        # バックアップ
        self.backup_csv()
        
        # 読み込み
        self.load_csv()
        
        # 修正実行
        self.fix_duplicates_carefully()
        self.fix_jiritsu_constraints()
        
        # 保存
        self.save_csv()
        
        # 検証とサマリー
        self.verify_and_summary()
        
        print(f"\n実施した修正: {len(self.modifications)}件")
        if self.modifications:
            for i, mod in enumerate(self.modifications[:10], 1):  # 最初の10件のみ表示
                print(f"  {i}. {mod}")
            if len(self.modifications) > 10:
                print(f"  ... 他 {len(self.modifications) - 10}件")

if __name__ == "__main__":
    fixer = UltrathinkFinalSolution()
    fixer.run()