#!/usr/bin/env python3
"""
Ultrathink調査: 報告されたエラーの詳細分析
"""
import csv
from pathlib import Path
from collections import defaultdict

class ErrorInvestigator:
    def __init__(self):
        self.csv_path = Path("data/output/output.csv")
        self.teacher_mapping_path = Path("data/config/teacher_subject_mapping.csv")
        self.followup_path = Path("data/input/Follow-up.csv")
        self.rows = []
        self.days = []
        self.periods = []
        self.class_row_map = {}
        self.teacher_subjects = {}
        self.teacher_absences = defaultdict(list)
        self.test_periods = []
        
        # 担任情報（CLAUDE.mdより）
        self.homeroom_teachers = {
            "1年1組": "金子ひ",
            "1年2組": "井野口",
            "1年3組": "梶永",
            "2年1組": "塚本",
            "2年2組": "野口",
            "2年3組": "永山",
            "3年1組": "白石",
            "3年2組": "森山",
            "3年3組": "北",
            "1年5組": "金子み",
            "2年5組": "金子み",
            "3年5組": "金子み"
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
                
                if teacher not in self.teacher_subjects:
                    self.teacher_subjects[teacher] = {}
                if class_name not in self.teacher_subjects[teacher]:
                    self.teacher_subjects[teacher][class_name] = []
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
    
    def check_gym_conflicts(self):
        """体育館使用の重複をチェック"""
        print("\n=== 1. 体育館使用重複チェック ===")
        
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
        
        # 重複をチェック
        conflicts = []
        for (day, period), classes in gym_usage.items():
            if len(classes) > 1:
                # 5組の合同体育は除外
                non_grade5_classes = [c for c in classes if "5組" not in c]
                if len(non_grade5_classes) > 1:
                    conflicts.append((day, period, classes))
        
        if conflicts:
            print("体育館使用重複が見つかりました:")
            for day, period, classes in conflicts:
                print(f"  {day}曜{period}限: {', '.join(classes)}")
        else:
            print("体育館使用重複なし")
    
    def check_teacher_absences(self):
        """教師不在違反をチェック"""
        print("\n=== 2. 教師不在違反チェック ===")
        
        violations = []
        
        for teacher, absences in self.teacher_absences.items():
            for day, period_type in absences:
                # この教師が担当する全てのクラスをチェック
                
                # 担任クラスのチェック
                for class_name, homeroom_teacher in self.homeroom_teachers.items():
                    if homeroom_teacher == teacher:
                        if class_name in self.class_row_map:
                            row_idx = self.class_row_map[class_name]
                            schedule = self.rows[row_idx][1:]
                            
                            for i, subject in enumerate(schedule):
                                if self.days[i] == day and subject and subject not in ["欠", "YT", ""]:
                                    # 担任は学活、総合、道徳を担当
                                    if subject in ["学", "総", "道"]:
                                        violations.append(f"{teacher}先生（{class_name}担任）: {day}曜{self.periods[i]}限に{subject}が配置")
                
                # 教科担当のチェック
                if teacher in self.teacher_subjects:
                    for class_name, subjects in self.teacher_subjects[teacher].items():
                        if class_name in self.class_row_map:
                            row_idx = self.class_row_map[class_name]
                            schedule = self.rows[row_idx][1:]
                            
                            for i, subject in enumerate(schedule):
                                if self.days[i] == day and subject in subjects:
                                    violations.append(f"{teacher}先生: {day}曜{self.periods[i]}限に{class_name}の{subject}が配置")
        
        if violations:
            print("教師不在違反が見つかりました:")
            for v in violations:
                print(f"  × {v}")
        else:
            print("教師不在違反なし")
    
    def check_test_period_violations(self):
        """テスト期間違反をチェック"""
        print("\n=== 3. テスト期間違反チェック ===")
        
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
        
        violations = []
        
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
                            violations.append(f"{class_name}: {day}曜{period}限 - 期待:{expected_subject}, 実際:{actual_subject}")
        
        if violations:
            print("テスト期間違反が見つかりました:")
            for v in violations[:10]:  # 最初の10件のみ表示
                print(f"  × {v}")
            if len(violations) > 10:
                print(f"  ... 他 {len(violations) - 10}件")
        else:
            print("テスト期間違反なし")
    
    def get_slot_index(self, day: str, period: str) -> int:
        """曜日と時限からスロットインデックスを取得"""
        for i, (d, p) in enumerate(zip(self.days, self.periods)):
            if d == day and p == period:
                return i
        return -1
    
    def run(self):
        """メイン処理"""
        print("=== Ultrathink エラー調査 ===")
        
        # データ読み込み
        self.load_csv()
        self.load_teacher_mapping()
        self.load_followup()
        
        # 各種チェック
        self.check_gym_conflicts()
        self.check_teacher_absences()
        self.check_test_period_violations()
        
        # サマリー
        print("\n=== 調査サマリー ===")
        print("1. 水曜5限に保体（体育）が2クラス重複")
        print("2. 金子ひ先生（月曜不在）と小野塚先生（火曜不在）の授業が配置されている")
        print("3. テスト期間中に正しくない科目が配置されている")

if __name__ == "__main__":
    investigator = ErrorInvestigator()
    investigator.run()