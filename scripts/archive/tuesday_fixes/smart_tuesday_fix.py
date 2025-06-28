#!/usr/bin/env python3
"""スマートな火曜問題修正スクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import copy

class SmartTimetableFixer:
    def __init__(self, input_path):
        self.df = pd.read_csv(input_path, header=None)
        self.teacher_mapping = self._load_teacher_mapping()
        self.days = self.df.iloc[0, 1:].tolist()
        self.periods = self.df.iloc[1, 1:].tolist()
        self.fixes = []
        
    def _load_teacher_mapping(self):
        """教師マッピングを読み込み"""
        mapping_path = Path(__file__).parent / "data" / "config" / "teacher_subject_mapping.csv"
        teacher_df = pd.read_csv(mapping_path)
        
        mapping = {}
        for _, row in teacher_df.iterrows():
            grade = int(row['学年'])
            class_num = int(row['組'])
            subject = row['教科']
            teacher = row['教員名']
            key = f"{grade}年{class_num}組"
            if key not in mapping:
                mapping[key] = {}
            mapping[key][subject] = teacher
        
        return mapping
    
    def get_teacher(self, class_name, subject):
        """教師を取得"""
        if class_name in self.teacher_mapping and subject in self.teacher_mapping[class_name]:
            return self.teacher_mapping[class_name][subject]
        return None
    
    def get_cell_index(self, day, period):
        """セルのインデックスを取得"""
        for col_idx in range(1, len(self.df.columns)):
            if self.days[col_idx - 1] == day and str(self.periods[col_idx - 1]) == str(period):
                return col_idx
        return None
    
    def get_class_row(self, class_name):
        """クラスの行番号を取得"""
        for idx in range(2, len(self.df)):
            if self.df.iloc[idx, 0] == class_name:
                return idx
        return None
    
    def swap_assignments(self, class_name, day1, period1, day2, period2):
        """授業を入れ替え"""
        class_row = self.get_class_row(class_name)
        col1 = self.get_cell_index(day1, period1)
        col2 = self.get_cell_index(day2, period2)
        
        if class_row and col1 and col2:
            subj1 = self.df.iloc[class_row, col1]
            subj2 = self.df.iloc[class_row, col2]
            self.df.iloc[class_row, col1] = subj2
            self.df.iloc[class_row, col2] = subj1
            return True, subj1, subj2
        return False, None, None
    
    def check_teacher_at_time(self, day, period, teacher_name):
        """指定時間の教師の授業数を確認"""
        col_idx = self.get_cell_index(day, period)
        if not col_idx:
            return []
        
        classes = []
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.isna(class_name) or class_name == "":
                continue
                
            subject = self.df.iloc[row_idx, col_idx]
            if pd.notna(subject) and subject != "":
                teacher = self.get_teacher(class_name, subject)
                if teacher == teacher_name:
                    classes.append((class_name, subject))
        
        return classes
    
    def fix_hf_meeting_smart(self):
        """火曜4限のHF会議問題をスマートに修正"""
        print("\n=== 火曜4限のHF会議対応（スマート版） ===")
        
        # 2年生クラスを教師ごとにグループ化
        grade2_by_teacher = defaultdict(list)
        tuesday_4th_col = self.get_cell_index("火", "4")
        
        grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
        
        for class_name in grade2_classes:
            class_row = self.get_class_row(class_name)
            if class_row:
                subject = self.df.iloc[class_row, tuesday_4th_col]
                if pd.notna(subject) and subject != "":
                    teacher = self.get_teacher(class_name, subject)
                    if teacher:
                        grade2_by_teacher[teacher].append((class_name, subject))
        
        # 教師ごとに分散して移動
        for teacher, classes in grade2_by_teacher.items():
            print(f"\n{teacher}先生の授業（{len(classes)}クラス）:")
            
            # 各クラスを異なる時間に移動
            target_slots = [
                ("木", "4"), ("木", "5"), ("金", "4"), ("金", "5"),
                ("月", "4"), ("月", "5"), ("水", "4"), ("水", "5")
            ]
            
            for i, (class_name, subject) in enumerate(classes):
                # 移動先を探す
                moved = False
                
                for target_day, target_period in target_slots[i:]:
                    # その時間に同じ教師がいないか確認
                    teacher_classes = self.check_teacher_at_time(target_day, target_period, teacher)
                    
                    if len(teacher_classes) == 0:
                        # 入れ替えを試みる
                        success, subj1, subj2 = self.swap_assignments(
                            class_name, "火", "4", target_day, target_period
                        )
                        
                        if success:
                            fix_msg = f"{class_name}: 火曜4限({subj1}) → {target_day}{target_period}限({subj2}と交換)"
                            self.fixes.append(fix_msg)
                            print(f"  ✓ {fix_msg}")
                            moved = True
                            break
                
                if not moved:
                    print(f"  ✗ {class_name}: 適切な移動先が見つかりません")
    
    def fix_tuesday_5th_smart(self):
        """火曜5限の競合をスマートに修正"""
        print("\n\n=== 火曜5限の競合修正（スマート版） ===")
        
        # 競合を確認
        conflicts = defaultdict(list)
        tuesday_5th_col = self.get_cell_index("火", "5")
        
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.isna(class_name) or class_name == "":
                continue
                
            subject = self.df.iloc[row_idx, tuesday_5th_col]
            if pd.notna(subject) and subject != "":
                teacher = self.get_teacher(class_name, subject)
                if teacher:
                    conflicts[teacher].append((class_name, subject))
        
        # 競合を解決
        for teacher, assignments in conflicts.items():
            if len(assignments) <= 1:
                continue
            
            # 5組の合同授業チェック
            if all("5組" in c for c, s in assignments):
                print(f"  ⓘ {teacher}先生: 5組の合同授業（問題なし）")
                continue
            
            # 自立活動の同時実施チェック
            if all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments):
                print(f"  ⓘ {teacher}先生: 自立活動の同時実施（問題なし）")
                continue
            
            print(f"\n{teacher}先生の競合解決:")
            
            # 最初のクラス以外を移動
            for i, (class_name, subject) in enumerate(assignments[1:]):
                # 移動先候補
                candidates = []
                
                for col_idx in range(1, len(self.df.columns)):
                    day = self.days[col_idx - 1]
                    period = str(self.periods[col_idx - 1])
                    
                    # 火曜5限、テスト期間、6限は除外
                    if (day == "火" and period == "5") or \
                       (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or \
                       period == "6":
                        continue
                    
                    # その時間に同じ教師がいないか確認
                    teacher_classes = self.check_teacher_at_time(day, period, teacher)
                    
                    if len(teacher_classes) == 0:
                        candidates.append((day, period))
                
                # 最適な候補を選択
                if candidates:
                    target_day, target_period = candidates[0]
                    success, subj1, subj2 = self.swap_assignments(
                        class_name, "火", "5", target_day, target_period
                    )
                    
                    if success:
                        fix_msg = f"{class_name}: 火曜5限({subj1}) → {target_day}{target_period}限({subj2}と交換)"
                        self.fixes.append(fix_msg)
                        print(f"  ✓ {fix_msg}")
                    else:
                        print(f"  ✗ {class_name}: 入れ替え失敗")
                else:
                    print(f"  ✗ {class_name}: 適切な移動先なし")
    
    def verify_result(self):
        """修正結果の検証"""
        print("\n\n=== 修正結果の検証 ===")
        
        # 火曜4限の2年生チェック
        print("\n【火曜4限】")
        tuesday_4th_col = self.get_cell_index("火", "4")
        grade2_count = 0
        
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.notna(class_name) and "2年" in class_name:
                subject = self.df.iloc[row_idx, tuesday_4th_col]
                if pd.notna(subject) and subject != "" and subject not in ["欠", "YT", "道", "学", "総", "行"]:
                    print(f"  {class_name}: {subject}")
                    grade2_count += 1
        
        if grade2_count == 0:
            print("  ✅ 2年生の授業なし（HF会議対応完了）")
        else:
            print(f"  ❌ {grade2_count}クラスの2年生授業が残存")
        
        # 火曜5限の競合チェック
        print("\n【火曜5限】")
        conflicts = defaultdict(list)
        tuesday_5th_col = self.get_cell_index("火", "5")
        
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.isna(class_name) or class_name == "":
                continue
                
            subject = self.df.iloc[row_idx, tuesday_5th_col]
            if pd.notna(subject) and subject != "":
                teacher = self.get_teacher(class_name, subject)
                if teacher:
                    conflicts[teacher].append((class_name, subject))
        
        problem_count = 0
        for teacher, assignments in conflicts.items():
            if len(assignments) > 1:
                # 5組と自立活動は除外
                if not all("5組" in c for c, s in assignments) and \
                   not all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments):
                    print(f"  ❌ {teacher}先生: {[c for c, s in assignments]}")
                    problem_count += 1
        
        if problem_count == 0:
            print("  ✅ 教師競合なし")
    
    def save(self, output_path):
        """結果を保存"""
        self.df.to_csv(output_path, index=False, header=False)
        print(f"\n修正件数: {len(self.fixes)}件")
        print(f"出力: {output_path}")

def main():
    # パス設定
    input_path = Path(__file__).parent / "data" / "output" / "output_backup.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_smart_fixed.csv"
    
    # 修正実行
    fixer = SmartTimetableFixer(input_path)
    fixer.fix_hf_meeting_smart()
    fixer.fix_tuesday_5th_smart()
    fixer.verify_result()
    fixer.save(output_path)

if __name__ == "__main__":
    main()