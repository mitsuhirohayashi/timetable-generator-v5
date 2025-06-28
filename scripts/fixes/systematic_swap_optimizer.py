#!/usr/bin/env python3
"""根本的な再構築 - 問題の多い時間帯を完全に再編成"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import random

class RadicalReconstructor:
    def __init__(self):
        self.input_path = Path(__file__).parent / "data" / "output" / "output_systematic_fixed.csv"
        self.output_path = Path(__file__).parent / "data" / "output" / "output_radical_fixed.csv"
        self.df = pd.read_csv(self.input_path, header=None)
        self.days = self.df.iloc[0, 1:].tolist()
        self.periods = self.df.iloc[1, 1:].tolist()
        self.teacher_mapping = self._load_complete_teacher_mapping()
        self.removed_assignments = []
        
    def _load_complete_teacher_mapping(self):
        """教師マッピングを読み込み"""
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
    
    def evacuate_problematic_slots(self):
        """問題の多い時間帯から授業を一時退避"""
        print("=== 問題時間帯からの授業退避 ===\n")
        
        problematic_slots = [
            ("火", "5"),  # 最も問題が多い
            ("金", "3"),  # 2番目に問題が多い
            ("火", "3"),  # その他の問題時間
        ]
        
        for day, period in problematic_slots:
            print(f"\n【{day}{period}限の退避】")
            col = self.get_cell(day, period)
            if not col:
                continue
            
            evacuated_count = 0
            for row in range(2, len(self.df)):
                class_name = self.df.iloc[row, 0]
                if pd.isna(class_name) or class_name == "":
                    continue
                
                subject = self.df.iloc[row, col]
                if pd.notna(subject) and subject != "" and not self.is_fixed_subject(subject):
                    # 教師情報も保存
                    teacher = self.teacher_mapping.get((class_name, subject))
                    self.removed_assignments.append({
                        'class': class_name,
                        'subject': subject,
                        'teacher': teacher,
                        'original_slot': (day, period)
                    })
                    
                    # 一時的に空にする
                    self.df.iloc[row, col] = ""
                    evacuated_count += 1
            
            print(f"  {evacuated_count}個の授業を退避")
        
        print(f"\n合計{len(self.removed_assignments)}個の授業を退避しました")
    
    def analyze_teacher_availability(self):
        """各教師の空き時間を分析"""
        teacher_schedule = defaultdict(lambda: defaultdict(list))
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in ["1", "2", "3", "4", "5"]:
                col = self.get_cell(day, period)
                if not col:
                    continue
                
                # 各時間の教師配置を確認
                for row in range(2, len(self.df)):
                    class_name = self.df.iloc[row, 0]
                    if pd.isna(class_name):
                        continue
                    
                    subject = self.df.iloc[row, col]
                    if pd.notna(subject) and subject != "":
                        teacher = self.teacher_mapping.get((class_name, subject))
                        if teacher:
                            teacher_schedule[teacher][(day, period)].append(class_name)
        
        return teacher_schedule
    
    def redistribute_assignments(self):
        """退避した授業を最適に再配置"""
        print("\n\n=== 授業の再配置 ===")
        
        # 教師の空き時間を分析
        teacher_schedule = self.analyze_teacher_availability()
        
        # 優先度順にソート（教師の負荷が高い順）
        sorted_assignments = sorted(self.removed_assignments, 
                                  key=lambda x: len(teacher_schedule.get(x['teacher'], {})), 
                                  reverse=True)
        
        placed_count = 0
        
        for assignment in sorted_assignments:
            class_name = assignment['class']
            subject = assignment['subject']
            teacher = assignment['teacher']
            original_slot = assignment['original_slot']
            
            print(f"\n{class_name}の{subject}（{teacher}先生）を配置:")
            
            # 最適なスロットを探す
            best_slot = self.find_best_slot_for_teacher(
                class_name, subject, teacher, teacher_schedule, original_slot
            )
            
            if best_slot:
                day, period = best_slot
                col = self.get_cell(day, period)
                class_row = self.get_class_row(class_name)
                
                if col and class_row:
                    # 既存の授業と交換
                    existing = self.df.iloc[class_row, col]
                    if pd.notna(existing) and existing != "":
                        # 元の場所に配置
                        orig_col = self.get_cell(*original_slot)
                        if orig_col and self.df.iloc[class_row, orig_col] == "":
                            self.df.iloc[class_row, orig_col] = existing
                            print(f"  既存の{existing}を{original_slot[0]}{original_slot[1]}限へ移動")
                    
                    self.df.iloc[class_row, col] = subject
                    
                    # 教師スケジュールを更新
                    teacher_schedule[teacher][(day, period)].append(class_name)
                    
                    print(f"  ✓ {day}{period}限に配置")
                    placed_count += 1
            else:
                print(f"  ✗ 配置先が見つかりません")
        
        print(f"\n{placed_count}/{len(self.removed_assignments)}個の授業を再配置しました")
    
    def find_best_slot_for_teacher(self, class_name, subject, teacher, teacher_schedule, avoid_slot):
        """教師の制約を考慮して最適なスロットを見つける"""
        class_row = self.get_class_row(class_name)
        if not class_row:
            return None
        
        candidate_slots = []
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in ["1", "2", "3", "4", "5"]:
                if (day, period) == avoid_slot:
                    continue
                
                col = self.get_cell(day, period)
                if not col:
                    continue
                
                # 教師がその時間に空いているか
                if (day, period) in teacher_schedule.get(teacher, {}):
                    continue
                
                # 日内重複チェック
                if self.would_cause_daily_duplicate(class_name, subject, day):
                    continue
                
                # その時間の競合数を計算
                conflict_count = self.count_conflicts_at(day, period)
                
                # 固定科目チェック
                current = self.df.iloc[class_row, col]
                if self.is_fixed_subject(current):
                    continue
                
                candidate_slots.append({
                    'slot': (day, period),
                    'conflicts': conflict_count,
                    'empty': pd.isna(current) or current == ""
                })
        
        if not candidate_slots:
            return None
        
        # 空きスロットを優先、次に競合の少ないスロット
        candidate_slots.sort(key=lambda x: (not x['empty'], x['conflicts']))
        
        return candidate_slots[0]['slot']
    
    def would_cause_daily_duplicate(self, class_name, subject, day):
        """日内重複が発生するかチェック"""
        class_row = self.get_class_row(class_name)
        if not class_row:
            return True
        
        for period in range(1, 7):
            col = self.get_cell(day, str(period))
            if col:
                s = self.df.iloc[class_row, col]
                if s == subject:
                    return True
        
        return False
    
    def count_conflicts_at(self, day, period):
        """特定時間の競合数をカウント"""
        col = self.get_cell(day, period)
        if not col:
            return 0
        
        teacher_assignments = defaultdict(list)
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name):
                continue
            
            subject = self.df.iloc[row, col]
            if pd.notna(subject) and subject != "":
                teacher = self.teacher_mapping.get((class_name, subject))
                if teacher:
                    teacher_assignments[teacher].append(class_name)
        
        conflicts = sum(1 for assignments in teacher_assignments.values() if len(assignments) > 1)
        return conflicts
    
    def fix_exchange_class_sync(self):
        """交流学級の同期を修正"""
        print("\n\n=== 交流学級の同期修正 ===")
        
        exchange_pairs = [
            ("1年6組", "1年1組"),
            ("1年7組", "1年2組"),
            ("2年6組", "2年3組"),
            ("2年7組", "2年2組"),
            ("3年6組", "3年3組"),
            ("3年7組", "3年2組"),
        ]
        
        sync_count = 0
        
        for exchange_class, parent_class in exchange_pairs:
            exchange_row = self.get_class_row(exchange_class)
            parent_row = self.get_class_row(parent_class)
            
            if not (exchange_row and parent_row):
                continue
            
            for col in range(1, len(self.df.columns)):
                exchange_subject = self.df.iloc[exchange_row, col]
                parent_subject = self.df.iloc[parent_row, col]
                
                # 自立活動の時は特別処理
                if exchange_subject in ["自立", "日生", "生単", "作業"]:
                    if parent_subject not in ["数", "英"]:
                        # 親学級を数学か英語に変更する必要がある
                        continue
                elif exchange_subject != parent_subject and not self.is_fixed_subject(exchange_subject):
                    # 同期が必要
                    self.df.iloc[exchange_row, col] = parent_subject
                    sync_count += 1
        
        print(f"{sync_count}箇所の同期を実行しました")
    
    def final_verification(self):
        """最終検証"""
        print("\n\n=== 最終検証 ===")
        
        total_conflicts = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in ["1", "2", "3", "4", "5", "6"]:
                conflicts = self.count_conflicts_at(day, period)
                if conflicts > 0:
                    total_conflicts += conflicts
        
        print(f"総競合数: {total_conflicts}件")
        
        # 特に問題の多かった時間帯を再チェック
        print("\n【主要時間帯の状況】")
        for day, period in [("火", "5"), ("金", "3"), ("火", "3")]:
            conflicts = self.count_conflicts_at(day, period)
            print(f"{day}{period}限: {conflicts}件の競合")
    
    def save(self):
        self.df.to_csv(self.output_path, index=False, header=False)
        print(f"\n根本的再構築完了: {self.output_path}")

def main():
    reconstructor = RadicalReconstructor()
    reconstructor.evacuate_problematic_slots()
    reconstructor.redistribute_assignments()
    reconstructor.fix_exchange_class_sync()
    reconstructor.final_verification()
    reconstructor.save()

if __name__ == "__main__":
    main()