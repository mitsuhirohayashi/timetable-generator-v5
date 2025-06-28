#!/usr/bin/env python3
"""
直接的な違反修正スクリプト

現在のoutput.csvの違反を直接修正します。
"""
import os
import sys
import csv
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# プロジェクトルートのパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger.info("=== 直接違反修正を開始 ===\n")
    
    # CSVファイルを読み込み
    input_file = 'data/output/output.csv'
    output_file = 'data/output/output_fixed_direct.csv'
    
    # データを読み込み
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行を保持
    header_rows = rows[:2]
    data_rows = rows[2:]
    
    # 時間割データを2次元配列として扱う
    schedule = []
    class_names = []
    
    for row in data_rows:
        if row and row[0]:  # クラス名がある行
            class_names.append(row[0])
            schedule.append(row[1:])  # 時間割部分
        else:
            class_names.append("")
            schedule.append([""] * 30)
    
    # 教師マッピング
    subject_teachers = {
        '国': '智田先生',
        '数': '井上先生',
        '英': '蒲地先生',
        '理': '梶永先生',
        '社': '神田先生',
        '音': '今先生',
        '美': '平野先生',
        '体': '野田先生',
        '技': '國本先生',
        '家': '石原先生',
        '保': '野田先生',
        '技家': '技家担当先生',
    }
    
    # 担任マッピング
    homeroom_teachers = {
        '1年1組': '金子ひ先生',
        '1年2組': '井野口先生',
        '1年3組': '梶永先生',
        '2年1組': '塚本先生',
        '2年2組': '野口先生',
        '2年3組': '永山先生',
        '3年1組': '白石先生',
        '3年2組': '森山先生',
        '3年3組': '北先生',
        '1年5組': '金子み先生',
        '2年5組': '金子み先生',
        '3年5組': '金子み先生',
    }
    
    fixed_count = 0
    
    # 1. 月曜6限の欠課を修正
    logger.info("1. 月曜6限の欠課を修正中...")
    monday_6th_col = 5  # 月曜6限のカラムインデックス
    for i, class_name in enumerate(class_names):
        if class_name and class_name != "":
            if schedule[i][monday_6th_col] != '欠':
                schedule[i][monday_6th_col] = '欠'
                fixed_count += 1
    logger.info(f"  → {fixed_count}クラスの月曜6限を修正")
    
    # 2. 教師重複を修正（簡易的に重複を検出して修正）
    logger.info("\n2. 教師重複を修正中...")
    teacher_conflict_fixes = 0
    
    for period in range(30):  # 各時限
        # その時限の教師使用状況を収集
        teacher_usage = defaultdict(list)
        
        for i, class_name in enumerate(class_names):
            if class_name and schedule[i][period]:
                subject = schedule[i][period]
                if subject in subject_teachers:
                    teacher = subject_teachers[subject]
                    teacher_usage[teacher].append((i, class_name))
        
        # 重複を修正
        for teacher, classes in teacher_usage.items():
            if len(classes) > 1:
                # 5組の合同授業は除外
                non_grade5 = [(i, c) for i, c in classes if '5組' not in c]
                if non_grade5:
                    classes = non_grade5
                
                if len(classes) > 1:
                    # 最初のクラス以外を変更
                    for idx, (i, class_name) in enumerate(classes[1:]):
                        # 代替科目を探す
                        alt_subject = find_alternative_subject(schedule[i], period)
                        if alt_subject:
                            schedule[i][period] = alt_subject
                            teacher_conflict_fixes += 1
    
    logger.info(f"  → {teacher_conflict_fixes}件の教師重複を修正")
    
    # 3. 日内重複を修正
    logger.info("\n3. 日内重複を修正中...")
    daily_duplicate_fixes = 0
    
    for i, class_name in enumerate(class_names):
        if not class_name:
            continue
        
        for day_start in range(0, 30, 6):  # 各曜日の開始位置
            # その日の科目をカウント
            day_subjects = defaultdict(list)
            for period_offset in range(6):
                period = day_start + period_offset
                subject = schedule[i][period]
                if subject and subject not in ['欠', 'YT', '学', '道', '総', '学総', '行']:
                    day_subjects[subject].append(period)
            
            # 重複を修正
            for subject, periods in day_subjects.items():
                if len(periods) > 1:
                    # 最初の時限以外を変更
                    for period in periods[1:]:
                        alt_subject = find_alternative_subject(schedule[i], period, exclude=subject)
                        if alt_subject:
                            schedule[i][period] = alt_subject
                            daily_duplicate_fixes += 1
    
    logger.info(f"  → {daily_duplicate_fixes}件の日内重複を修正")
    
    # 4. 空きコマを埋める
    logger.info("\n4. 空きコマを埋める...")
    empty_fills = 0
    
    for i, class_name in enumerate(class_names):
        if not class_name:
            continue
        
        for period in range(30):
            if not schedule[i][period] or schedule[i][period] == "":
                # 不足している教科を選択
                needed_subject = find_needed_subject(schedule[i], period, class_name)
                if needed_subject:
                    schedule[i][period] = needed_subject
                    empty_fills += 1
    
    logger.info(f"  → {empty_fills}個の空きコマを埋めました")
    
    # 5. 5組を同期
    logger.info("\n5. 5組を同期中...")
    sync_count = 0
    
    # 5組のインデックスを探す
    grade5_indices = []
    for i, class_name in enumerate(class_names):
        if '5組' in class_name:
            grade5_indices.append(i)
    
    if len(grade5_indices) >= 2:
        for period in range(30):
            # 各5組の科目を収集
            subjects = []
            for i in grade5_indices:
                if schedule[i][period]:
                    subjects.append(schedule[i][period])
            
            if subjects:
                # 最も多い科目を選択
                most_common = max(set(subjects), key=subjects.count)
                
                # 全5組を統一
                for i in grade5_indices:
                    if schedule[i][period] != most_common:
                        schedule[i][period] = most_common
                        sync_count += 1
    
    logger.info(f"  → {sync_count}コマを同期")
    
    # 結果を保存
    logger.info("\n結果を保存中...")
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        # ヘッダーを書き込み
        writer.writerows(header_rows)
        
        # データを書き込み
        for i, class_name in enumerate(class_names):
            row = [class_name] + schedule[i]
            writer.writerow(row)
    
    # 元のファイルも更新
    with open(input_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(header_rows)
        for i, class_name in enumerate(class_names):
            row = [class_name] + schedule[i]
            writer.writerow(row)
    
    logger.info(f"\n修正完了！")
    logger.info(f"出力ファイル: {output_file}")
    logger.info(f"元ファイルも更新: {input_file}")
    
    # 違反チェックを実行
    logger.info("\n=== 修正後の違反チェック ===")
    os.system("python3 scripts/analysis/check_violations.py")


def find_alternative_subject(class_schedule, period, exclude=None):
    """代替科目を探す"""
    # 主要教科
    main_subjects = ['国', '数', '英', '理', '社']
    skill_subjects = ['音', '美', '体', '技', '家']
    
    # その日の科目を収集
    day_start = (period // 6) * 6
    day_subjects = set()
    for p in range(day_start, day_start + 6):
        if class_schedule[p]:
            day_subjects.add(class_schedule[p])
    
    # まだその日に配置されていない主要教科
    for subject in main_subjects:
        if subject not in day_subjects and subject != exclude:
            return subject
    
    # 技能教科
    for subject in skill_subjects:
        if subject not in day_subjects and subject != exclude:
            return subject
    
    return None


def find_needed_subject(class_schedule, period, class_name):
    """必要な教科を探す"""
    # 標準時数（簡易版）
    standard_hours = {
        '国': 4, '数': 4, '英': 4, '理': 3, '社': 3,
        '音': 2, '美': 2, '技': 1, '家': 1, '体': 3
    }
    
    # 現在の時数をカウント
    current_hours = defaultdict(int)
    for p in range(30):
        if class_schedule[p]:
            current_hours[class_schedule[p]] += 1
    
    # その日の科目を収集
    day_start = (period // 6) * 6
    day_subjects = set()
    for p in range(day_start, day_start + 6):
        if class_schedule[p]:
            day_subjects.add(class_schedule[p])
    
    # 不足している教科で、その日にまだない教科を優先
    best_subject = None
    max_shortage = 0
    
    for subject, target in standard_hours.items():
        current = current_hours.get(subject, 0)
        shortage = target - current
        
        if shortage > 0 and subject not in day_subjects:
            if shortage > max_shortage:
                max_shortage = shortage
                best_subject = subject
    
    # 見つからない場合は、単に不足している教科
    if not best_subject:
        for subject, target in standard_hours.items():
            current = current_hours.get(subject, 0)
            shortage = target - current
            
            if shortage > max_shortage:
                max_shortage = shortage
                best_subject = subject
    
    return best_subject


if __name__ == "__main__":
    main()