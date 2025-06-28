#!/usr/bin/env python3
"""究極の包括的修正スクリプト - すべての問題を確実に解決"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import copy

class UltraComprehensiveFixer:
    def __init__(self):
        self.input_path = Path(__file__).parent / "data" / "output" / "output_comprehensive_fixed.csv"
        self.output_path = Path(__file__).parent / "data" / "output" / "output_ultra_fixed.csv"
        self.df = pd.read_csv(self.input_path, header=None)
        self.days = self.df.iloc[0, 1:].tolist()
        self.periods = self.df.iloc[1, 1:].tolist()
        self.fixes = []
        self.teacher_mapping = self._load_complete_teacher_mapping()
        
    def _load_complete_teacher_mapping(self):
        """完全な教師マッピング"""
        mapping_path = Path(__file__).parent / "data" / "config" / "teacher_subject_mapping.csv"
        teacher_df = pd.read_csv(mapping_path)
        
        mapping = {}
        for _, row in teacher_df.iterrows():
            grade = int(row['学年'])
            class_num = int(row['組'])
            subject = row['教科']
            teacher = row['教員名']
            class_name = f"{grade}年{class_num}組"
            mapping[(class_name, subject)] = teacher
        
        return mapping
    
    def get_cell(self, day, period):
        """セルのインデックスを取得"""
        for i, (d, p) in enumerate(zip(self.days, self.periods)):
            if d == day and str(p) == str(period):
                return i + 1
        return None
    
    def get_class_row(self, class_name):
        """クラスの行番号を取得"""
        for i in range(2, len(self.df)):
            if self.df.iloc[i, 0] == class_name:
                return i
        return None
    
    def is_fixed_subject(self, subject):
        """固定科目かチェック"""
        return subject in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト", ""]
    
    def get_all_teacher_conflicts(self, day, period):
        """特定時間のすべての教師競合を取得"""
        col = self.get_cell(day, period)
        if not col:
            return {}
        
        teacher_assignments = defaultdict(list)
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name) or class_name == "":
                continue
            
            subject = self.df.iloc[row, col]
            if pd.notna(subject) and subject != "":
                teacher = self.teacher_mapping.get((class_name, subject))
                if teacher:
                    teacher_assignments[teacher].append((class_name, subject))
        
        # 競合のみ返す
        conflicts = {}
        for teacher, assignments in teacher_assignments.items():
            if len(assignments) > 1:
                # 5組と自立活動は除外
                all_grade5 = all("5組" in c for c, s in assignments)
                all_jiritsu = all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments)
                
                if not all_grade5 and not all_jiritsu:
                    conflicts[teacher] = assignments
        
        return conflicts
    
    def find_conflict_free_slot(self, class_name, subject, exclude_slots=None):
        """競合のない時間を探す"""
        if exclude_slots is None:
            exclude_slots = []
            
        class_row = self.get_class_row(class_name)
        if not class_row:
            return None
        
        teacher = self.teacher_mapping.get((class_name, subject))
        if not teacher:
            return None
        
        # すべての時間スロットを探索（火曜5限以外を優先）
        for day in ["月", "水", "木", "金", "火"]:
            for period in ["2", "3", "4", "5", "1"]:
                if (day, period) in exclude_slots:
                    continue
                
                # 火曜5限は最後の手段
                if day == "火" and period == "5":
                    continue
                
                col = self.get_cell(day, period)
                if not col:
                    continue
                
                current_subject = self.df.iloc[class_row, col]
                
                # 固定科目や空きスロットは交換不可
                if self.is_fixed_subject(current_subject) or pd.isna(current_subject):
                    continue
                
                # 同じ教科の日内重複チェック
                day_subjects = []
                for p in range(1, 7):
                    c = self.get_cell(day, str(p))
                    if c:
                        s = self.df.iloc[class_row, c]
                        if pd.notna(s) and s != "":
                            day_subjects.append(s)
                
                if subject in day_subjects:
                    continue
                
                # その時間に同じ教師が他クラスを教えていないかチェック
                conflicts = self.get_all_teacher_conflicts(day, period)
                if teacher in conflicts:
                    continue
                
                # 交換相手の教師も競合しないかチェック
                target_teacher = self.teacher_mapping.get((class_name, current_subject))
                if target_teacher:
                    # 元の時間（火曜5限など）でその教師が競合しないか
                    src_conflicts = self.get_all_teacher_conflicts("火", "5")
                    if target_teacher in src_conflicts:
                        continue
                
                return (day, period, current_subject)
        
        return None
    
    def force_swap(self, class_name, src_day, src_period, dst_day, dst_period):
        """強制的に授業を交換"""
        class_row = self.get_class_row(class_name)
        src_col = self.get_cell(src_day, src_period)
        dst_col = self.get_cell(dst_day, dst_period)
        
        if class_row and src_col and dst_col:
            src_subject = self.df.iloc[class_row, src_col]
            dst_subject = self.df.iloc[class_row, dst_col]
            
            # 道徳は動かさない
            if dst_subject in ["道", "道徳"]:
                return False
            
            self.df.iloc[class_row, src_col] = dst_subject
            self.df.iloc[class_row, dst_col] = src_subject
            
            self.fixes.append(f"{class_name}: {src_day}{src_period}限({src_subject}) ⇔ {dst_day}{dst_period}限({dst_subject})")
            return True
        return False
    
    def ultra_fix_tuesday_5th(self):
        """火曜5限の残り競合を徹底的に解決"""
        print("\n=== 火曜5限の残り競合を究極解決 ===")
        
        while True:
            conflicts = self.get_all_teacher_conflicts("火", "5")
            if not conflicts:
                print("\n✅ すべての競合が解決されました！")
                break
            
            print(f"\n残り{len(conflicts)}件の競合:")
            for teacher, assignments in conflicts.items():
                print(f"  {teacher}: {[c for c, s in assignments]}")
            
            # 各競合を解決
            resolved_any = False
            for teacher, assignments in conflicts.items():
                print(f"\n{teacher}先生の競合を解決:")
                
                # 2番目以降のクラスを移動
                for class_name, subject in assignments[1:]:
                    safe_slot = self.find_conflict_free_slot(class_name, subject, [("火", "5")])
                    
                    if safe_slot:
                        day, period, _ = safe_slot
                        if self.force_swap(class_name, "火", "5", day, period):
                            print(f"  ✓ {class_name}: 火曜5限({subject}) → {day}{period}限")
                            resolved_any = True
                            break
                    else:
                        print(f"  ✗ {class_name}: 移動先が見つかりません")
            
            if not resolved_any:
                print("\n⚠️  これ以上の自動解決は困難です")
                break
    
    def ultra_fix_gym_conflicts(self):
        """月曜4限の体育館使用を確実に解決"""
        print("\n\n=== 月曜4限の体育館使用を究極解決 ===")
        
        monday_4th = self.get_cell("月", "4")
        pe_classes = []
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.notna(class_name) and self.df.iloc[row, monday_4th] == "保":
                pe_classes.append(class_name)
        
        print(f"現在の体育実施クラス: {pe_classes}")
        
        # 3番目以降のクラスを移動
        if len(pe_classes) > 2:
            for class_name in pe_classes[2:]:
                print(f"\n{class_name}の保健体育を移動:")
                
                # 体育館が空いている時間を探す
                moved = False
                for day in ["火", "水", "木", "金"]:
                    for period in ["2", "3", "4", "5"]:
                        col = self.get_cell(day, period)
                        if not col:
                            continue
                        
                        # その時間に体育をしているクラスをカウント
                        gym_count = 0
                        for r in range(2, len(self.df)):
                            if self.df.iloc[r, col] == "保":
                                gym_count += 1
                        
                        # 体育館が空いている（1クラス以下）
                        if gym_count <= 1:
                            if self.force_swap(class_name, "月", "4", day, period):
                                print(f"  ✓ 月曜4限 → {day}{period}限")
                                moved = True
                                break
                    
                    if moved:
                        break
                
                if not moved:
                    print(f"  ✗ 移動先が見つかりません")
    
    def verify_all_fixes(self):
        """すべての修正結果を検証"""
        print("\n\n=== 最終検証 ===")
        
        # 火曜5限
        print("\n【火曜5限】")
        conflicts = self.get_all_teacher_conflicts("火", "5")
        if conflicts:
            print(f"  ❌ まだ{len(conflicts)}件の競合があります")
            for teacher, assignments in conflicts.items():
                print(f"    {teacher}: {[c for c, s in assignments]}")
        else:
            print("  ✅ すべての競合が解決されました")
        
        # 月曜4限
        print("\n【月曜4限の体育館】")
        monday_4th = self.get_cell("月", "4")
        pe_classes = []
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.notna(class_name) and self.df.iloc[row, monday_4th] == "保":
                pe_classes.append(class_name)
        
        print(f"  体育実施: {pe_classes} ({len(pe_classes)}クラス)")
        if len(pe_classes) <= 2:
            print("  ✅ 体育館使用制約OK")
        else:
            print("  ❌ まだ違反があります")
        
        # 日内重複（2年2組）
        print("\n【2年2組の日内重複】")
        class_row = self.get_class_row("2年2組")
        if class_row:
            for day in ["木", "金"]:
                subjects = defaultdict(list)
                for period in range(1, 7):
                    col = self.get_cell(day, str(period))
                    if col:
                        subject = self.df.iloc[class_row, col]
                        if pd.notna(subject) and subject != "" and not self.is_fixed_subject(subject):
                            subjects[subject].append(period)
                
                duplicates = {s: p for s, p in subjects.items() if len(p) > 1}
                if duplicates:
                    print(f"  ❌ {day}曜日: {duplicates}")
                else:
                    print(f"  ✅ {day}曜日: 重複なし")
    
    def save(self):
        """結果を保存"""
        self.df.to_csv(self.output_path, index=False, header=False)
        print(f"\n\n究極修正完了: {self.output_path}")
        print(f"修正件数: {len(self.fixes)}件")

def main():
    fixer = UltraComprehensiveFixer()
    fixer.ultra_fix_tuesday_5th()
    fixer.ultra_fix_gym_conflicts()
    fixer.verify_all_fixes()
    fixer.save()

if __name__ == "__main__":
    main()