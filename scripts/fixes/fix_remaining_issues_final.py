#!/usr/bin/env python3
"""
残りの問題を修正する最終スクリプト

1. 空きコマを埋める
2. 教師重複を修正
3. 月曜6限の欠を確実に設定
"""
import os
import sys
import csv
import logging
from collections import defaultdict

# プロジェクトルートのパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger.info("=== 残りの問題を修正 ===\n")
    
    # ファイルパス
    output_file = 'data/output/output.csv'
    
    # output.csvを読み込み
    with open(output_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行を保持
    header_rows = rows[:2]
    data_rows = rows[2:]
    
    # 教師マッピング
    subject_teachers = {
        '国': '智田先生',
        '数': '井上先生',
        '英': '蒲地先生',
        '理': '梶永先生',
        '社': '神田先生',
        '音': '今先生',
        '美': '平野先生',
        '保': '野田先生',
        '技': '國本先生',
        '家': '石原先生',
    }
    
    # 標準時数
    standard_hours = {
        '国': 4.0,
        '数': 4.0,
        '英': 4.0,
        '理': 3.0,
        '社': 3.0,
        '音': 1.3,
        '美': 1.3,
        '技': 1.0,
        '家': 1.0,
        '保': 3.0,
    }
    
    fix_count = 0
    
    # 1. 月曜6限の欠を修正
    logger.info("1. 月曜6限の欠を修正...")
    monday_6th_idx = 6  # CSVのインデックス（0から始まるが、1列目はクラス名）
    for i, row in enumerate(data_rows):
        if row and row[0]:  # クラス名がある行
            if monday_6th_idx < len(row) and row[monday_6th_idx] != '欠':
                logger.info(f"  {row[0]}: {row[monday_6th_idx]} → 欠")
                row[monday_6th_idx] = '欠'
                fix_count += 1
    
    # 2. 空きコマを埋める
    logger.info("\n2. 空きコマを埋める...")
    for i, row in enumerate(data_rows):
        if not row or not row[0]:  # 空行またはクラス名なし
            continue
        
        class_name = row[0]
        
        # 現在の時数をカウント
        current_hours = defaultdict(int)
        for j in range(1, 31):  # 1-30列（月1〜金6）
            if j < len(row) and row[j]:
                subject = row[j]
                if subject in standard_hours:
                    current_hours[subject] += 1
        
        # 空きコマを探して埋める
        for j in range(1, 31):
            if j < len(row) and (not row[j] or row[j] == ""):
                # その日の科目を収集
                day_start = ((j - 1) // 6) * 6 + 1
                day_subjects = set()
                for k in range(day_start, day_start + 6):
                    if k < len(row) and row[k]:
                        day_subjects.add(row[k])
                
                # 最も不足している科目を選択
                best_subject = None
                max_shortage = 0
                
                for subject, target in standard_hours.items():
                    current = current_hours.get(subject, 0)
                    shortage = target - current
                    
                    # その日にまだない科目を優先
                    if shortage > 0 and subject not in day_subjects:
                        if shortage > max_shortage:
                            max_shortage = shortage
                            best_subject = subject
                
                # 見つからない場合は単に不足している科目
                if not best_subject:
                    for subject, target in standard_hours.items():
                        current = current_hours.get(subject, 0)
                        shortage = target - current
                        
                        if shortage > max_shortage:
                            max_shortage = shortage
                            best_subject = subject
                
                if best_subject:
                    logger.info(f"  {class_name} {get_period_name(j-1)}: 空 → {best_subject}")
                    row[j] = best_subject
                    current_hours[best_subject] += 1
                    fix_count += 1
    
    # 3. 教師重複を修正
    logger.info("\n3. 教師重複を修正...")
    for period_idx in range(30):  # 各時限
        # その時限の教師使用状況を収集
        teacher_usage = defaultdict(list)
        
        for i, row in enumerate(data_rows):
            if not row or not row[0]:
                continue
            
            class_name = row[0]
            csv_idx = period_idx + 1
            
            if csv_idx < len(row) and row[csv_idx]:
                subject = row[csv_idx]
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
                    logger.info(f"  {get_period_name(period_idx)}: {teacher}が重複")
                    # 最初のクラス以外を変更
                    for idx, (i, class_name) in enumerate(classes[1:]):
                        old_subject = data_rows[i][csv_idx]
                        # 代替科目を探す
                        alt_subject = find_alternative_subject(data_rows[i], period_idx, old_subject)
                        if alt_subject:
                            logger.info(f"    {class_name}: {old_subject} → {alt_subject}")
                            data_rows[i][csv_idx] = alt_subject
                            fix_count += 1
    
    logger.info(f"\n合計 {fix_count} 箇所を修正しました。")
    
    # 結果を保存
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(header_rows)
        writer.writerows(data_rows)
    
    logger.info("完了！")
    
    # 違反チェックを実行
    logger.info("\n=== 修正後の違反チェック ===")
    os.system("python3 scripts/analysis/check_violations.py")


def get_period_name(period_idx):
    """期間インデックスから曜日と時限の名前を取得"""
    days = ["月", "火", "水", "木", "金"]
    day_idx = period_idx // 6
    period_num = (period_idx % 6) + 1
    return f"{days[day_idx]}{period_num}限"


def find_alternative_subject(class_row, period_idx, exclude_subject):
    """代替科目を探す"""
    # 主要教科
    main_subjects = ['国', '数', '英', '理', '社']
    skill_subjects = ['音', '美', '保', '技', '家']
    
    # その日の科目を収集
    day_start = (period_idx // 6) * 6 + 1
    day_subjects = set()
    for p in range(day_start, day_start + 6):
        if p < len(class_row) and class_row[p]:
            day_subjects.add(class_row[p])
    
    # まだその日に配置されていない主要教科
    for subject in main_subjects:
        if subject not in day_subjects and subject != exclude_subject:
            return subject
    
    # 技能教科
    for subject in skill_subjects:
        if subject not in day_subjects and subject != exclude_subject:
            return subject
    
    return None


if __name__ == "__main__":
    main()