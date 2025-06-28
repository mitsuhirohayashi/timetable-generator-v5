#!/usr/bin/env python3
"""特定の教師重複問題を分析し修正するスクリプト"""

import csv
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional


class SpecificIssueFixer:
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
        
    def analyze_specific_conflicts(self):
        """特定の教師重複を詳細に分析"""
        print("\n=== 特定の教師重複の詳細分析 ===")
        
        # 塚本先生の金曜3校時
        print("\n【塚本先生の金曜3校時問題】")
        tsukamoto_classes = []
        for class_name in self.classes:
            if '金' in self.schedule[class_name] and 3 in self.schedule[class_name]['金']:
                subject = self.schedule[class_name]['金'][3]
                if subject == '音':
                    teacher = self.get_teacher(class_name, subject)
                    if teacher == '塚本':
                        tsukamoto_classes.append(class_name)
        
        print(f"塚本先生が金曜3校時に教えているクラス: {', '.join(tsukamoto_classes)}")
        
        # 5組の合同授業確認
        grade5_in_conflict = [c for c in tsukamoto_classes if c in self.grade5_classes]
        if len(grade5_in_conflict) >= 2:
            print("→ 5組の合同授業として正常です")
        
        # その他のクラス
        other_classes = [c for c in tsukamoto_classes if c not in self.grade5_classes]
        if other_classes:
            print(f"→ 問題のあるクラス: {', '.join(other_classes)}")
            
            # 修正案を提示
            for cls in other_classes:
                print(f"\n  {cls}の金曜日の時間割:")
                for period in range(1, 7):
                    subj = self.schedule[cls]['金'].get(period, '')
                    print(f"    {period}校時: {subj}")
                    
    def fix_specific_issue(self):
        """特定の問題を修正"""
        print("\n=== 特定問題の修正 ===")
        
        # 1年3組の金曜3校時を他の時間と入れ替える
        if '1年3組' in self.classes:
            # 金曜の他の時間を探す
            friday_schedule = self.schedule['1年3組']['金']
            
            # 音楽でない時間を探す
            for period in [1, 2, 4, 5]:  # 3と6以外
                if period in friday_schedule:
                    subj = friday_schedule[period]
                    if subj and subj != '音' and subj not in ['欠', 'YT', '道', '総', '学']:
                        # 交換
                        print(f"1年3組の金曜{period}校時({subj})と3校時(音)を交換")
                        self.schedule['1年3組']['金'][3] = subj
                        self.schedule['1年3組']['金'][period] = '音'
                        break
                        
    def find_all_conflicts(self) -> List[Tuple[str, str, int, List[Tuple[str, str]]]]:
        """すべての教師重複を検出"""
        teacher_schedule = defaultdict(lambda: defaultdict(list))
        
        for class_name in self.classes:
            for day in self.days:
                if day not in self.schedule[class_name]:
                    continue
                    
                for period in range(1, 7):
                    subject = self.schedule[class_name][day].get(period, '')
                    
                    if subject:
                        teacher = self.get_teacher(class_name, subject)
                        if teacher:
                            teacher_schedule[teacher][(day, period)].append((class_name, subject))
        
        # 重複を検出
        conflicts = []
        for teacher, schedule in teacher_schedule.items():
            for (day, period), classes in schedule.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for cls, _ in classes if cls in self.grade5_classes)
                    if grade5_count == len(classes) and grade5_count > 1:
                        continue
                    conflicts.append((teacher, day, period, classes))
                    
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
        
    def fix_exchange_sync(self):
        """交流学級の同期を修正"""
        print("\n=== 交流学級同期の修正 ===")
        
        violations = self.find_exchange_sync_violations()
        
        for exchange_class, parent_class, day, period, exchange_subject, parent_subject in violations:
            print(f"\n{exchange_class}と{parent_class}の{day}曜{period}校時:")
            print(f"  交流学級: {exchange_subject}, 親学級: {parent_subject}")
            
            # 交流学級が自立活動でない場合、親学級と同じにする
            if exchange_subject != '自立':
                self.schedule[exchange_class][day][period] = parent_subject
                print(f"  → {exchange_class}を{parent_subject}に変更")
                
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
        
        # 空きスロットに"空"と表示
        empty_row = ['']
        empty_row.extend(['空' if r == '' else r for r in row[1:]])
        rows.append(empty_row)
        
        # CSVファイルに書き込み
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
            
    def fill_empty_slots(self):
        """3年6組の空きスロットを埋める"""
        print("\n=== 3年6組の空きスロットを埋める ===")
        
        if '3年6組' not in self.classes:
            return
            
        # 3年6組の担任を確認（財津先生）
        empty_slots = []
        for day in self.days:
            if day in self.schedule['3年6組']:
                for period in range(1, 7):
                    if not self.schedule['3年6組'][day].get(period, ''):
                        empty_slots.append((day, period))
                        
        print(f"3年6組の空きスロット: {len(empty_slots)}個")
        
        # 親学級（3年3組）と同じにする
        for day, period in empty_slots:
            if day in self.schedule['3年3組'] and period in self.schedule['3年3組'][day]:
                parent_subject = self.schedule['3年3組'][day][period]
                if parent_subject:
                    self.schedule['3年6組'][day][period] = parent_subject
                    print(f"  {day}曜{period}校時: {parent_subject}（親学級に合わせる）")
                    
    def run(self):
        """メイン処理"""
        print("=== 特定問題の分析と修正 ===")
        
        # データ読み込み
        self.load_schedule('data/output/output_fixed.csv')
        self.load_teacher_mapping('data/config/teacher_subject_mapping.csv')
        
        # 特定の問題を分析
        self.analyze_specific_conflicts()
        
        # 初期状態
        print("\n初期違反状態:")
        initial_conflicts = self.find_all_conflicts()
        initial_sync_violations = self.find_exchange_sync_violations()
        print(f"教師重複: {len(initial_conflicts)}件")
        print(f"交流学級同期違反: {len(initial_sync_violations)}件")
        
        # 修正実行
        self.fix_specific_issue()
        self.fix_exchange_sync()
        self.fill_empty_slots()
        
        # 最終状態
        print("\n最終違反状態:")
        final_conflicts = self.find_all_conflicts()
        final_sync_violations = self.find_exchange_sync_violations()
        print(f"教師重複: {len(final_conflicts)}件")
        print(f"交流学級同期違反: {len(final_sync_violations)}件")
        
        # 残存する重複を表示
        if final_conflicts:
            print("\n残存する教師重複:")
            for teacher, day, period, classes in final_conflicts[:10]:  # 最初の10件
                print(f"  {teacher}先生: {day}曜{period}校時 - {', '.join([f'{cls}({subj})' for cls, subj in classes])}")
        
        # 結果保存
        self.save_schedule('data/output/output_final.csv')
        
        print("\n=== 処理完了 ===")


if __name__ == "__main__":
    fixer = SpecificIssueFixer()
    fixer.run()