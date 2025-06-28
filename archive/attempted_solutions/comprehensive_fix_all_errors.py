#!/usr/bin/env python3
"""
日内重複とD12×、D18×エラーを包括的に解消
ultrathinkモードで慎重に設計
"""
import csv
from pathlib import Path
import shutil
from collections import defaultdict
import copy

class ComprehensiveScheduleFixer:
    def __init__(self):
        self.csv_path = Path("data/output/output.csv")
        self.rows = []
        self.days = []
        self.periods = []
        self.class_row_map = {}
        self.exchange_pairs = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家"}
        
        # 標準時数要件（主要教科のみ）
        self.standard_hours = {
            "1年": {"国": 4, "社": 3, "数": 4, "理": 3, "英": 4},
            "2年": {"国": 4, "社": 3, "数": 3, "理": 4, "英": 4},
            "3年": {"国": 3, "社": 4, "数": 4, "理": 4, "英": 4},
            "1年5組": {"国": 4, "社": 1, "数": 4, "理": 3, "英": 2},
            "2年5組": {"国": 4, "社": 1, "数": 4, "理": 3, "英": 2},
            "3年5組": {"国": 4, "社": 1, "数": 4, "理": 3, "英": 2}
        }
    
    def load_csv(self):
        """CSVファイルを読み込み"""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            self.rows = list(reader)
        
        self.days = self.rows[0][1:]
        self.periods = self.rows[1][1:]
        
        # クラス名と行番号のマッピング
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
        backup_path = Path("data/output/output_backup_comprehensive.csv")
        shutil.copy(self.csv_path, backup_path)
        print(f"バックアップを作成: {backup_path}")
    
    def get_time_index(self, day, period):
        """曜日と時限から列インデックスを取得"""
        for i, (d, p) in enumerate(zip(self.days, self.periods)):
            if d == day and p == period:
                return i + 1  # +1はクラス名列のため
        return None
    
    def get_class_schedule(self, class_name):
        """クラスの時間割を取得"""
        if class_name in self.class_row_map:
            row_idx = self.class_row_map[class_name]
            return self.rows[row_idx][1:]
        return None
    
    def detect_daily_duplicates(self, class_name):
        """日内重複を検出"""
        schedule = self.get_class_schedule(class_name)
        if not schedule:
            return []
        
        duplicates = []
        day_subjects = defaultdict(list)
        
        for i, (day, period, subject) in enumerate(zip(self.days, self.periods, schedule)):
            if subject and subject not in self.fixed_subjects:
                day_subjects[day].append((period, subject, i))
        
        for day, subjects in day_subjects.items():
            subject_count = defaultdict(list)
            for period, subject, idx in subjects:
                subject_count[subject].append((period, idx))
            
            for subject, occurrences in subject_count.items():
                if len(occurrences) > 1:
                    duplicates.append({
                        'day': day,
                        'subject': subject,
                        'periods': [p for p, _ in occurrences],
                        'indices': [idx for _, idx in occurrences]
                    })
        
        return duplicates
    
    def count_subject_hours(self, class_name):
        """教科別時数をカウント"""
        schedule = self.get_class_schedule(class_name)
        if not schedule:
            return {}
        
        subject_count = defaultdict(int)
        for subject in schedule:
            if subject and subject not in self.fixed_subjects:
                subject_count[subject] += 1
        
        return subject_count
    
    def find_swappable_slot(self, class_name, target_day, exclude_subject, need_subject=None):
        """交換可能なスロットを探す"""
        schedule = self.get_class_schedule(class_name)
        if not schedule:
            return None
        
        row_idx = self.class_row_map[class_name]
        
        # 同じ曜日の他の時限を探す
        for i, (day, period, subject) in enumerate(zip(self.days, self.periods, schedule)):
            if day == target_day and subject != exclude_subject:
                if subject not in self.fixed_subjects:
                    # need_subjectが指定されている場合はそれを優先
                    if need_subject and subject == need_subject:
                        return i
                    elif not need_subject:
                        # 重複チェック
                        temp_schedule = schedule[:]
                        temp_schedule[i] = exclude_subject
                        if not self.would_create_duplicate(temp_schedule, target_day):
                            return i
        
        return None
    
    def would_create_duplicate(self, schedule, day):
        """スケジュール変更が重複を作るか確認"""
        day_subjects = []
        for i, (d, p, s) in enumerate(zip(self.days, self.periods, schedule)):
            if d == day and s and s not in self.fixed_subjects:
                day_subjects.append(s)
        
        return len(day_subjects) != len(set(day_subjects))
    
    def fix_daily_duplicates(self):
        """全ての日内重複を修正"""
        print("\n=== 日内重複の修正 ===")
        fixes = []
        
        # 各クラスの重複を修正
        for class_name in ["1年1組", "3年1組", "3年3組", "3年6組"]:
            if class_name not in self.class_row_map:
                continue
            
            duplicates = self.detect_daily_duplicates(class_name)
            row_idx = self.class_row_map[class_name]
            
            for dup in duplicates:
                day = dup['day']
                subject = dup['subject']
                indices = dup['indices']
                
                print(f"\n{class_name}: {day}曜日の{subject}重複を修正")
                
                # 最初の出現以外を他の科目と交換
                for i in range(1, len(indices)):
                    idx = indices[i]
                    period = self.periods[idx]
                    
                    # 交換先を探す
                    swap_idx = self.find_swappable_slot(class_name, day, subject)
                    if swap_idx is not None and swap_idx + 1 < len(self.rows[row_idx]):
                        # 交換実行
                        col1 = idx + 1
                        col2 = swap_idx + 1
                        original = self.rows[row_idx][col2]
                        self.rows[row_idx][col1], self.rows[row_idx][col2] = \
                            self.rows[row_idx][col2], self.rows[row_idx][col1]
                        
                        fixes.append(f"{class_name}: {day}曜{period}限の{subject}と{day}曜{self.periods[swap_idx]}限の{original}を交換")
                        print(f"  {day}曜{period}限（{subject}）↔ {day}曜{self.periods[swap_idx]}限（{original}）")
        
        return fixes
    
    def fix_hours_shortage(self):
        """時数不足を修正（D12×、D18×対応）"""
        print("\n=== 時数不足の修正 ===")
        fixes = []
        
        # 2年5組（行12）の確認と修正
        if "2年5組" in self.class_row_map:
            class_name = "2年5組"
            subject_count = self.count_subject_hours(class_name)
            required = self.standard_hours.get(class_name, {})
            
            for subject, req_hours in required.items():
                current = subject_count.get(subject, 0)
                if current < req_hours:
                    shortage = req_hours - current
                    print(f"\n{class_name}: {subject}が{shortage}時間不足")
                    
                    # 不足分を補充
                    row_idx = self.class_row_map[class_name]
                    schedule = self.get_class_schedule(class_name)
                    
                    for i, s in enumerate(schedule):
                        if shortage == 0:
                            break
                        # 作業、美術、音楽などを主要教科に置き換え
                        if s in ["作業", "美", "音", "技", "家", "保"] and s not in self.fixed_subjects:
                            self.rows[row_idx][i+1] = subject
                            fixes.append(f"{class_name}: {self.days[i]}曜{self.periods[i]}限を{s}→{subject}")
                            print(f"  {self.days[i]}曜{self.periods[i]}限: {s}→{subject}")
                            shortage -= 1
        
        # 3年3組（行18）の確認と修正
        if "3年3組" in self.class_row_map:
            class_name = "3年3組"
            subject_count = self.count_subject_hours(class_name)
            required = {"国": 3, "社": 4, "数": 4, "理": 4, "英": 4}
            
            for subject, req_hours in required.items():
                current = subject_count.get(subject, 0)
                if current < req_hours:
                    shortage = req_hours - current
                    print(f"\n{class_name}: {subject}が{shortage}時間不足")
                    
                    # 社会が多い場合は社会と交換
                    row_idx = self.class_row_map[class_name]
                    schedule = self.get_class_schedule(class_name)
                    
                    if subject_count.get("社", 0) > required.get("社", 0):
                        for i, s in enumerate(schedule):
                            if shortage == 0:
                                break
                            if s == "社":
                                self.rows[row_idx][i+1] = subject
                                fixes.append(f"{class_name}: {self.days[i]}曜{self.periods[i]}限を社→{subject}")
                                print(f"  {self.days[i]}曜{self.periods[i]}限: 社→{subject}")
                                shortage -= 1
                                break
        
        return fixes
    
    def verify_all_constraints(self):
        """全ての制約を検証"""
        print("\n=== 最終検証 ===")
        all_good = True
        
        # 1. 自立活動制約
        print("\n1. 自立活動制約:")
        violations = 0
        for exchange_class, parent_class in self.exchange_pairs.items():
            if exchange_class not in self.class_row_map or parent_class not in self.class_row_map:
                continue
            
            exchange_schedule = self.get_class_schedule(exchange_class)
            parent_schedule = self.get_class_schedule(parent_class)
            
            for i, (es, ps) in enumerate(zip(exchange_schedule, parent_schedule)):
                if es == "自立" and ps not in ["数", "英"]:
                    print(f"  × {exchange_class} {self.days[i]}曜{self.periods[i]}限（親学級は{ps}）")
                    violations += 1
                    all_good = False
        
        if violations == 0:
            print("  ✓ 違反なし")
        
        # 2. 日内重複
        print("\n2. 日内重複:")
        dup_count = 0
        for class_name in self.class_row_map.keys():
            duplicates = self.detect_daily_duplicates(class_name)
            for dup in duplicates:
                print(f"  × {class_name} {dup['day']}曜日: {dup['subject']}が{len(dup['periods'])}回")
                dup_count += 1
                all_good = False
        
        if dup_count == 0:
            print("  ✓ 重複なし")
        
        # 3. 時数確認
        print("\n3. 主要教科時数:")
        for class_name in ["2年5組", "3年3組"]:
            if class_name not in self.class_row_map:
                continue
            
            print(f"\n  {class_name}:")
            subject_count = self.count_subject_hours(class_name)
            required = self.standard_hours.get(class_name, self.standard_hours.get(class_name[:2], {}))
            
            for subject, req_hours in required.items():
                current = subject_count.get(subject, 0)
                status = "✓" if current >= req_hours else "×"
                print(f"    {subject}: {current}/{req_hours} {status}")
                if current < req_hours:
                    all_good = False
        
        return all_good
    
    def run(self):
        """メイン処理を実行"""
        print("=== 包括的スケジュール修正プログラム ===")
        
        # バックアップ作成
        self.backup_csv()
        
        # CSV読み込み
        self.load_csv()
        
        # 1. 日内重複を修正
        duplicate_fixes = self.fix_daily_duplicates()
        
        # 2. 時数不足を修正
        hours_fixes = self.fix_hours_shortage()
        
        # CSV保存
        self.save_csv()
        
        # 3. 最終検証
        all_good = self.verify_all_constraints()
        
        # 結果サマリー
        print("\n=== 修正サマリー ===")
        print(f"日内重複修正: {len(duplicate_fixes)}件")
        print(f"時数修正: {len(hours_fixes)}件")
        print(f"合計: {len(duplicate_fixes) + len(hours_fixes)}件")
        
        if all_good:
            print("\n✅ 全ての問題が解決されました！")
        else:
            print("\n⚠️ 一部の問題が残っています。追加の修正が必要です。")

if __name__ == "__main__":
    fixer = ComprehensiveScheduleFixer()
    fixer.run()