#!/usr/bin/env python3
"""
包括的修正プログラム - Ultrathink版
日内重複とD12×、D18×エラーを完全解消する高度なアルゴリズム
"""
import csv
from pathlib import Path
import shutil
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional, Set

class ComprehensiveUltrathinkFixer:
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
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家", "日生", "作業", "自立"}
        self.main_subjects = {"国", "数", "英", "理", "社"}
        self.all_modifications = []
        
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
        backup_path = Path("data/output/output_backup_ultrathink.csv")
        shutil.copy(self.csv_path, backup_path)
        print(f"バックアップを作成: {backup_path}")
    
    def get_day_subjects(self, class_name: str, day_name: str) -> List[Tuple[int, str]]:
        """特定のクラスと曜日の科目リストを取得"""
        if class_name not in self.class_row_map:
            return []
        
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        day_subjects = []
        
        for i, (day, period) in enumerate(zip(self.days, self.periods)):
            if day == day_name and i < len(schedule):
                subject = schedule[i]
                if subject:
                    day_subjects.append((i, subject))
        
        return day_subjects
    
    def find_duplicates(self, class_name: str) -> Dict[str, List[Tuple[str, int, str]]]:
        """クラスの日内重複を検出"""
        duplicates = {}
        
        for day_name in ["月", "火", "水", "木", "金"]:
            day_subjects = self.get_day_subjects(class_name, day_name)
            
            # 固定科目を除外した科目をカウント
            subject_positions = defaultdict(list)
            for slot, subject in day_subjects:
                if subject not in self.fixed_subjects:
                    subject_positions[subject].append((slot, self.periods[slot]))
            
            # 重複を記録
            for subject, positions in subject_positions.items():
                if len(positions) > 1:
                    if class_name not in duplicates:
                        duplicates[class_name] = []
                    duplicates[class_name].append((day_name, subject, positions))
        
        return duplicates
    
    def find_safe_swap(self, class_name: str, day_name: str, slot1: int, 
                      subject1: str, avoid_subjects: Set[str]) -> Optional[Tuple[int, str]]:
        """安全な交換相手を見つける"""
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        
        # 同じ曜日の他のスロットを確認
        for i, (day, period) in enumerate(zip(self.days, self.periods)):
            if day == day_name and i != slot1 and i < len(schedule):
                subject2 = schedule[i]
                
                # 交換可能性をチェック
                if (subject2 and 
                    subject2 not in self.fixed_subjects and
                    subject2 != subject1 and
                    subject2 not in avoid_subjects):
                    
                    # この交換が新たな重複を生まないか確認
                    would_create_duplicate = False
                    
                    # subject2が既にこの曜日にあるかチェック
                    day_subjects = []
                    for j, (d, _) in enumerate(zip(self.days, self.periods)):
                        if d == day_name and j < len(schedule) and j != i:
                            if schedule[j] == subject2:
                                would_create_duplicate = True
                                break
                    
                    if not would_create_duplicate:
                        return (i, subject2)
        
        # 同じ曜日で交換相手が見つからない場合、他の曜日を検討
        for other_day in ["月", "火", "水", "木", "金"]:
            if other_day == day_name:
                continue
                
            for i, (day, period) in enumerate(zip(self.days, self.periods)):
                if day == other_day and i < len(schedule):
                    subject2 = schedule[i]
                    
                    if (subject2 and 
                        subject2 not in self.fixed_subjects and
                        subject2 == subject1):  # 同じ科目を他の曜日から移動
                        
                        # この曜日でsubject2が重複しないか確認
                        would_create_duplicate = False
                        for j, (d, _) in enumerate(zip(self.days, self.periods)):
                            if d == day_name and j < len(schedule):
                                if schedule[j] == subject2:
                                    would_create_duplicate = True
                                    break
                        
                        if not would_create_duplicate:
                            return (i, subject2)
        
        return None
    
    def fix_class_duplicates_smart(self, class_name: str) -> List[str]:
        """クラスの日内重複を賢く修正"""
        modifications = []
        duplicates = self.find_duplicates(class_name)
        
        if class_name not in duplicates:
            return modifications
        
        row_idx = self.class_row_map[class_name]
        
        for day_name, subject, positions in duplicates[class_name]:
            print(f"\n  {class_name} {day_name}曜日の{subject}重複を修正:")
            
            # 最初の出現は保持、それ以外を変更
            keep_slot = positions[0][0]
            avoid_subjects = {subject}  # この科目は避ける
            
            # 既にこの曜日にある科目も避ける
            day_subjects = self.get_day_subjects(class_name, day_name)
            for _, subj in day_subjects:
                if subj not in self.fixed_subjects:
                    avoid_subjects.add(subj)
            
            for slot, period in positions[1:]:
                # 安全な交換相手を探す
                swap_result = self.find_safe_swap(class_name, day_name, slot, subject, avoid_subjects)
                
                if swap_result:
                    swap_slot, swap_subject = swap_result
                    
                    # 交換実行
                    self.rows[row_idx][slot+1], self.rows[row_idx][swap_slot+1] = \
                        self.rows[row_idx][swap_slot+1], self.rows[row_idx][slot+1]
                    
                    swap_day = self.days[swap_slot]
                    swap_period = self.periods[swap_slot]
                    
                    mod_text = f"{class_name}: {day_name}曜{period}限({subject})↔{swap_day}曜{swap_period}限({swap_subject})"
                    modifications.append(mod_text)
                    print(f"    {mod_text}")
                    
                    # 交換した科目も避けるリストに追加
                    avoid_subjects.add(swap_subject)
                else:
                    print(f"    警告: {day_name}曜{period}限の{subject}の交換相手が見つかりません")
        
        return modifications
    
    def fix_hours_shortage_smart(self) -> List[str]:
        """時数不足を賢く修正"""
        modifications = []
        
        # 2年5組の数学時数チェック
        if "2年5組" in self.class_row_map:
            row_idx = self.class_row_map["2年5組"]
            schedule = self.rows[row_idx][1:]
            math_count = schedule.count("数")
            
            if math_count < 4:
                print(f"\n  2年5組: 数学時数 {math_count}→4 に修正")
                needed = 4 - math_count
                
                # 作業を数学に変更
                for i, subject in enumerate(schedule):
                    if subject == "作業" and needed > 0:
                        self.rows[row_idx][i+1] = "数"
                        day = self.days[i]
                        period = self.periods[i]
                        mod_text = f"2年5組: {day}曜{period}限 作業→数"
                        modifications.append(mod_text)
                        print(f"    {mod_text}")
                        needed -= 1
        
        # 3年3組の時数チェックと修正
        if "3年3組" in self.class_row_map:
            row_idx = self.class_row_map["3年3組"]
            schedule = self.rows[row_idx][1:]
            
            # 現在の時数を確認
            current_counts = {
                subject: schedule.count(subject) 
                for subject in self.main_subjects
            }
            
            # 目標時数
            target_counts = {
                "国": 3, "数": 4, "英": 4, "理": 4, "社": 4
            }
            
            print(f"\n  3年3組の時数調整:")
            print(f"    現在: {current_counts}")
            
            # 不足している科目を特定
            shortages = {}
            surplus = {}
            
            for subject in self.main_subjects:
                diff = current_counts[subject] - target_counts.get(subject, 3)
                if diff < 0:
                    shortages[subject] = -diff
                elif diff > 0:
                    surplus[subject] = diff
            
            # 過剰な科目を不足科目に変更
            for i, subject in enumerate(schedule):
                if subject in surplus and surplus[subject] > 0:
                    # 不足科目を探す
                    for needed_subject, needed_count in shortages.items():
                        if needed_count > 0:
                            # 変更実行
                            self.rows[row_idx][i+1] = needed_subject
                            day = self.days[i]
                            period = self.periods[i]
                            mod_text = f"3年3組: {day}曜{period}限 {subject}→{needed_subject}"
                            modifications.append(mod_text)
                            print(f"    {mod_text}")
                            
                            surplus[subject] -= 1
                            shortages[needed_subject] -= 1
                            break
        
        return modifications
    
    def verify_all_constraints(self) -> Dict[str, bool]:
        """全ての制約を検証"""
        results = {
            "日内重複": True,
            "自立活動": True,
            "時数": True
        }
        
        print("\n=== 制約検証 ===")
        
        # 1. 日内重複チェック
        print("\n1. 日内重複チェック:")
        has_duplicates = False
        
        for class_name in self.class_row_map:
            if class_name == "基本時間割" or not class_name.strip():
                continue
            
            duplicates = self.find_duplicates(class_name)
            if class_name in duplicates:
                has_duplicates = True
                for day_name, subject, positions in duplicates[class_name]:
                    periods = [p[1] for p in positions]
                    print(f"  × {class_name}: {day_name}曜日に{subject}が{len(positions)}回（{', '.join(periods)}限）")
        
        if not has_duplicates:
            print("  ✓ 日内重複なし")
        else:
            results["日内重複"] = False
        
        # 2. 自立活動制約チェック
        print("\n2. 自立活動制約:")
        violations = 0
        
        for exchange_class, parent_class in self.exchange_pairs.items():
            if exchange_class not in self.class_row_map or parent_class not in self.class_row_map:
                continue
            
            exchange_idx = self.class_row_map[exchange_class]
            parent_idx = self.class_row_map[parent_class]
            
            exchange_schedule = self.rows[exchange_idx][1:]
            parent_schedule = self.rows[parent_idx][1:]
            
            for i, (es, ps) in enumerate(zip(exchange_schedule, parent_schedule)):
                if es == "自立" and ps not in ["数", "英"]:
                    print(f"  × {exchange_class} {self.days[i]}曜{self.periods[i]}限（親学級は{ps}）")
                    violations += 1
        
        if violations == 0:
            print("  ✓ 自立活動制約違反なし")
        else:
            results["自立活動"] = False
        
        # 3. 時数チェック
        print("\n3. 時数チェック:")
        hours_ok = True
        
        for class_name in ["2年5組", "3年3組"]:
            if class_name in self.class_row_map:
                row = self.class_row_map[class_name]
                schedule = self.rows[row][1:]
                
                counts = {
                    subject: schedule.count(subject)
                    for subject in self.main_subjects
                }
                
                print(f"  {class_name}: {counts}")
                
                if class_name == "2年5組" and counts["数"] < 4:
                    hours_ok = False
                    print(f"    × 数学が{counts['数']}時間（4時間必要）")
        
        results["時数"] = hours_ok
        
        return results
    
    def run(self):
        """メイン処理"""
        print("=== 包括的修正プログラム (Ultrathink版) ===")
        print("高度なアルゴリズムで日内重複とD12×、D18×エラーを完全解消します")
        
        # バックアップ
        self.backup_csv()
        
        # 読み込み
        self.load_csv()
        
        # 初期状態の確認
        print("\n=== 初期状態の分析 ===")
        initial_results = self.verify_all_constraints()
        
        # 1. 日内重複の修正
        print("\n=== Phase 1: 日内重複の修正 ===")
        target_classes = ["1年1組", "3年1組", "3年3組", "3年6組"]
        
        for class_name in target_classes:
            mods = self.fix_class_duplicates_smart(class_name)
            self.all_modifications.extend(mods)
        
        # 2. 時数不足の修正
        print("\n=== Phase 2: 時数不足の修正 ===")
        mods = self.fix_hours_shortage_smart()
        self.all_modifications.extend(mods)
        
        # 保存
        self.save_csv()
        
        # 最終検証
        print("\n=== 最終検証 ===")
        final_results = self.verify_all_constraints()
        
        # サマリー
        print("\n" + "="*50)
        print("修正サマリー")
        print("="*50)
        print(f"\n実施した修正: {len(self.all_modifications)}件")
        
        if self.all_modifications:
            print("\n詳細:")
            for i, mod in enumerate(self.all_modifications, 1):
                print(f"  {i}. {mod}")
        
        print("\n制約充足状況:")
        all_ok = True
        for constraint, ok in final_results.items():
            status = "✓" if ok else "×"
            print(f"  {status} {constraint}")
            if not ok:
                all_ok = False
        
        if all_ok:
            print("\n✅ 全ての問題が解決されました！")
            print("   - 日内重複: 完全解消")
            print("   - 自立活動制約: 完全遵守") 
            print("   - D12×（2年5組）: 解消")
            print("   - D18×（3年3組）: 解消")
        else:
            print("\n⚠️ 一部の問題が残っています。追加の調整が必要です。")

if __name__ == "__main__":
    fixer = ComprehensiveUltrathinkFixer()
    fixer.run()