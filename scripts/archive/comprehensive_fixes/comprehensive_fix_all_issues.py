#!/usr/bin/env python3
"""すべての問題を包括的に修正するスクリプト（ultrathink版）"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import copy

class ComprehensiveFixer:
    def __init__(self):
        self.input_path = Path(__file__).parent / "data" / "output" / "output.csv"
        self.output_path = Path(__file__).parent / "data" / "output" / "output_comprehensive_fixed.csv"
        self.df = pd.read_csv(self.input_path, header=None)
        self.days = self.df.iloc[0, 1:].tolist()
        self.periods = self.df.iloc[1, 1:].tolist()
        self.fixes = []
        self.teacher_mapping = self._load_teacher_mapping()
        
    def _load_teacher_mapping(self):
        """教師マッピングを構築"""
        return {
            # 1年
            ("1年1組", "家"): "大嶋",
            ("1年6組", "家"): "大嶋",
            ("1年2組", "英"): "箱崎",
            ("1年3組", "数"): "井上",
            ("1年7組", "自立"): "智田",
            # 2年
            ("2年1組", "英"): "箱崎",
            ("2年3組", "数"): "井上",
            ("2年6組", "自立"): "智田",
            ("2年7組", "自立"): "智田",
            ("2年1組", "保"): "財津",
            ("2年2組", "保"): "財津",
            ("2年3組", "保"): "財津",
            ("2年7組", "保"): "財津",
            # 3年
            ("3年1組", "社"): "北",
            ("3年7組", "社"): "北",
            ("3年2組", "理"): "白石",
            ("3年3組", "理"): "白石",
            ("3年7組", "自立"): "智田",
        }
    
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
    
    def get_teacher_schedule(self, teacher, day, period):
        """特定の教師が特定の時間に教えているクラスを取得"""
        col = self.get_cell(day, period)
        if not col:
            return []
        
        classes = []
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name) or class_name == "":
                continue
            subject = self.df.iloc[row, col]
            if pd.notna(subject) and subject != "":
                if self.teacher_mapping.get((class_name, subject)) == teacher:
                    classes.append((class_name, subject))
        return classes
    
    def find_safe_slot(self, class_name, subject, avoid_slots):
        """安全な移動先スロットを探す"""
        class_row = self.get_class_row(class_name)
        if not class_row:
            return None
        
        teacher = self.teacher_mapping.get((class_name, subject))
        
        # 優先順位付きスロット探索
        priority_days = ["金", "木", "水", "月"]  # 火曜を避ける
        
        for day in priority_days:
            for period in ["2", "3", "4", "5"]:
                if (day, period) in avoid_slots:
                    continue
                
                col = self.get_cell(day, period)
                if not col:
                    continue
                
                current_subject = self.df.iloc[class_row, col]
                
                # 固定科目は交換不可
                if self.is_fixed_subject(current_subject):
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
                
                # 教師の空き時間チェック
                if teacher:
                    teacher_classes = self.get_teacher_schedule(teacher, day, period)
                    if teacher_classes:
                        continue
                
                return (day, period, current_subject)
        
        return None
    
    def swap_assignments(self, class_name, src_day, src_period, dst_day, dst_period):
        """授業を交換"""
        class_row = self.get_class_row(class_name)
        src_col = self.get_cell(src_day, src_period)
        dst_col = self.get_cell(dst_day, dst_period)
        
        if class_row and src_col and dst_col:
            src_subject = self.df.iloc[class_row, src_col]
            dst_subject = self.df.iloc[class_row, dst_col]
            
            self.df.iloc[class_row, src_col] = dst_subject
            self.df.iloc[class_row, dst_col] = src_subject
            
            self.fixes.append(f"{class_name}: {src_day}{src_period}限({src_subject}) ⇔ {dst_day}{dst_period}限({dst_subject})")
            return True
        return False
    
    def phase1_fix_tuesday_5th(self):
        """Phase 1: 火曜5限の教師重複を解消"""
        print("\n=== Phase 1: 火曜5限の教師重複解消 ===")
        
        tuesday_5th_conflicts = [
            # (クラス, 教科, 優先移動先)
            ("1年6組", "家", [("木", "2"), ("金", "3"), ("水", "4")]),
            ("2年1組", "英", [("金", "2"), ("木", "3"), ("水", "3")]),
            ("2年3組", "数", [("月", "4"), ("金", "3"), ("木", "2")]),
            ("3年7組", "社", [("金", "2"), ("金", "3"), ("木", "2")]),
            ("3年3組", "理", [("金", "5"), ("木", "3"), ("水", "4")]),
            ("1年7組", "自立", [("月", "5"), ("金", "2"), ("水", "3")]),
            ("2年6組", "自立", [("水", "5"), ("金", "3"), ("木", "3")]),
        ]
        
        for class_name, subject, priority_slots in tuesday_5th_conflicts:
            print(f"\n{class_name}の{subject}を移動:")
            
            moved = False
            for day, period in priority_slots:
                if self.swap_assignments(class_name, "火", "5", day, period):
                    print(f"  ✓ 火曜5限 → {day}{period}限")
                    moved = True
                    break
            
            if not moved:
                # 自動探索
                safe_slot = self.find_safe_slot(class_name, subject, [("火", "5")])
                if safe_slot:
                    day, period, _ = safe_slot
                    if self.swap_assignments(class_name, "火", "5", day, period):
                        print(f"  ✓ 火曜5限 → {day}{period}限（自動探索）")
                    else:
                        print(f"  ✗ 移動失敗")
                else:
                    print(f"  ✗ 移動先が見つかりません")
    
    def phase2_fix_gym_conflicts(self):
        """Phase 2: 月曜4限の体育館使用違反を解消"""
        print("\n\n=== Phase 2: 月曜4限の体育館使用違反解消 ===")
        
        monday_4th_pe = [
            ("2年1組", "保", [("火", "2"), ("水", "3"), ("金", "2")]),
            ("2年7組", "保", [("木", "2"), ("金", "3"), ("水", "4")]),
        ]
        
        for class_name, subject, priority_slots in monday_4th_pe:
            print(f"\n{class_name}の{subject}を移動:")
            
            moved = False
            for day, period in priority_slots:
                # その時間に他に体育がないかチェック
                gym_used = False
                col = self.get_cell(day, period)
                if col:
                    for row in range(2, len(self.df)):
                        if self.df.iloc[row, col] == "保":
                            gym_used = True
                            break
                
                if not gym_used:
                    if self.swap_assignments(class_name, "月", "4", day, period):
                        print(f"  ✓ 月曜4限 → {day}{period}限")
                        moved = True
                        break
            
            if not moved:
                print(f"  ✗ 移動先が見つかりません")
    
    def phase3_fix_daily_duplicates(self):
        """Phase 3: 日内重複を解消"""
        print("\n\n=== Phase 3: 日内重複の解消 ===")
        
        # 2年2組の問題を修正
        print("\n2年2組の日内重複:")
        
        # 木曜5限の数を他の教科と交換
        if self.swap_assignments("2年2組", "木", "5", "金", "2"):
            print("  ✓ 木曜5限(数) → 金曜2限と交換")
        
        # 金曜5限の国を他の教科と交換
        safe_slot = self.find_safe_slot("2年2組", "国", [("金", "3"), ("金", "5")])
        if safe_slot:
            day, period, _ = safe_slot
            if self.swap_assignments("2年2組", "金", "5", day, period):
                print(f"  ✓ 金曜5限(国) → {day}{period}限と交換")
    
    def verify_fixes(self):
        """修正結果を検証"""
        print("\n\n=== 修正結果の検証 ===")
        
        # 火曜5限の検証
        print("\n【火曜5限の教師配置】")
        tuesday_5th = self.get_cell("火", "5")
        
        teacher_assignments = defaultdict(list)
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name):
                continue
            subject = self.df.iloc[row, tuesday_5th]
            if pd.notna(subject) and subject != "":
                teacher = self.teacher_mapping.get((class_name, subject), f"{subject}担当")
                teacher_assignments[teacher].append((class_name, subject))
        
        conflicts = 0
        for teacher, assignments in sorted(teacher_assignments.items()):
            if len(assignments) > 1:
                # 5組と自立活動チェック
                all_grade5 = all("5組" in c for c, s in assignments)
                all_jiritsu = all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments)
                
                if not all_grade5 and not all_jiritsu:
                    print(f"  ❌ {teacher}: {[c for c, s in assignments]}")
                    conflicts += 1
                else:
                    status = "5組合同" if all_grade5 else "自立活動同時実施"
                    print(f"  ✅ {teacher}: {[c for c, s in assignments]} ({status})")
            else:
                print(f"  ○ {teacher}: {[c for c, s in assignments]}")
        
        if conflicts == 0:
            print("\n✅ 火曜5限の競合がすべて解決されました！")
        
        # 月曜4限の検証
        print("\n【月曜4限の体育館使用】")
        monday_4th = self.get_cell("月", "4")
        pe_classes = []
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.notna(class_name) and self.df.iloc[row, monday_4th] == "保":
                pe_classes.append(class_name)
        
        print(f"  体育実施クラス: {pe_classes} ({len(pe_classes)}クラス)")
        if len(pe_classes) <= 2:
            print("  ✅ 体育館使用制約OK（2クラス以下）")
        else:
            print("  ❌ まだ違反があります")
    
    def save(self):
        """結果を保存"""
        self.df.to_csv(self.output_path, index=False, header=False)
        print(f"\n\n修正完了: {self.output_path}")
        print(f"修正件数: {len(self.fixes)}件")

def main():
    fixer = ComprehensiveFixer()
    fixer.phase1_fix_tuesday_5th()
    fixer.phase2_fix_gym_conflicts()
    fixer.phase3_fix_daily_duplicates()
    fixer.verify_fixes()
    fixer.save()

if __name__ == "__main__":
    main()