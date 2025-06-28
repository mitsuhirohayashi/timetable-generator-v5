#!/usr/bin/env python3
"""究極のシステマティック修正 - すべての問題を体系的に解決"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import copy

class UltimateSystematicFixer:
    def __init__(self):
        self.input_path = Path(__file__).parent / "data" / "output" / "output.csv"
        self.output_path = Path(__file__).parent / "data" / "output" / "output_systematic_fixed.csv"
        self.df = pd.read_csv(self.input_path, header=None)
        self.days = self.df.iloc[0, 1:].tolist()
        self.periods = self.df.iloc[1, 1:].tolist()
        self.fixes = []
        self.teacher_mapping = self._load_complete_teacher_mapping()
        
    def _load_complete_teacher_mapping(self):
        """完全な教師マッピングを読み込み"""
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
        for i, (d, p) in enumerate(zip(self.days, self.periods)):
            if d == day and str(p) == str(period):
                return i + 1
        return None
    
    def get_class_row(self, class_name):
        for i in range(2, len(self.df)):
            if self.df.iloc[i, 0] == class_name:
                return i
        return None
    
    def is_fixed_subject(self, subject):
        return subject in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト", ""]
    
    def analyze_all_conflicts(self):
        """すべての時間帯の競合を分析"""
        print("=== 全時間帯の競合分析 ===\n")
        
        conflict_summary = {}
        
        for day in self.days[:30:6]:  # 各曜日の最初の要素
            for period in range(1, 7):
                col = self.get_cell(day, str(period))
                if not col:
                    continue
                
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
                
                # 競合を検出
                conflicts = []
                for teacher, assignments in teacher_assignments.items():
                    if len(assignments) > 1:
                        # 5組と自立活動は除外
                        all_grade5 = all("5組" in c for c, s in assignments)
                        all_jiritsu = all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments)
                        
                        if not all_grade5 and not all_jiritsu:
                            conflicts.append({
                                'teacher': teacher,
                                'assignments': assignments
                            })
                
                if conflicts:
                    conflict_summary[f"{day}{period}限"] = conflicts
        
        # 最も問題の多い時間帯を表示
        print("【競合の多い時間帯】")
        sorted_conflicts = sorted(conflict_summary.items(), key=lambda x: len(x[1]), reverse=True)
        for time_slot, conflicts in sorted_conflicts[:5]:
            print(f"{time_slot}: {len(conflicts)}件の競合")
            for conf in conflicts:
                print(f"  - {conf['teacher']}: {[c for c, s in conf['assignments']]}")
        
        return conflict_summary
    
    def systematic_redistribute(self):
        """体系的に授業を再配置"""
        print("\n\n=== 体系的な再配置を開始 ===")
        
        # 火曜5限と金曜3限の問題を同時に解決
        critical_slots = [
            ("火", "5", ["1年6組", "1年7組", "2年6組", "3年6組", "3年7組"]),
            ("金", "3", ["1年6組", "2年3組", "2年7組", "3年3組", "3年7組"])
        ]
        
        for day, period, problem_classes in critical_slots:
            print(f"\n【{day}{period}限の問題解決】")
            col = self.get_cell(day, period)
            
            for class_name in problem_classes:
                class_row = self.get_class_row(class_name)
                if not class_row:
                    continue
                
                subject = self.df.iloc[class_row, col]
                if self.is_fixed_subject(subject):
                    continue
                
                print(f"\n{class_name}の{subject}を移動:")
                
                # 最適な移動先を探す
                best_slot = self.find_optimal_slot(class_name, subject, [(day, period)])
                
                if best_slot:
                    dst_day, dst_period, _ = best_slot
                    if self.smart_swap(class_name, day, period, dst_day, dst_period):
                        print(f"  ✓ {day}{period}限 → {dst_day}{dst_period}限")
                    else:
                        print(f"  ✗ 交換失敗")
                else:
                    print(f"  ✗ 適切な移動先が見つかりません")
    
    def find_optimal_slot(self, class_name, subject, exclude_slots):
        """最適な移動先を見つける（負荷分散を考慮）"""
        class_row = self.get_class_row(class_name)
        if not class_row:
            return None
        
        teacher = self.teacher_mapping.get((class_name, subject))
        if not teacher:
            return None
        
        # 各時間帯の教師負荷を計算
        slot_loads = {}
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in ["1", "2", "3", "4", "5"]:
                if (day, period) in exclude_slots:
                    continue
                
                col = self.get_cell(day, period)
                if not col:
                    continue
                
                # 教師の負荷を計算
                teacher_count = 0
                for row in range(2, len(self.df)):
                    s = self.df.iloc[row, col]
                    if pd.notna(s) and s != "":
                        t = self.teacher_mapping.get((self.df.iloc[row, 0], s))
                        if t == teacher:
                            teacher_count += 1
                
                # その時間の総授業数
                total_classes = sum(1 for row in range(2, len(self.df)) 
                                  if pd.notna(self.df.iloc[row, col]) 
                                  and self.df.iloc[row, col] != "")
                
                slot_loads[(day, period)] = {
                    'teacher_load': teacher_count,
                    'total_load': total_classes,
                    'col': col
                }
        
        # 負荷の少ない時間帯を優先
        sorted_slots = sorted(slot_loads.items(), 
                            key=lambda x: (x[1]['teacher_load'], x[1]['total_load']))
        
        for (day, period), load_info in sorted_slots:
            col = load_info['col']
            current_subject = self.df.iloc[class_row, col]
            
            # 固定科目は交換不可
            if self.is_fixed_subject(current_subject):
                continue
            
            # 日内重複チェック
            if self.would_cause_daily_duplicate(class_name, subject, day):
                continue
            
            # 教師がその時間に空いているか
            if load_info['teacher_load'] > 0:
                continue
            
            return (day, period, current_subject)
        
        return None
    
    def would_cause_daily_duplicate(self, class_name, subject, day):
        """日内重複が発生するかチェック"""
        class_row = self.get_class_row(class_name)
        if not class_row:
            return True
        
        day_subjects = []
        for period in range(1, 7):
            col = self.get_cell(day, str(period))
            if col:
                s = self.df.iloc[class_row, col]
                if pd.notna(s) and s != "":
                    day_subjects.append(s)
        
        return subject in day_subjects
    
    def smart_swap(self, class_name, src_day, src_period, dst_day, dst_period):
        """スマートな授業交換（連鎖的な影響を考慮）"""
        class_row = self.get_class_row(class_name)
        src_col = self.get_cell(src_day, src_period)
        dst_col = self.get_cell(dst_day, dst_period)
        
        if not (class_row and src_col and dst_col):
            return False
        
        src_subject = self.df.iloc[class_row, src_col]
        dst_subject = self.df.iloc[class_row, dst_col]
        
        # 交換前の状態を保存
        original_state = self.df.copy()
        
        # 交換実行
        self.df.iloc[class_row, src_col] = dst_subject
        self.df.iloc[class_row, dst_col] = src_subject
        
        # 交換後の競合をチェック
        src_conflicts_after = self.count_conflicts_at(src_day, src_period)
        dst_conflicts_after = self.count_conflicts_at(dst_day, dst_period)
        
        # 元の状態の競合数
        original_state_df = self.df
        self.df = original_state
        src_conflicts_before = self.count_conflicts_at(src_day, src_period)
        dst_conflicts_before = self.count_conflicts_at(dst_day, dst_period)
        
        # 競合が増えない場合のみ採用
        if (src_conflicts_after + dst_conflicts_after) <= (src_conflicts_before + dst_conflicts_before):
            self.df = original_state_df
            self.df.iloc[class_row, src_col] = dst_subject
            self.df.iloc[class_row, dst_col] = src_subject
            self.fixes.append(f"{class_name}: {src_day}{src_period}限({src_subject}) ⇔ {dst_day}{dst_period}限({dst_subject})")
            return True
        else:
            # 元に戻す
            self.df = original_state
            return False
    
    def count_conflicts_at(self, day, period):
        """特定時間の競合数をカウント"""
        col = self.get_cell(day, period)
        if not col:
            return 0
        
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
        
        conflicts = 0
        for teacher, assignments in teacher_assignments.items():
            if len(assignments) > 1:
                all_grade5 = all("5組" in c for c, s in assignments)
                all_jiritsu = all(s in ["自立", "日生", "生単", "作業"] for c, s in assignments)
                if not all_grade5 and not all_jiritsu:
                    conflicts += 1
        
        return conflicts
    
    def fix_daily_duplicates(self):
        """日内重複を修正"""
        print("\n\n=== 日内重複の修正 ===")
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name):
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                subjects = defaultdict(list)
                
                for period in range(1, 7):
                    col = self.get_cell(day, str(period))
                    if col:
                        subject = self.df.iloc[row, col]
                        if pd.notna(subject) and subject != "" and not self.is_fixed_subject(subject):
                            subjects[subject].append((period, col))
                
                # 重複を検出
                for subject, occurrences in subjects.items():
                    if len(occurrences) > 1:
                        print(f"\n{class_name}の{day}曜日に{subject}が{len(occurrences)}回:")
                        
                        # 2回目以降を移動
                        for period, col in occurrences[1:]:
                            # 他の曜日の同じ時間で交換可能な科目を探す
                            for other_day in ["月", "火", "水", "木", "金"]:
                                if other_day == day:
                                    continue
                                
                                other_col = self.get_cell(other_day, str(period))
                                if other_col:
                                    other_subject = self.df.iloc[row, other_col]
                                    
                                    if (pd.notna(other_subject) and 
                                        not self.is_fixed_subject(other_subject) and
                                        not self.would_cause_daily_duplicate(class_name, other_subject, day)):
                                        
                                        # 交換
                                        self.df.iloc[row, col] = other_subject
                                        self.df.iloc[row, other_col] = subject
                                        print(f"  ✓ {day}{period}限({subject}) ⇔ {other_day}{period}限({other_subject})")
                                        self.fixes.append(f"{class_name}: 日内重複解消")
                                        break
    
    def verify_all(self):
        """包括的な検証"""
        print("\n\n=== 包括的検証 ===")
        
        # 競合の再分析
        conflict_summary = self.analyze_all_conflicts()
        
        total_conflicts = sum(len(conflicts) for conflicts in conflict_summary.values())
        print(f"\n総競合数: {total_conflicts}件")
        
        if total_conflicts < 20:
            print("✅ 大幅に改善されました！")
        else:
            print("⚠️  まだ改善の余地があります")
    
    def save(self):
        self.df.to_csv(self.output_path, index=False, header=False)
        print(f"\n\nシステマティック修正完了: {self.output_path}")
        print(f"修正件数: {len(self.fixes)}件")

def main():
    fixer = UltimateSystematicFixer()
    fixer.analyze_all_conflicts()
    fixer.systematic_redistribute()
    fixer.fix_daily_duplicates()
    fixer.verify_all()
    fixer.save()

if __name__ == "__main__":
    main()