#!/usr/bin/env python3
"""
架空の教師を削除し、QA.txtに基づいて実在の教師に置き換えるスクリプト
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Tuple

def load_current_mapping(file_path: str) -> List[List[str]]:
    """現在のマッピングファイルを読み込む"""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        return list(reader)

def get_fictional_teachers() -> List[str]:
    """架空の教師のリストを返す"""
    return ['中村', '佐藤', '山田', '斎藤', '渡辺', '渡部', '田中', '鈴木', '高橋']

def get_real_teacher_mapping() -> Dict[Tuple[str, str, str], str]:
    """QA.txtに基づく正しい教師マッピングを返す"""
    # (教科, 学年, 組) -> 教師名
    mapping = {}
    
    # 音楽 - 全クラス：塚本
    for grade in ['1', '2', '3']:
        for class_num in ['1', '2', '3', '5']:
            mapping[('音', grade, class_num)] = '塚本'
    # 交流学級も追加
    for grade in ['1', '2', '3']:
        for class_num in ['6', '7']:
            mapping[('音', grade, class_num)] = '塚本'
    
    # 家庭 - 全クラス：金子み
    for grade in ['1', '2', '3']:
        for class_num in ['1', '2', '3', '5']:
            mapping[('家', grade, class_num)] = '金子み'
    # 交流学級も追加
    for grade in ['1', '2', '3']:
        for class_num in ['6', '7']:
            mapping[('家', grade, class_num)] = '金子み'
    
    # 美術
    # 1-1, 1-2, 1-3, 2-1, 2-2, 2-3, 3-1, 3-2, 3-3：青井
    for grade, classes in [('1', ['1', '2', '3']), ('2', ['1', '2', '3']), ('3', ['1', '2', '3'])]:
        for class_num in classes:
            mapping[('美', grade, class_num)] = '青井'
    # 1-5, 2-5, 3-5：金子み
    for grade in ['1', '2', '3']:
        mapping[('美', grade, '5')] = '金子み'
    
    # 技家（テスト期間）- 全クラス：林・金子み（両名が担当として登録）
    # 林先生がすでに登録されているので、金子み先生も追加する必要がある
    for grade in ['1', '2', '3']:
        for class_num in ['1', '2', '3', '5', '6', '7']:
            # 技家は林先生がすでに登録されているので、そのまま
            pass
    
    # 国語
    # 1-5, 2-5, 3-5：寺田（※金子みとの選択制だが、寺田を使用）
    for grade in ['1', '2', '3']:
        mapping[('国', grade, '5')] = '寺田'
    
    # 数学
    # 1-5, 2-5, 3-5：梶永
    for grade in ['1', '2', '3']:
        mapping[('数', grade, '5')] = '梶永'
    
    return mapping

def analyze_fictional_assignments(data: List[List[str]], fictional_teachers: List[str]) -> List[Tuple[str, str, str, str]]:
    """架空の教師の割り当てを分析"""
    fictional_assignments = []
    
    for row in data[1:]:  # ヘッダーをスキップ
        if len(row) >= 4 and row[0] in fictional_teachers:
            fictional_assignments.append((row[0], row[1], row[2], row[3]))
    
    return fictional_assignments

def replace_teachers(data: List[List[str]], fictional_teachers: List[str], real_mapping: Dict[Tuple[str, str, str], str]) -> Tuple[List[List[str]], List[str]]:
    """架空の教師を実在の教師に置き換え"""
    new_data = [data[0]]  # ヘッダーを保持
    replacements = []
    removed_rows = []
    
    for row in data[1:]:
        if len(row) >= 4:
            if row[0] in fictional_teachers:
                key = (row[1], row[2], row[3])
                if key in real_mapping:
                    new_row = [real_mapping[key], row[1], row[2], row[3]]
                    new_data.append(new_row)
                    replacements.append(f"{row[0]} -> {real_mapping[key]} ({row[1]}, {row[2]}年{row[3]}組)")
                else:
                    # マッピングが見つからない場合は行を削除
                    removed_rows.append(f"{row[0]} ({row[1]}, {row[2]}年{row[3]}組)")
            else:
                new_data.append(row)
        else:
            new_data.append(row)
    
    return new_data, replacements, removed_rows

def save_backup(file_path: str):
    """バックアップを作成"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.replace('.csv', f'_backup_{timestamp}.csv')
    
    with open(file_path, 'r', encoding='utf-8-sig') as source:
        with open(backup_path, 'w', encoding='utf-8', newline='') as backup:
            backup.write(source.read())
    
    return backup_path

def save_corrected_file(file_path: str, data: List[List[str]]):
    """修正されたファイルを保存"""
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)

def main():
    """メイン処理"""
    file_path = 'data/config/teacher_subject_mapping.csv'
    
    # 現在のマッピングを読み込む
    current_data = load_current_mapping(file_path)
    
    # 架空の教師を取得
    fictional_teachers = get_fictional_teachers()
    
    # 架空の教師の割り当てを分析
    fictional_assignments = analyze_fictional_assignments(current_data, fictional_teachers)
    
    print("=== 架空の教師の割り当て ===")
    for teacher, subject, grade, class_num in fictional_assignments:
        print(f"{teacher}: {subject} ({grade}年{class_num}組)")
    print(f"\n合計: {len(fictional_assignments)}件")
    
    # 実在の教師マッピングを取得
    real_mapping = get_real_teacher_mapping()
    
    # 教師を置き換え
    new_data, replacements, removed_rows = replace_teachers(current_data, fictional_teachers, real_mapping)
    
    print("\n=== 置き換え内容 ===")
    for replacement in replacements:
        print(replacement)
    print(f"\n置き換え数: {len(replacements)}件")
    
    if removed_rows:
        print("\n=== 削除された行 ===")
        for removed in removed_rows:
            print(removed)
        print(f"\n削除数: {len(removed_rows)}件")
    
    # バックアップを作成
    backup_path = save_backup(file_path)
    print(f"\nバックアップを作成しました: {backup_path}")
    
    # 修正されたファイルを保存
    save_corrected_file(file_path, new_data)
    print(f"修正されたファイルを保存しました: {file_path}")
    
    # 結果の要約
    print("\n=== 結果の要約 ===")
    print(f"架空の教師の割り当て: {len(fictional_assignments)}件")
    print(f"置き換え: {len(replacements)}件")
    print(f"削除: {len(removed_rows)}件")
    print(f"元の行数: {len(current_data) - 1}")
    print(f"新しい行数: {len(new_data) - 1}")

if __name__ == "__main__":
    main()