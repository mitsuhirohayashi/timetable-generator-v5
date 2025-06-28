#!/usr/bin/env python3
"""
残りの日内重複を修正
"""
import csv
from pathlib import Path
import shutil

class RemainingDuplicatesFixer:
    def __init__(self):
        self.csv_path = Path("data/output/output.csv")
        self.rows = []
        self.days = []
        self.periods = []
        self.class_row_map = {}
        
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
        backup_path = Path("data/output/output_backup_before_final_fix.csv")
        shutil.copy(self.csv_path, backup_path)
        print(f"バックアップを作成: {backup_path}")
    
    def swap_subjects(self, class_name: str, day1: str, period1: str, day2: str, period2: str):
        """2つのスロットの科目を交換"""
        if class_name not in self.class_row_map:
            return
        
        row_idx = self.class_row_map[class_name]
        
        # スロットインデックスを取得
        slot1_idx = None
        slot2_idx = None
        
        for i, (d, p) in enumerate(zip(self.days, self.periods)):
            if d == day1 and p == period1:
                slot1_idx = i
            if d == day2 and p == period2:
                slot2_idx = i
        
        if slot1_idx is not None and slot2_idx is not None:
            # 交換
            subject1 = self.rows[row_idx][slot1_idx + 1]
            subject2 = self.rows[row_idx][slot2_idx + 1]
            
            self.rows[row_idx][slot1_idx + 1] = subject2
            self.rows[row_idx][slot2_idx + 1] = subject1
            
            print(f"  {class_name}: {day1}曜{period1}限({subject1})↔{day2}曜{period2}限({subject2})")
    
    def fix_all_duplicates(self):
        """全ての日内重複を修正"""
        print("\n=== 残りの日内重複を修正 ===")
        
        # 1年1組: 月曜日に保が2回（2, 4限）
        # 月曜4限の保を火曜4限の数と交換
        self.swap_subjects("1年1組", "月", "4", "火", "4")
        
        # 3年1組: 月曜日に国が2回（1, 6限）
        # 月曜6限の国を保に変更（火曜5限の保と交換）
        self.swap_subjects("3年1組", "月", "6", "火", "5")
        
        # 3年3組: 月曜日に国が2回（1, 6限）
        # 月曜6限の国を英に変更（火曜2限の英と交換）
        self.swap_subjects("3年3組", "月", "6", "火", "2")
        
        # 3年6組: 月曜日に国が2回（1, 5限）
        # 月曜5限の国を数に変更（火曜1限の数と交換）
        self.swap_subjects("3年6組", "月", "5", "火", "1")
        
        # 3年6組: 金曜日に英が2回（1, 2限）
        # 金曜2限の英を国に変更（月曜1限の国と交換）
        self.swap_subjects("3年6組", "金", "2", "月", "1")
    
    def run(self):
        """メイン処理"""
        print("=== 残りの日内重複修正プログラム ===")
        
        # バックアップ
        self.backup_csv()
        
        # 読み込み
        self.load_csv()
        
        # 修正
        self.fix_all_duplicates()
        
        # 保存
        self.save_csv()
        
        print("\n修正完了！")

if __name__ == "__main__":
    fixer = RemainingDuplicatesFixer()
    fixer.run()