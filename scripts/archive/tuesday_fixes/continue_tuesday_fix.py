#!/usr/bin/env python3
"""火曜問題の追加修正スクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

class ContinuedFixer:
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
            
            # 固定科目はスキップ
            if subj2 in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"]:
                return False, None, None
            
            self.df.iloc[class_row, col1] = subj2
            self.df.iloc[class_row, col2] = subj1
            return True, subj1, subj2
        return False, None, None
    
    def check_all_conflicts(self, day, period):
        """指定時間の全競合をチェック"""
        col_idx = self.get_cell_index(day, period)
        if not col_idx:
            return {}
        
        teacher_classes = defaultdict(list)
        
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.isna(class_name) or class_name == "":
                continue
                
            subject = self.df.iloc[row_idx, col_idx]
            if pd.notna(subject) and subject != "":
                teacher = self.get_teacher(class_name, subject)
                if teacher:
                    teacher_classes[teacher].append((class_name, subject))
        
        # 競合のみ返す
        conflicts = {}
        for teacher, classes in teacher_classes.items():
            if len(classes) > 1:
                # 5組と自立活動は除外
                if not all("5組" in c for c, s in classes) and \
                   not all(s in ["自立", "日生", "生単", "作業"] for c, s in classes):
                    conflicts[teacher] = classes
        
        return conflicts
    
    def fix_remaining_hf_issues(self):
        """残りのHF会議問題を修正"""
        print("\n=== 残りの火曜4限HF会議問題を修正 ===")
        
        tuesday_4th_col = self.get_cell_index("火", "4")
        remaining_grade2 = []
        
        # 残っている2年生クラスを確認
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.notna(class_name) and "2年" in class_name:
                subject = self.df.iloc[row_idx, tuesday_4th_col]
                if pd.notna(subject) and subject != "" and subject not in ["欠", "YT", "道", "学", "総", "行"]:
                    remaining_grade2.append((class_name, subject))
        
        print(f"残り{len(remaining_grade2)}クラス: {[c for c, s in remaining_grade2]}")
        
        # 各クラスを処理
        for class_name, subject in remaining_grade2:
            print(f"\n{class_name}の{subject}を移動:")
            
            # 全時間スロットを試す
            moved = False
            for col_idx in range(1, len(self.df.columns)):
                day = self.days[col_idx - 1]
                period = str(self.periods[col_idx - 1])
                
                # 火曜4限、テスト期間、6限は除外
                if (day == "火" and period == "4") or \
                   (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or \
                   period == "6":
                    continue
                
                # その時間の競合を事前チェック
                current_conflicts = self.check_all_conflicts(day, period)
                
                # 仮の入れ替えを実行して確認
                success, subj1, subj2 = self.swap_assignments(class_name, "火", "4", day, period)
                
                if success:
                    # 新しい競合を確認
                    new_conflicts = self.check_all_conflicts(day, period)
                    
                    # 競合が増えていない場合は採用
                    if len(new_conflicts) <= len(current_conflicts):
                        fix_msg = f"{class_name}: 火曜4限({subj1}) → {day}{period}限({subj2}と交換)"
                        self.fixes.append(fix_msg)
                        print(f"  ✓ {fix_msg}")
                        moved = True
                        break
                    else:
                        # 元に戻す
                        self.swap_assignments(class_name, day, period, "火", "4")
            
            if not moved:
                print(f"  ✗ 移動先が見つかりません")
    
    def fix_remaining_conflicts(self):
        """残りの火曜5限競合を修正"""
        print("\n\n=== 残りの火曜5限競合を修正 ===")
        
        conflicts = self.check_all_conflicts("火", "5")
        
        for teacher, classes in conflicts.items():
            print(f"\n{teacher}先生の競合（{len(classes)}クラス）:")
            
            # 2番目以降のクラスを移動
            for i, (class_name, subject) in enumerate(classes[1:]):
                print(f"  {class_name}の{subject}を移動:")
                
                # 移動先を探す
                moved = False
                for col_idx in range(1, len(self.df.columns)):
                    day = self.days[col_idx - 1]
                    period = str(self.periods[col_idx - 1])
                    
                    # 制約チェック
                    if (day == "火" and period == "5") or \
                       (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or \
                       period == "6":
                        continue
                    
                    # その時間に同じ教師がいないか確認
                    conflicts_at_time = self.check_all_conflicts(day, period)
                    if teacher in conflicts_at_time:
                        continue
                    
                    # 入れ替えを試みる
                    success, subj1, subj2 = self.swap_assignments(class_name, "火", "5", day, period)
                    
                    if success:
                        fix_msg = f"{class_name}: 火曜5限({subj1}) → {day}{period}限({subj2}と交換)"
                        self.fixes.append(fix_msg)
                        print(f"    ✓ {fix_msg}")
                        moved = True
                        break
                
                if not moved:
                    print(f"    ✗ 移動先が見つかりません")
    
    def verify_final_result(self):
        """最終結果の検証"""
        print("\n\n=== 最終検証 ===")
        
        # 火曜4限
        print("\n【火曜4限の2年生】")
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
            print("  ✅ HF会議対応完了！")
        else:
            print(f"  ❌ まだ{grade2_count}クラス残存")
        
        # 火曜5限
        print("\n【火曜5限の競合】")
        conflicts = self.check_all_conflicts("火", "5")
        
        if not conflicts:
            print("  ✅ 競合解消完了！")
        else:
            for teacher, classes in conflicts.items():
                print(f"  ❌ {teacher}先生: {[c for c, s in classes]}")
    
    def save(self, output_path):
        """結果を保存"""
        self.df.to_csv(output_path, index=False, header=False)
        print(f"\n追加修正: {len(self.fixes)}件")
        print(f"最終出力: {output_path}")

def main():
    # 前回の修正結果を読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output_smart_fixed.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_final_fixed.csv"
    
    fixer = ContinuedFixer(input_path)
    fixer.fix_remaining_hf_issues()
    fixer.fix_remaining_conflicts()
    fixer.verify_final_result()
    fixer.save(output_path)

if __name__ == "__main__":
    main()