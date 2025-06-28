#!/usr/bin/env python3
"""最後の空きスロットを埋める"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.infrastructure.config.path_config import path_config


def analyze_available_subjects(schedule_data, class_name):
    """クラスの週間時数を分析して追加可能な科目を特定"""
    # 標準時数を読み込む
    base_hours = {}
    try:
        with open('data/config/base_timetable.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                subject = row.get('科目', row.get(''))  # 最初の列が科目名
                if class_name in row:
                    hours = float(row[class_name]) if row[class_name] else 0
                    if hours > 0:
                        base_hours[subject] = hours
    except Exception as e:
        print(f"標準時数ファイルの読み込みエラー: {e}")
        return []
    
    # 現在の時数をカウント
    current_hours = defaultdict(int)
    for slot_data in schedule_data[class_name].values():
        if slot_data and slot_data not in ["", "欠", "YT", "学", "総", "道", "学総", "行"]:
            current_hours[slot_data] += 1
    
    # 追加可能な科目をリストアップ（優先順位付き）
    available_subjects = []
    
    # 主要5教科を優先
    priority_subjects = ["国", "数", "英", "理", "社"]
    for subject in priority_subjects:
        if subject in base_hours:
            diff = base_hours[subject] - current_hours[subject]
            if diff > 0:  # まだ追加可能
                available_subjects.append((subject, diff))
    
    # その他の教科
    for subject, standard in base_hours.items():
        if subject not in priority_subjects:
            diff = standard - current_hours[subject]
            if diff > 0:
                available_subjects.append((subject, diff))
    
    # 差分が大きい順にソート
    available_subjects.sort(key=lambda x: x[1], reverse=True)
    
    return [subj[0] for subj in available_subjects]


def get_teacher_for_subject(class_name, subject):
    """指定されたクラスと科目の教師を取得"""
    teacher_mapping = {}
    try:
        with open('data/config/teacher_subject_mapping.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                grade = row['学年']
                class_num = row['組']
                key_class = f"{grade}年{class_num}組"
                if key_class == class_name and row['教科'] == subject:
                    return row['教員名']
    except Exception as e:
        print(f"教師マッピングファイルの読み込みエラー: {e}")
    
    return None


def check_teacher_availability(schedule_data, teacher, day, period):
    """教師が指定された時間に空いているかチェック"""
    if not teacher:
        return False
    
    # 全クラスをチェック
    for cls, slots in schedule_data.items():
        slot_key = (day, period)
        if slot_key in slots and slots[slot_key]:
            # この時間のこのクラスの教師を確認
            subject = slots[slot_key]
            assigned_teacher = get_teacher_for_subject(cls, subject)
            if assigned_teacher == teacher:
                return False  # 既に授業がある
    
    return True


def fill_empty_slots():
    """空きスロットを埋める"""
    print("=== 最後の空きスロットを埋める ===\n")
    
    # output.csvを読み込む
    output_path = path_config.output_dir / "output.csv"
    print(f"Reading schedule from: {output_path}")
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # スケジュールデータを辞書形式に変換
    schedule_data = {}
    days = ["月", "火", "水", "木", "金"]
    
    for idx, row in enumerate(data):
        if idx < 2:  # ヘッダー行をスキップ
            continue
        
        class_name = row[0] if row else ""
        if not class_name or class_name.strip() == '':
            continue
        
        schedule_data[class_name] = {}
        col_idx = 1
        
        for day in days:
            for period in range(1, 7):
                if col_idx < len(row):
                    subject = row[col_idx].strip() if row[col_idx] else ""
                    schedule_data[class_name][(day, period)] = subject
                col_idx += 1
    
    # 空きスロットを特定して埋める
    filled_count = 0
    empty_slots = [
        ("1年6組", "火", 6),
        ("2年1組", "金", 6)
    ]
    
    for class_name, day, period in empty_slots:
        print(f"\n処理中: {class_name} {day}曜{period}限")
        
        # 利用可能な科目を取得
        available_subjects = analyze_available_subjects(schedule_data, class_name)
        print(f"  追加可能な科目: {available_subjects}")
        
        # 各科目について教師の空き状況をチェック
        assigned = False
        for subject in available_subjects:
            teacher = get_teacher_for_subject(class_name, subject)
            if teacher and check_teacher_availability(schedule_data, teacher, day, period):
                print(f"  → {subject}（{teacher}先生）を配置")
                
                # データを更新
                for idx, row in enumerate(data):
                    if idx >= 2 and row[0] == class_name:
                        col_idx = 1 + (["月", "火", "水", "木", "金"].index(day) * 6) + (period - 1)
                        data[idx][col_idx] = subject
                        schedule_data[class_name][(day, period)] = subject
                        filled_count += 1
                        assigned = True
                        break
                
                if assigned:
                    break
        
        if not assigned:
            print(f"  → 配置可能な科目が見つかりませんでした")
    
    # 修正後のデータを保存
    if filled_count > 0:
        # バックアップを作成
        backup_path = output_path.with_suffix('.csv.bak_fill_final')
        with open(backup_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nBackup saved to: {backup_path}")
        
        # 修正版を保存
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"\nFilled {filled_count} empty slots")
        print(f"Updated schedule saved to: {output_path}")
    else:
        print("\nNo slots could be filled")
    
    return filled_count


if __name__ == "__main__":
    filled_count = fill_empty_slots()
    print(f"\nTotal slots filled: {filled_count}")