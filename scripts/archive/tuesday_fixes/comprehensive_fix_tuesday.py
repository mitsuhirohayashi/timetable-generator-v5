#!/usr/bin/env python3
"""火曜4限と5限の包括的修正スクリプト（連鎖的入れ替え対応）"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import copy

class TimetableFixer:
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
        return f"{subject}担当"
    
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
    
    def check_teacher_conflict(self, day, period, exclude_classes=None):
        """指定時間の教師競合をチェック"""
        exclude_classes = exclude_classes or []
        col_idx = self.get_cell_index(day, period)
        if not col_idx:
            return {}
        
        teacher_assignments = defaultdict(list)
        
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.isna(class_name) or class_name == "" or class_name in exclude_classes:
                continue
                
            subject = self.df.iloc[row_idx, col_idx]
            if pd.notna(subject) and subject != "":
                teacher = self.get_teacher(class_name, subject)
                teacher_assignments[teacher].append((class_name, subject))
        
        # 競合をチェック
        conflicts = {}
        for teacher, assignments in teacher_assignments.items():
            if len(assignments) > 1:
                # 5組の合同授業は除外
                grade5_classes = {"1年5組", "2年5組", "3年5組"}
                non_grade5 = [c for c, s in assignments if c not in grade5_classes]
                
                # 自立活動の同時実施は除外
                jiritsu_subjects = {"自立", "日生", "生単", "作業"}
                all_jiritsu = all(s in jiritsu_subjects for c, s in assignments)
                
                if len(non_grade5) > 1 and not all_jiritsu:
                    conflicts[teacher] = assignments
        
        return conflicts
    
    def find_chain_swap_solution(self, class_name, from_day, from_period, avoid_conflicts=None):
        """連鎖的な入れ替えソリューションを探索"""
        avoid_conflicts = avoid_conflicts or []
        
        class_row = self.get_class_row(class_name)
        if not class_row:
            return None
            
        from_col = self.get_cell_index(from_day, from_period)
        if not from_col:
            return None
            
        from_subject = self.df.iloc[class_row, from_col]
        if pd.isna(from_subject) or from_subject == "":
            return None
        
        # 全ての時間スロットを試す
        for col_idx in range(1, len(self.df.columns)):
            day = self.days[col_idx - 1]
            period = str(self.periods[col_idx - 1])
            
            # 同じ時間、テスト期間、6限は除外
            if (day == from_day and period == str(from_period)) or \
               (day in ["月", "火", "水"] and period in ["1", "2", "3"]) or \
               period == "6":
                continue
            
            to_subject = self.df.iloc[class_row, col_idx]
            if pd.isna(to_subject) or to_subject == "" or \
               to_subject in ["欠", "YT", "道", "学", "総", "行", "学総"]:
                continue
            
            # 仮の入れ替えを実行
            temp_df = self.df.copy()
            temp_df.iloc[class_row, from_col] = to_subject
            temp_df.iloc[class_row, col_idx] = from_subject
            
            # 新しい競合をチェック
            self.df = temp_df
            new_conflicts_from = self.check_teacher_conflict(from_day, from_period)
            new_conflicts_to = self.check_teacher_conflict(day, period)
            self.df = self.df  # 元に戻す
            
            # 競合が解決または改善される場合
            if len(new_conflicts_from) + len(new_conflicts_to) < len(avoid_conflicts):
                return {
                    'class': class_name,
                    'from': (from_day, from_period, from_subject),
                    'to': (day, period, to_subject),
                    'new_conflicts': list(new_conflicts_from.keys()) + list(new_conflicts_to.keys())
                }
        
        return None
    
    def fix_hf_meeting(self):
        """火曜4限のHF会議問題を修正"""
        print("\n=== 火曜4限のHF会議対応 ===")
        
        grade2_classes = ["2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組"]
        
        for class_name in grade2_classes:
            solution = self.find_chain_swap_solution(class_name, "火", "4")
            
            if solution:
                # 入れ替えを実行
                class_row = self.get_class_row(class_name)
                from_col = self.get_cell_index(solution['from'][0], solution['from'][1])
                to_col = self.get_cell_index(solution['to'][0], solution['to'][1])
                
                self.df.iloc[class_row, from_col] = solution['to'][2]
                self.df.iloc[class_row, to_col] = solution['from'][2]
                
                fix_msg = f"{class_name}: 火曜4限({solution['from'][2]}) ⇔ {solution['to'][0]}{solution['to'][1]}限({solution['to'][2]})"
                self.fixes.append(fix_msg)
                print(f"  ✓ {fix_msg}")
            else:
                print(f"  ✗ {class_name}: 適切な入れ替え先が見つかりません")
    
    def fix_tuesday_5th_conflicts(self):
        """火曜5限の競合を修正"""
        print("\n=== 火曜5限の競合修正 ===")
        
        # 現在の競合を確認
        conflicts = self.check_teacher_conflict("火", "5")
        
        if not conflicts:
            print("  火曜5限に競合はありません")
            return
        
        print(f"  検出された競合: {len(conflicts)}件")
        for teacher, assignments in conflicts.items():
            print(f"    - {teacher}先生: {[c for c, s in assignments]}")
        
        # 各競合を解決
        for teacher, assignments in conflicts.items():
            # 自立活動の同時実施は許可
            if all(s in {"自立", "日生", "生単", "作業"} for c, s in assignments):
                print(f"  ⓘ {teacher}先生の自立活動は同時実施可能")
                continue
            
            # 最初のクラス以外を移動対象とする
            for class_name, subject in assignments[1:]:
                solution = self.find_chain_swap_solution(class_name, "火", "5", [teacher])
                
                if solution:
                    # 入れ替えを実行
                    class_row = self.get_class_row(class_name)
                    from_col = self.get_cell_index("火", "5")
                    to_col = self.get_cell_index(solution['to'][0], solution['to'][1])
                    
                    self.df.iloc[class_row, from_col] = solution['to'][2]
                    self.df.iloc[class_row, to_col] = solution['from'][2]
                    
                    fix_msg = f"{class_name}: 火曜5限({subject}) ⇔ {solution['to'][0]}{solution['to'][1]}限({solution['to'][2]})"
                    self.fixes.append(fix_msg)
                    print(f"  ✓ {fix_msg}")
                    break
    
    def verify_fixes(self):
        """修正後の検証"""
        print("\n=== 修正後の検証 ===")
        
        # 火曜4限の2年生チェック
        print("\n【火曜4限の2年生】")
        col_idx = self.get_cell_index("火", "4")
        grade2_count = 0
        
        for row_idx in range(2, len(self.df)):
            class_name = self.df.iloc[row_idx, 0]
            if pd.notna(class_name) and "2年" in class_name:
                subject = self.df.iloc[row_idx, col_idx]
                if pd.notna(subject) and subject != "" and subject not in ["欠", "YT", "道", "学", "総", "行"]:
                    print(f"  {class_name}: {subject}")
                    grade2_count += 1
        
        if grade2_count == 0:
            print("  ✅ 2年生の授業はありません（HF会議対応完了）")
        else:
            print(f"  ❌ まだ{grade2_count}クラスの2年生授業が残っています")
        
        # 火曜5限の競合チェック
        print("\n【火曜5限の教師競合】")
        conflicts = self.check_teacher_conflict("火", "5")
        
        if not conflicts:
            print("  ✅ 教師競合はありません")
        else:
            print(f"  ❌ {len(conflicts)}件の競合が残っています")
            for teacher, assignments in conflicts.items():
                # 自立活動チェック
                if all(s in {"自立", "日生", "生単", "作業"} for c, s in assignments):
                    print(f"    ⓘ {teacher}先生: {[c for c, s in assignments]} - 自立活動の同時実施")
                else:
                    print(f"    ❌ {teacher}先生: {[c for c, s in assignments]}")
    
    def save(self, output_path):
        """修正結果を保存"""
        self.df.to_csv(output_path, index=False, header=False)
        
        print(f"\n=== 修正完了 ===")
        print(f"修正件数: {len(self.fixes)}件")
        for fix in self.fixes:
            print(f"  - {fix}")
        print(f"\n修正後のファイル: {output_path}")

def main():
    input_path = Path(__file__).parent / "data" / "output" / "output.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_comprehensive_fixed.csv"
    
    # 元のファイルに戻す（前回の修正をリセット）
    original_path = Path(__file__).parent / "data" / "output" / "output_backup.csv"
    if not original_path.exists():
        # バックアップを作成
        import shutil
        shutil.copy(input_path, original_path)
    else:
        # バックアップから復元
        import shutil
        shutil.copy(original_path, input_path)
    
    fixer = TimetableFixer(input_path)
    
    # 1. 火曜4限のHF会議対応
    fixer.fix_hf_meeting()
    
    # 2. 火曜5限の競合修正
    fixer.fix_tuesday_5th_conflicts()
    
    # 3. 検証
    fixer.verify_fixes()
    
    # 4. 保存
    fixer.save(output_path)

if __name__ == "__main__":
    main()