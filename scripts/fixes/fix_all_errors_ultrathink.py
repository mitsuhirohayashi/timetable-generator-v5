#!/usr/bin/env python3
"""
Ultrathink包括的エラー修正プログラム
- 体育館使用重複の解消
- 教師不在違反の修正
- テスト期間違反の修正
"""
import csv
from pathlib import Path
from collections import defaultdict
import sys

class UltrathinkErrorFixer:
    def __init__(self):
        self.csv_path = Path("data/output/output.csv")
        self.teacher_mapping_path = Path("data/config/teacher_subject_mapping.csv")
        self.followup_path = Path("data/input/Follow-up.csv")
        self.rows = []
        self.days = []
        self.periods = []
        self.class_row_map = {}
        self.teacher_subjects = defaultdict(lambda: defaultdict(list))
        self.teacher_absences = defaultdict(list)
        self.test_periods = []
        self.error_count = 0
        self.fix_count = 0
        
        # 交流学級と親学級の対応
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        
        # 親学級から交流学級への逆引き
        self.parent_exchange_map = defaultdict(list)
        for exchange, parent in self.exchange_parent_map.items():
            self.parent_exchange_map[parent].append(exchange)
    
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
    
    def load_teacher_mapping(self):
        """教師担当マッピングを読み込み"""
        with open(self.teacher_mapping_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                teacher = row['教員名']
                subject = row['教科']
                grade = row['学年']
                class_num = row['組']
                class_name = f"{grade}年{class_num}組"
                self.teacher_subjects[teacher][class_name].append(subject)
    
    def load_followup(self):
        """Follow-up.csvから教師不在とテスト期間を読み込み"""
        with open(self.followup_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        current_day = None
        for row in rows:
            if not row or not row[0]:
                continue
            
            text = row[0]
            
            # 曜日の識別
            if "月曜日" in text:
                current_day = "月"
            elif "火曜日" in text:
                current_day = "火"
            elif "水曜日" in text:
                current_day = "水"
            elif "木曜日" in text:
                current_day = "木"
            elif "金曜日" in text:
                current_day = "金"
            
            # 教師不在の解析
            if current_day and "不在" in text:
                if "金子ひ先生は振休で1日不在" in text:
                    self.teacher_absences["金子ひ"].append((current_day, "終日"))
                elif "小野塚先生は振休で1日不在" in text:
                    self.teacher_absences["小野塚"].append((current_day, "終日"))
                elif "白石先生は終日年休" in text:
                    self.teacher_absences["白石"].append((current_day, "終日"))
                elif "永山先生は終日年休" in text:
                    self.teacher_absences["永山"].append((current_day, "終日"))
            
            # テスト期間の解析
            if "校時はテスト" in text:
                if current_day == "月" and "１・２・３校時" in text:
                    self.test_periods.extend([("月", "1"), ("月", "2"), ("月", "3")])
                elif current_day == "火" and "１・２・３校時" in text:
                    self.test_periods.extend([("火", "1"), ("火", "2"), ("火", "3")])
                elif current_day == "水" and "１・２校時" in text:
                    self.test_periods.extend([("水", "1"), ("水", "2")])
    
    def get_slot_index(self, day: str, period: str) -> int:
        """曜日と時限からスロットインデックスを取得"""
        for i, (d, p) in enumerate(zip(self.days, self.periods)):
            if d == day and p == period:
                return i
        return -1
    
    def get_teacher_for_subject(self, class_name: str, subject: str) -> str:
        """クラスと科目から担当教師を取得"""
        for teacher, classes in self.teacher_subjects.items():
            if class_name in classes and subject in classes[class_name]:
                return teacher
        return ""
    
    def is_teacher_available(self, teacher: str, day: str, period: str) -> bool:
        """教師が特定の時間に利用可能か確認"""
        if teacher in self.teacher_absences:
            for absent_day, absent_type in self.teacher_absences[teacher]:
                if absent_day == day and absent_type == "終日":
                    return False
        return True
    
    def fix_gym_conflicts(self):
        """体育館使用重複を修正"""
        print("\n=== 1. 体育館使用重複の修正 ===")
        
        # 各時間帯の体育館使用状況を収集
        gym_usage = defaultdict(list)
        
        for class_name, row_idx in self.class_row_map.items():
            if class_name == "基本時間割" or not class_name.strip():
                continue
            
            schedule = self.rows[row_idx][1:]
            
            for i, subject in enumerate(schedule):
                if subject == "保":
                    day = self.days[i]
                    period = self.periods[i]
                    gym_usage[(day, period)].append(class_name)
        
        # 重複を修正
        for (day, period), classes in gym_usage.items():
            if len(classes) > 1:
                # 5組の合同体育は除外
                non_grade5_classes = [c for c in classes if "5組" not in c]
                if len(non_grade5_classes) > 1:
                    print(f"\n{day}曜{period}限の体育館重複: {', '.join(non_grade5_classes)}")
                    
                    # 最初のクラス以外の体育を他の時間に移動
                    for i, class_name in enumerate(non_grade5_classes[1:]):
                        self.error_count += 1
                        if self.relocate_pe_class(class_name, day, period):
                            self.fix_count += 1
    
    def relocate_pe_class(self, class_name: str, conflict_day: str, conflict_period: str) -> bool:
        """体育の授業を他の時間に移動"""
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        conflict_slot = self.get_slot_index(conflict_day, conflict_period)
        
        # 体育教師を取得
        pe_teacher = self.get_teacher_for_subject(class_name, "保")
        
        # 他の適切な時間を探す
        for i, subject in enumerate(schedule):
            if i == conflict_slot:
                continue
            
            day = self.days[i]
            period = self.periods[i]
            
            # スワップ可能かチェック
            if (subject not in ["欠", "YT", "学", "道", "総", "学総", "行", "テスト", "技家"] and
                subject != "保" and
                not self.is_gym_occupied(day, period, class_name) and
                self.is_teacher_available(pe_teacher, day, period)):
                
                # 日内重複をチェック
                if not self.would_create_daily_duplicate(class_name, day, "保", conflict_slot):
                    # スワップ実行
                    self.rows[row_idx][conflict_slot + 1] = subject
                    self.rows[row_idx][i + 1] = "保"
                    print(f"  → {class_name}の体育を{day}曜{period}限に移動（{subject}と交換）")
                    return True
        
        print(f"  × {class_name}の体育を移動できる適切な時間が見つかりません")
        return False
    
    def is_gym_occupied(self, day: str, period: str, exclude_class: str = None) -> bool:
        """特定の時間に体育館が使用されているかチェック"""
        for class_name, row_idx in self.class_row_map.items():
            if class_name == "基本時間割" or not class_name.strip() or class_name == exclude_class:
                continue
            
            schedule = self.rows[row_idx][1:]
            slot_idx = self.get_slot_index(day, period)
            
            if slot_idx >= 0 and slot_idx < len(schedule) and schedule[slot_idx] == "保":
                # 5組の合同体育は特別扱い
                if "5組" not in class_name or "5組" not in exclude_class:
                    return True
        
        return False
    
    def would_create_daily_duplicate(self, class_name: str, day: str, subject: str, exclude_slot: int) -> bool:
        """日内重複を作成するかチェック"""
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        
        for i, (d, s) in enumerate(zip(self.days, schedule)):
            if d == day and i != exclude_slot and s == subject:
                return True
        
        return False
    
    def fix_teacher_absences(self):
        """教師不在違反を修正"""
        print("\n=== 2. 教師不在違反の修正 ===")
        
        for teacher, absences in self.teacher_absences.items():
            for day, period_type in absences:
                if period_type == "終日":
                    print(f"\n{teacher}先生（{day}曜終日不在）の授業を修正:")
                    
                    # この教師が担当する全てのクラスをチェック
                    for class_name, subjects in self.teacher_subjects[teacher].items():
                        if class_name in self.class_row_map:
                            row_idx = self.class_row_map[class_name]
                            schedule = self.rows[row_idx][1:]
                            
                            for i, subject in enumerate(schedule):
                                if self.days[i] == day and subject in subjects:
                                    self.error_count += 1
                                    if self.relocate_teacher_class(class_name, teacher, subject, day, self.periods[i]):
                                        self.fix_count += 1
    
    def relocate_teacher_class(self, class_name: str, absent_teacher: str, subject: str, 
                               conflict_day: str, conflict_period: str) -> bool:
        """不在教師の授業を他の時間に移動"""
        row_idx = self.class_row_map[class_name]
        schedule = self.rows[row_idx][1:]
        conflict_slot = self.get_slot_index(conflict_day, conflict_period)
        
        # 他の適切な時間を探す
        for i, other_subject in enumerate(schedule):
            if i == conflict_slot:
                continue
            
            day = self.days[i]
            period = self.periods[i]
            
            # スワップ可能かチェック
            if (other_subject not in ["欠", "YT", "学", "道", "総", "学総", "行", "テスト", "技家"] and
                other_subject != subject and
                self.is_teacher_available(absent_teacher, day, period)):
                
                # 他の教師の可用性をチェック
                other_teacher = self.get_teacher_for_subject(class_name, other_subject)
                if other_teacher and self.is_teacher_available(other_teacher, conflict_day, conflict_period):
                    # 日内重複をチェック
                    if (not self.would_create_daily_duplicate(class_name, day, subject, conflict_slot) and
                        not self.would_create_daily_duplicate(class_name, conflict_day, other_subject, i)):
                        
                        # スワップ実行
                        self.rows[row_idx][conflict_slot + 1] = other_subject
                        self.rows[row_idx][i + 1] = subject
                        print(f"  → {class_name}の{subject}を{day}曜{period}限に移動（{other_subject}と交換）")
                        
                        # 交流学級も同期
                        self.sync_exchange_classes(class_name, conflict_slot, other_subject, i, subject)
                        
                        return True
        
        print(f"  × {class_name}の{subject}を移動できる適切な時間が見つかりません")
        return False
    
    def sync_exchange_classes(self, parent_class: str, slot1: int, subject1: str, slot2: int, subject2: str):
        """交流学級を親学級と同期"""
        if parent_class in self.parent_exchange_map:
            for exchange_class in self.parent_exchange_map[parent_class]:
                if exchange_class in self.class_row_map:
                    exchange_row_idx = self.class_row_map[exchange_class]
                    exchange_schedule = self.rows[exchange_row_idx][1:]
                    
                    # 交流学級が自立活動でない場合のみ同期
                    if exchange_schedule[slot1] not in ["自立", "日生", "作業"]:
                        self.rows[exchange_row_idx][slot1 + 1] = subject1
                    if exchange_schedule[slot2] not in ["自立", "日生", "作業"]:
                        self.rows[exchange_row_idx][slot2 + 1] = subject2
    
    def fix_test_period_violations(self):
        """テスト期間違反を修正"""
        print("\n=== 3. テスト期間違反の修正 ===")
        
        # テスト期間中の正しい科目
        test_subjects = {
            "月": {
                "1": {"1年": "英", "2年": "数", "3年": "国"},
                "2": {"1年": "保", "2年": "技家", "3年": "音"},
                "3": {"1年": "技家", "2年": "社", "3年": "理"}
            },
            "火": {
                "1": {"1年": "社", "2年": "国", "3年": "数"},
                "2": {"1年": "音", "2年": "保", "3年": "英"},
                "3": {"1年": "国", "2年": "理", "3年": "技家"}
            },
            "水": {
                "1": {"1年": "理", "2年": "英", "3年": "保"},
                "2": {"1年": "数", "2年": "音", "3年": "社"}
            }
        }
        
        for day, period in self.test_periods:
            if day in test_subjects and period in test_subjects[day]:
                expected_subjects = test_subjects[day][period]
                
                for class_name, row_idx in self.class_row_map.items():
                    if class_name == "基本時間割" or not class_name.strip():
                        continue
                    
                    # 学年を取得
                    if "1年" in class_name:
                        grade = "1年"
                    elif "2年" in class_name:
                        grade = "2年"
                    elif "3年" in class_name:
                        grade = "3年"
                    else:
                        continue
                    
                    # 5組は除外（テスト期間の対象外）
                    if "5組" in class_name:
                        continue
                    
                    schedule = self.rows[row_idx][1:]
                    slot_idx = self.get_slot_index(day, period)
                    
                    if slot_idx >= 0 and slot_idx < len(schedule):
                        actual_subject = schedule[slot_idx]
                        expected_subject = expected_subjects.get(grade, "")
                        
                        if actual_subject != expected_subject:
                            self.error_count += 1
                            print(f"\n{class_name}: {day}曜{period}限を{expected_subject}に修正（現在: {actual_subject}）")
                            
                            # 正しい科目に変更
                            self.rows[row_idx][slot_idx + 1] = expected_subject
                            self.fix_count += 1
                            
                            # 交流学級も同期
                            if class_name in self.parent_exchange_map:
                                for exchange_class in self.parent_exchange_map[class_name]:
                                    if exchange_class in self.class_row_map:
                                        exchange_row_idx = self.class_row_map[exchange_class]
                                        self.rows[exchange_row_idx][slot_idx + 1] = expected_subject
    
    def save_csv(self, output_path: str):
        """修正した時間割を保存"""
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(self.rows)
    
    def run(self):
        """メイン処理"""
        print("=== Ultrathink 包括的エラー修正 ===")
        
        # データ読み込み
        self.load_csv()
        self.load_teacher_mapping()
        self.load_followup()
        
        # 各種修正
        self.fix_gym_conflicts()
        self.fix_teacher_absences()
        self.fix_test_period_violations()
        
        # 結果を保存
        self.save_csv(self.csv_path)
        
        # サマリー
        print(f"\n=== 修正完了 ===")
        print(f"検出されたエラー: {self.error_count}件")
        print(f"修正されたエラー: {self.fix_count}件")
        print(f"修正率: {self.fix_count/self.error_count*100:.1f}%" if self.error_count > 0 else "エラーなし")

if __name__ == "__main__":
    fixer = UltrathinkErrorFixer()
    fixer.run()