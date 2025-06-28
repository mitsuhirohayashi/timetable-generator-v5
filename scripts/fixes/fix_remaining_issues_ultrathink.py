#!/usr/bin/env python3
"""
Ultrathink: 残存エラーの修正
- 水曜5限の体育館重複（2年1組と2年2組）
- 小野塚先生の火曜不在違反
"""
import csv
from pathlib import Path

class RemainingIssueFixer:
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
    
    def get_slot_index(self, day: str, period: str) -> int:
        """曜日と時限からスロットインデックスを取得"""
        for i, (d, p) in enumerate(zip(self.days, self.periods)):
            if d == day and p == period:
                return i
        return -1
    
    def fix_wednesday_pe_conflict(self):
        """水曜5限の体育館重複を修正"""
        print("\n=== 水曜5限の体育館重複修正 ===")
        
        # 2年2組の体育を移動
        class_name = "2年2組"
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        
        # 水曜5限のインデックス
        wed5_idx = self.get_slot_index("水", "5")
        
        print(f"現在の{class_name}の水曜5限: {schedule[wed5_idx]}")
        
        # 適切な移動先を探す
        # 木曜5限の数学と交換（日内重複を避ける）
        thu5_idx = self.get_slot_index("木", "5")
        if schedule[thu5_idx] == "数":
            # 木曜に数学が既にあるかチェック
            thu_subjects = [schedule[i] for i, d in enumerate(self.days) if d == "木"]
            if thu_subjects.count("数") == 1:
                # スワップ実行
                self.rows[row_idx][wed5_idx + 1] = "数"
                self.rows[row_idx][thu5_idx + 1] = "保"
                print(f"→ {class_name}の保体を木曜5限に移動（数と交換）")
                
                # 交流学級（2年7組）も同期
                exchange_row_idx = self.class_row_map["2年7組"]
                exchange_schedule = self.rows[exchange_row_idx][1:]
                if exchange_schedule[wed5_idx] != "自立":
                    self.rows[exchange_row_idx][wed5_idx + 1] = "数"
                if exchange_schedule[thu5_idx] != "自立":
                    self.rows[exchange_row_idx][thu5_idx + 1] = "保"
                return True
        
        return False
    
    def fix_onozuka_tuesday_conflicts(self):
        """小野塚先生の火曜不在違反を修正"""
        print("\n=== 小野塚先生の火曜不在違反修正 ===")
        
        # 2年2組の火曜1限の国語を移動
        self.fix_onozuka_class("2年2組", "火", "1", "国")
        
        # 2年3組の火曜1限の国語を移動
        self.fix_onozuka_class("2年3組", "火", "1", "国")
    
    def fix_onozuka_class(self, class_name: str, conflict_day: str, conflict_period: str, subject: str):
        """小野塚先生の授業を移動"""
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        conflict_slot = self.get_slot_index(conflict_day, conflict_period)
        
        print(f"\n{class_name}の{conflict_day}曜{conflict_period}限の{subject}を移動:")
        
        # 金曜4限の総合と交換（固定科目でないことを確認）
        fri4_idx = self.get_slot_index("金", "4")
        if schedule[fri4_idx] == "総":
            # 金曜に国語がないことを確認
            fri_subjects = [schedule[i] for i, d in enumerate(self.days) if d == "金"]
            if "国" not in fri_subjects:
                # スワップ実行
                self.rows[row_idx][conflict_slot + 1] = "総"
                self.rows[row_idx][fri4_idx + 1] = "国"
                print(f"→ 国語を金曜4限に移動（総と交換）")
                
                # 交流学級も同期
                if class_name == "2年2組":
                    exchange_class = "2年7組"
                elif class_name == "2年3組":
                    exchange_class = "2年6組"
                else:
                    return
                
                if exchange_class in self.class_row_map:
                    exchange_row_idx = self.class_row_map[exchange_class]
                    exchange_schedule = self.rows[exchange_row_idx][1:]
                    if exchange_schedule[conflict_slot] != "自立":
                        self.rows[exchange_row_idx][conflict_slot + 1] = "総"
                    if exchange_schedule[fri4_idx] != "自立":
                        self.rows[exchange_row_idx][fri4_idx + 1] = "国"
    
    def save_csv(self):
        """修正した時間割を保存"""
        with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(self.rows)
    
    def run(self):
        """メイン処理"""
        print("=== Ultrathink 残存エラー修正 ===")
        
        # データ読み込み
        self.load_csv()
        
        # 修正実行
        self.fix_wednesday_pe_conflict()
        self.fix_onozuka_tuesday_conflicts()
        
        # 保存
        self.save_csv()
        
        print("\n=== 修正完了 ===")

if __name__ == "__main__":
    fixer = RemainingIssueFixer()
    fixer.run()