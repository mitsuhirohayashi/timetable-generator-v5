#!/usr/bin/env python3
"""
自立活動制約違反を修正
"""
import csv
from pathlib import Path
import shutil

class JiritsuViolationFixer:
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
        backup_path = Path("data/output/output_backup_jiritsu_fix.csv")
        shutil.copy(self.csv_path, backup_path)
        print(f"バックアップを作成: {backup_path}")
    
    def fix_jiritsu_violation(self):
        """自立活動制約違反を修正"""
        print("\n=== 自立活動制約違反を修正 ===")
        
        # 1年6組 月曜5限（親学級1年1組は国）
        # 1年1組の月曜5限を数学に変更（金曜5限の数と交換）
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
                
                # 交換（月曜5限を数に、金曜5限を国に）
                self.rows[row_idx][mon5_idx + 1] = fri5_subject
                self.rows[row_idx][fri5_idx + 1] = mon5_subject
    
    def run(self):
        """メイン処理"""
        print("=== 自立活動制約違反修正プログラム ===")
        
        # バックアップ
        self.backup_csv()
        
        # 読み込み
        self.load_csv()
        
        # 修正
        self.fix_jiritsu_violation()
        
        # 保存
        self.save_csv()
        
        print("\n修正完了！")

if __name__ == "__main__":
    fixer = JiritsuViolationFixer()
    fixer.run()