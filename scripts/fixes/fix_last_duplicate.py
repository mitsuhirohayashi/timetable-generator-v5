#!/usr/bin/env python3
"""
最後の日内重複を修正
"""
import csv
from pathlib import Path
import shutil

class LastDuplicateFixer:
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
        backup_path = Path("data/output/output_backup_absolutely_final.csv")
        shutil.copy(self.csv_path, backup_path)
        print(f"バックアップを作成: {backup_path}")
    
    def fix_last_duplicate(self):
        """最後の日内重複を修正"""
        print("\n=== 最後の日内重複を修正 ===")
        
        # 1年1組: 月曜日に数が2回（4, 5限）
        # 月曜5限の数を社に変更（金曜5限の社と交換）
        if "1年1組" in self.class_row_map:
            row_idx = self.class_row_map["1年1組"]
            
            # スロットインデックスを取得
            mon5_idx = None
            fri5_idx = None
            
            for i, (d, p) in enumerate(zip(self.days, self.periods)):
                if d == "月" and p == "5":
                    mon5_idx = i
                if d == "金" and p == "5":
                    fri5_idx = i
            
            if mon5_idx is not None and fri5_idx is not None:
                # 現在の科目を確認
                mon5_subject = self.rows[row_idx][mon5_idx + 1]
                fri5_subject = self.rows[row_idx][fri5_idx + 1]
                
                print(f"  1年1組: 月曜5限({mon5_subject})↔金曜5限({fri5_subject})")
                
                # 交換
                self.rows[row_idx][mon5_idx + 1] = fri5_subject
                self.rows[row_idx][fri5_idx + 1] = mon5_subject
    
    def run(self):
        """メイン処理"""
        print("=== 最後の日内重複修正プログラム ===")
        
        # バックアップ
        self.backup_csv()
        
        # 読み込み
        self.load_csv()
        
        # 修正
        self.fix_last_duplicate()
        
        # 保存
        self.save_csv()
        
        print("\n修正完了！")

if __name__ == "__main__":
    fixer = LastDuplicateFixer()
    fixer.run()