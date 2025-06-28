#!/usr/bin/env python3
"""最終的な教師重複と交流学級同期違反を修正するスクリプト（シンプル版）"""

import csv
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional


class SimpleScheduleFixer:
    def __init__(self):
        # 交流学級マッピング
        self.exchange_pairs = {
            '1年6組': '1年1組',
            '1年7組': '1年2組', 
            '2年6組': '2年3組',
            '2年7組': '2年2組',
            '3年6組': '3年3組',
            '3年7組': '3年2組',
        }
        
        # 固定科目
        self.fixed_subjects = {'欠', 'YT', '学', '学活', '総', '総合', '道', '道徳', '学総', '行', '行事', 'テスト', '技家'}
        
        # 主要教科
        self.main_subjects = {'国', '数', '英', '理', '社'}
        
        # 5組クラス
        self.grade5_classes = {'1年5組', '2年5組', '3年5組'}
        
        self.schedule = {}
        self.teacher_mapping = {}
        self.classes = []
        self.days = ['月', '火', '水', '木', '金']
        
    def load_schedule(self, filename: str):
        """スケジュールを読み込む"""
        print(f"スケジュールを読み込み中: {filename}")
        
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
        # ヘッダー行から日と時限を取得
        header1 = rows[0]  # 曜日
        header2 = rows[1]  # 時限
        
        # クラスごとにスケジュールを読み込む
        for row_idx in range(2, len(rows)):
            if not rows[row_idx][0]:  # 空行はスキップ
                continue
                
            class_name = rows[row_idx][0]
            self.classes.append(class_name)
            self.schedule[class_name] = {}
            
            for col_idx in range(1, len(rows[row_idx])):
                if col_idx >= len(header1):
                    break
                    
                day = header1[col_idx]
                period = int(header2[col_idx]) if header2[col_idx].isdigit() else 0
                
                if day and period:
                    if day not in self.schedule[class_name]:
                        self.schedule[class_name][day] = {}
                    
                    subject = rows[row_idx][col_idx].strip() if rows[row_idx][col_idx] else ''
                    self.schedule[class_name][day][period] = subject
                    
    def load_teacher_mapping(self, filename: str):
        """教師マッピングを読み込む"""
        print(f"教師マッピングを読み込み中: {filename}")
        
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # ヘッダーをスキップ
            
            for row in reader:
                if len(row) >= 4:
                    teacher = row[0].strip()
                    subject = row[1].strip()
                    grade = row[2].strip()
                    class_num = row[3].strip()
                    
                    class_name = f"{grade}年{class_num}組"
                    key = (class_name, subject)
                    self.teacher_mapping[key] = teacher
                    
    def get_teacher(self, class_name: str, subject: str) -> Optional[str]:
        """クラスと教科から教師を取得"""
        return self.teacher_mapping.get((class_name, subject))
        
    def find_teacher_conflicts(self) -> Dict[Tuple[str, int], List[Tuple[str, str, str]]]:
        """教師の重複を検出"""
        teacher_schedule = defaultdict(lambda: defaultdict(list))
        
        for class_name in self.classes:
            for day in self.days:
                if day not in self.schedule[class_name]:
                    continue
                    
                for period in range(1, 7):
                    subject = self.schedule[class_name][day].get(period, '')
                    
                    if subject and subject not in self.fixed_subjects:
                        teacher = self.get_teacher(class_name, subject)
                        if teacher:
                            teacher_schedule[teacher][(day, period)].append((class_name, subject))
        
        # 重複を検出
        conflicts = {}
        for teacher, schedule in teacher_schedule.items():
            for (day, period), classes in schedule.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for cls, _ in classes if cls in self.grade5_classes)
                    if grade5_count == len(classes) and grade5_count > 1:
                        continue
                    conflicts[(day, period)] = [(teacher, cls, subj) for cls, subj in classes]
                    
        return conflicts
    
    def find_exchange_sync_violations(self) -> List[Tuple[str, str, str, int, str, str]]:
        """交流学級の同期違反を検出"""
        violations = []
        
        for exchange_class, parent_class in self.exchange_pairs.items():
            if exchange_class not in self.classes or parent_class not in self.classes:
                continue
                
            for day in self.days:
                if day not in self.schedule[exchange_class] or day not in self.schedule[parent_class]:
                    continue
                    
                for period in range(1, 7):
                    exchange_subject = self.schedule[exchange_class][day].get(period, '')
                    parent_subject = self.schedule[parent_class][day].get(period, '')
                    
                    # 交流学級が自立活動の場合
                    if exchange_subject == '自立':
                        if parent_subject not in ['数', '英']:
                            violations.append((exchange_class, parent_class, day, period, exchange_subject, parent_subject))
                    # 交流学級が自立活動でない場合、親学級と同じでなければならない
                    elif exchange_subject and parent_subject and exchange_subject != parent_subject:
                        violations.append((exchange_class, parent_class, day, period, exchange_subject, parent_subject))
                        
        return violations
    
    def swap_periods(self, class_name: str, day: str, period1: int, period2: int) -> bool:
        """同じクラスの2つの時限を交換"""
        if day not in self.schedule[class_name]:
            return False
            
        subject1 = self.schedule[class_name][day].get(period1, '')
        subject2 = self.schedule[class_name][day].get(period2, '')
        
        # 固定科目は交換しない
        if subject1 in self.fixed_subjects or subject2 in self.fixed_subjects:
            return False
            
        self.schedule[class_name][day][period1] = subject2
        self.schedule[class_name][day][period2] = subject1
        
        return True
    
    def fix_teacher_conflicts(self) -> int:
        """教師の重複を修正"""
        print("\n=== 教師重複の修正 ===")
        fixed_count = 0
        max_iterations = 100
        iteration = 0
        
        while iteration < max_iterations:
            conflicts = self.find_teacher_conflicts()
            if not conflicts:
                break
                
            iteration += 1
            
            for (day, period), teacher_assignments in conflicts.items():
                print(f"\n{day}曜{period}校時の重複:")
                for teacher, class_name, subject in teacher_assignments:
                    print(f"  - {teacher}先生: {class_name} {subject}")
                
                # 最初のクラスを残し、他のクラスの授業を移動
                base_teacher, base_class, base_subject = teacher_assignments[0]
                
                for teacher, conflict_class, conflict_subject in teacher_assignments[1:]:
                    # 同じ日の他の時間帯と交換を試みる
                    moved = False
                    for alt_period in range(1, 7):
                        if alt_period == period:
                            continue
                            
                        alt_subject = self.schedule[conflict_class][day].get(alt_period, '')
                        if not alt_subject or alt_subject in self.fixed_subjects:
                            continue
                            
                        # 交換先でも重複が発生しないか確認
                        alt_teacher = self.get_teacher(conflict_class, alt_subject)
                        conflict_free = True
                        
                        if alt_teacher:
                            for cls in self.classes:
                                check_subject = self.schedule[cls][day].get(period, '')
                                if check_subject and self.get_teacher(cls, check_subject) == alt_teacher and cls != conflict_class:
                                    conflict_free = False
                                    break
                        
                        if conflict_free:
                            if self.swap_periods(conflict_class, day, period, alt_period):
                                print(f"  → {conflict_class}の{day}曜{period}校時と{alt_period}校時を交換")
                                fixed_count += 1
                                moved = True
                                break
                    
                    if moved:
                        break
        
        return fixed_count
    
    def fix_exchange_sync_violations(self) -> int:
        """交流学級の同期違反を修正"""
        print("\n=== 交流学級同期の修正 ===")
        fixed_count = 0
        
        violations = self.find_exchange_sync_violations()
        
        for exchange_class, parent_class, day, period, exchange_subject, parent_subject in violations:
            print(f"\n{exchange_class}と{parent_class}の{day}曜{period}校時:")
            print(f"  交流学級: {exchange_subject}, 親学級: {parent_subject}")
            
            # 交流学級が自立活動の場合
            if exchange_subject == '自立':
                # 親学級を数学か英語に変更する必要がある
                target_subjects = ['数', '英']
                for target_subject in target_subjects:
                    # その日の他の時間帯でtarget_subjectを探す
                    for alt_period in range(1, 7):
                        if alt_period == period:
                            continue
                            
                        alt_subject = self.schedule[parent_class][day].get(alt_period, '')
                        if alt_subject == target_subject:
                            if self.swap_periods(parent_class, day, period, alt_period):
                                print(f"  → {parent_class}の{day}曜{period}校時を{target_subject}に変更")
                                fixed_count += 1
                                break
                    if fixed_count > 0:
                        break
            else:
                # 交流学級を親学級と同じにする
                self.schedule[exchange_class][day][period] = parent_subject
                print(f"  → {exchange_class}を{parent_subject}に変更")
                fixed_count += 1
        
        return fixed_count
    
    def fill_empty_slots(self) -> int:
        """空きスロットを埋める"""
        print("\n=== 空きスロットの充填 ===")
        filled_count = 0
        
        for class_name in self.classes:
            for day in self.days:
                if day not in self.schedule[class_name]:
                    self.schedule[class_name][day] = {}
                    
                for period in range(1, 7):
                    subject = self.schedule[class_name][day].get(period, '')
                    
                    if not subject:
                        # その日に既に配置されている科目を確認
                        day_subjects = set()
                        for p in range(1, 7):
                            s = self.schedule[class_name][day].get(p, '')
                            if s:
                                day_subjects.add(s)
                        
                        # 利用可能な科目を探す（主要教科を優先）
                        available_subjects = []
                        for (cls, subj), teacher in self.teacher_mapping.items():
                            if cls == class_name and subj not in self.fixed_subjects and subj not in day_subjects:
                                if subj in self.main_subjects:
                                    available_subjects.insert(0, subj)
                                else:
                                    available_subjects.append(subj)
                        
                        if available_subjects:
                            self.schedule[class_name][day][period] = available_subjects[0]
                            print(f"  {class_name}の{day}曜{period}校時に{available_subjects[0]}を配置")
                            filled_count += 1
        
        return filled_count
    
    def save_schedule(self, filename: str):
        """スケジュールを保存"""
        print(f"\nスケジュールを保存中: {filename}")
        
        # 出力データの準備
        rows = []
        
        # ヘッダー行
        header1 = ['基本時間割']
        header2 = ['']
        for day in self.days:
            for period in range(1, 7):
                header1.append(day)
                header2.append(str(period))
        
        rows.append(header1)
        rows.append(header2)
        
        # クラスごとのデータ
        standard_order = [
            '1年1組', '1年2組', '1年3組', '1年5組', '1年6組', '1年7組',
            '2年1組', '2年2組', '2年3組', '2年5組', '2年6組', '2年7組',
            '',  # 空行
            '3年1組', '3年2組', '3年3組', '3年5組', '3年6組', '3年7組'
        ]
        
        for class_name in standard_order:
            if class_name == '':
                rows.append([''])
                continue
                
            if class_name not in self.classes:
                continue
                
            row = [class_name]
            for day in self.days:
                for period in range(1, 7):
                    subject = ''
                    if day in self.schedule[class_name]:
                        subject = self.schedule[class_name][day].get(period, '')
                    row.append(subject)
            
            rows.append(row)
        
        # CSVファイルに書き込み
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
    
    def verify_fixes(self):
        """修正後の違反を確認"""
        print("\n=== 修正後の検証 ===")
        
        # 教師重複を再確認
        conflicts = self.find_teacher_conflicts()
        print(f"\n教師重複: {len(conflicts)}件")
        
        # 交流学級同期を再確認
        sync_violations = self.find_exchange_sync_violations()
        print(f"交流学級同期違反: {len(sync_violations)}件")
        
        # 空きスロットを確認
        empty_count = 0
        for class_name in self.classes:
            for day in self.days:
                if day in self.schedule[class_name]:
                    for period in range(1, 7):
                        if not self.schedule[class_name][day].get(period, ''):
                            empty_count += 1
        
        print(f"空きスロット: {empty_count}件")
        
        return len(conflicts), len(sync_violations), empty_count
    
    def run(self):
        """メイン処理"""
        print("=== 最終修正処理開始（シンプル版） ===")
        
        # データ読み込み
        self.load_schedule('data/output/output_fixed.csv')
        self.load_teacher_mapping('data/config/teacher_subject_mapping.csv')
        
        # 初期状態を確認
        print("\n初期違反状態:")
        initial_conflicts = self.find_teacher_conflicts()
        initial_sync_violations = self.find_exchange_sync_violations()
        print(f"教師重複: {len(initial_conflicts)}件")
        print(f"交流学級同期違反: {len(initial_sync_violations)}件")
        
        # 修正実行
        teacher_fixed = self.fix_teacher_conflicts()
        sync_fixed = self.fix_exchange_sync_violations() 
        filled = self.fill_empty_slots()
        
        print(f"\n修正結果:")
        print(f"教師重複修正: {teacher_fixed}件")
        print(f"交流学級同期修正: {sync_fixed}件")
        print(f"空きスロット充填: {filled}件")
        
        # 最終検証
        final_conflicts, final_sync, final_empty = self.verify_fixes()
        
        # 結果保存
        self.save_schedule('data/output/output_final.csv')
        
        print("\n=== 処理完了 ===")
        print(f"残存違反数:")
        print(f"  教師重複: {final_conflicts}件")
        print(f"  交流学級同期: {final_sync}件")
        print(f"  空きスロット: {final_empty}件")


if __name__ == "__main__":
    fixer = SimpleScheduleFixer()
    fixer.run()