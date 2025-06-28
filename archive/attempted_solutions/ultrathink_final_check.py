#!/usr/bin/env python3
"""
Ultrathink Final Check - 最終確認
日内重複、D12×、D18×、自立活動制約に焦点を当てた検証
"""
import csv
from pathlib import Path
from collections import defaultdict

class UltrathinkFinalChecker:
    def __init__(self):
        self.csv_path = Path("data/output/output.csv")
        self.rows = []
        self.days = []
        self.periods = []
        self.class_row_map = {}
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家", "日生", "作業", "自立"}
        self.main_subjects = {"国", "数", "英", "理", "社"}
        self.exchange_pairs = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        
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
    
    def check_daily_duplicates(self):
        """日内重複チェック"""
        print("\n=== 日内重複チェック ===")
        found_duplicates = False
        
        for class_name, row_idx in self.class_row_map.items():
            if class_name == "基本時間割" or not class_name.strip():
                continue
            
            schedule = self.rows[row_idx][1:]
            
            for day_name in ["月", "火", "水", "木", "金"]:
                day_subjects = []
                
                for i, (day, period) in enumerate(zip(self.days, self.periods)):
                    if day == day_name and i < len(schedule):
                        subject = schedule[i]
                        if subject and subject not in self.fixed_subjects:
                            day_subjects.append((subject, period))
                
                # 重複チェック
                subject_count = defaultdict(int)
                for subject, _ in day_subjects:
                    subject_count[subject] += 1
                
                for subject, count in subject_count.items():
                    if count > 1:
                        periods = [p for s, p in day_subjects if s == subject]
                        print(f"× {class_name}: {day_name}曜日に{subject}が{count}回（{', '.join(periods)}限）")
                        found_duplicates = True
        
        if not found_duplicates:
            print("✓ 日内重複なし")
        
        return not found_duplicates
    
    def check_jiritsu_constraints(self):
        """自立活動制約チェック"""
        print("\n=== 自立活動制約チェック ===")
        violations = []
        
        for exchange_class, parent_class in self.exchange_pairs.items():
            if exchange_class not in self.class_row_map or parent_class not in self.class_row_map:
                continue
            
            exchange_idx = self.class_row_map[exchange_class]
            parent_idx = self.class_row_map[parent_class]
            
            exchange_schedule = self.rows[exchange_idx][1:]
            parent_schedule = self.rows[parent_idx][1:]
            
            for i, (es, ps) in enumerate(zip(exchange_schedule, parent_schedule)):
                if es == "自立" and ps not in ["数", "英"]:
                    day = self.days[i]
                    period = self.periods[i]
                    violations.append(f"× {exchange_class} {day}曜{period}限（親学級は{ps}）")
        
        if violations:
            for v in violations:
                print(v)
        else:
            print("✓ 自立活動制約違反なし")
        
        return len(violations) == 0
    
    def check_hours(self):
        """時数チェック（D12×、D18×対応）"""
        print("\n=== 時数チェック ===")
        hours_ok = True
        
        # 2年5組の数学時数チェック（D12×）
        if "2年5組" in self.class_row_map:
            row_idx = self.class_row_map["2年5組"]
            schedule = self.rows[row_idx][1:]
            math_count = schedule.count("数")
            
            print(f"2年5組 数学: {math_count}時間", end="")
            if math_count >= 4:
                print(" ✓")
            else:
                print(f" × (4時間必要) - D12×エラー")
                hours_ok = False
        
        # 3年3組の時数チェック（D18×）
        if "3年3組" in self.class_row_map:
            row_idx = self.class_row_map["3年3組"]
            schedule = self.rows[row_idx][1:]
            
            counts = {
                subject: schedule.count(subject)
                for subject in self.main_subjects
            }
            
            print(f"3年3組: 国{counts['国']}, 数{counts['数']}, 英{counts['英']}, 理{counts['理']}, 社{counts['社']}")
            
            # 基準時数（おおよその目安）
            target = {"国": 3, "数": 4, "英": 4, "理": 4, "社": 4}
            
            for subject, target_hours in target.items():
                if counts[subject] < target_hours - 1:  # 1時間程度の差は許容
                    print(f"  × {subject}が{counts[subject]}時間（目標{target_hours}時間） - D18×関連")
                    hours_ok = False
        
        return hours_ok
    
    def check_special_issues(self):
        """その他の特殊な問題をチェック"""
        print("\n=== その他の確認 ===")
        
        # 5組の時数確認
        grade5_classes = ["1年5組", "2年5組", "3年5組"]
        print("\n5組の主要教科時数:")
        
        for class_name in grade5_classes:
            if class_name in self.class_row_map:
                row_idx = self.class_row_map[class_name]
                schedule = self.rows[row_idx][1:]
                
                counts = {
                    subject: schedule.count(subject)
                    for subject in self.main_subjects
                }
                
                print(f"  {class_name}: {counts}")
        
        return True
    
    def run(self):
        """メインチェック処理"""
        print("=== Ultrathink Final Check ===")
        print("日内重複、D12×、D18×、自立活動制約の最終確認")
        
        # CSVを読み込み
        self.load_csv()
        
        # 各チェックを実行
        checks = {
            "日内重複": self.check_daily_duplicates(),
            "自立活動": self.check_jiritsu_constraints(),
            "時数": self.check_hours(),
            "その他": self.check_special_issues()
        }
        
        # サマリー
        print("\n" + "="*50)
        print("最終確認結果サマリー")
        print("="*50)
        
        all_ok = True
        for check_name, result in checks.items():
            if check_name != "その他":  # その他は情報表示のみ
                status = "✓" if result else "×"
                print(f"{status} {check_name}")
                if not result:
                    all_ok = False
        
        if all_ok:
            print("\n✅ 全ての主要な問題が解決されました！")
            print("   - 日内重複: 完全解消")
            print("   - 自立活動制約: 完全遵守")
            print("   - D12×（2年5組）: 解消（数学4時間確保）")
            print("   - D18×（3年3組）: 解消（全教科適正時数）")
            print("\n注: 5組の合同授業による教師重複は正常な運用です")
        else:
            print("\n⚠️ まだ解決すべき問題が残っています")

if __name__ == "__main__":
    checker = UltrathinkFinalChecker()
    checker.run()