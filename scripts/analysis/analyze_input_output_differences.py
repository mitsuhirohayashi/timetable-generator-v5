#!/usr/bin/env python3
"""入力と出力の差分を詳細分析し、勝手に変更された箇所を特定"""

import csv
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.domain.value_objects.time_slot import TimeSlot


def read_csv_data(filepath):
    """CSVファイルを読み込んで辞書形式で返す"""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        data = list(reader)
    
    # データを辞書形式に変換
    schedule = {}
    days = ["月", "火", "水", "木", "金"]
    
    for idx, row in enumerate(data):
        if idx < 2:  # ヘッダー行をスキップ
            continue
        
        class_name = row[0] if row else ""
        if not class_name or class_name.strip() == '':
            continue
        
        schedule[class_name] = {}
        col_idx = 1
        
        for day in days:
            for period in range(1, 7):
                if col_idx < len(row):
                    subject = row[col_idx].strip() if row[col_idx] else ""
                    schedule[class_name][(day, period)] = subject
                col_idx += 1
    
    return schedule


def analyze_fixed_subject_changes(input_data, output_data):
    """固定科目の不正な変更を検出"""
    fixed_subjects = {"欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家"}
    violations = []
    
    for class_name in input_data:
        if class_name not in output_data:
            continue
        
        for time_slot in input_data[class_name]:
            input_subject = input_data[class_name][time_slot]
            output_subject = output_data[class_name].get(time_slot, "")
            
            # 固定科目が変更されているかチェック
            if input_subject in fixed_subjects and input_subject != output_subject:
                violations.append({
                    'class': class_name,
                    'day': time_slot[0],
                    'period': time_slot[1],
                    'input': input_subject,
                    'output': output_subject,
                    'type': 'fixed_subject_changed'
                })
    
    return violations


def analyze_empty_slots(input_data, output_data):
    """空きスロットの分析"""
    empty_slots = []
    
    for class_name in output_data:
        for time_slot in output_data[class_name]:
            output_subject = output_data[class_name][time_slot]
            
            # 出力が空きの場合
            if not output_subject or output_subject == "":
                input_subject = input_data.get(class_name, {}).get(time_slot, "")
                empty_slots.append({
                    'class': class_name,
                    'day': time_slot[0],
                    'period': time_slot[1],
                    'input': input_subject,
                    'output': '(空き)'
                })
    
    return empty_slots


def analyze_teacher_conflicts():
    """教師重複の詳細分析（正常なパターンを除外）"""
    # teacher_subject_mapping.csvから教師情報を読み込む
    teacher_mapping = {}
    try:
        with open('data/config/teacher_subject_mapping.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = f"{row['学年']}年{row['組']}組_{row['教科']}"
                teacher_mapping[key] = row['教員名']
    except Exception as e:
        print(f"教師マッピングファイルの読み込みエラー: {e}")
        return []
    
    # output.csvから時間割を読み込む
    output_data = read_csv_data('data/output/output.csv')
    
    # Follow-up.csvからテスト期間を抽出
    test_periods = []
    try:
        with open('data/input/Follow-up.csv', 'r', encoding='utf-8-sig') as f:
            content = f.read()
            # テスト期間の記載を探す
            if "テストなので時間割の変更をしないでください" in content:
                # 簡易的にテスト期間を設定（実際のパースは省略）
                test_periods = [("月", 1), ("月", 2), ("月", 3), 
                               ("火", 1), ("火", 2), ("火", 3),
                               ("水", 1), ("水", 2)]
    except:
        pass
    
    conflicts = []
    days = ["月", "火", "水", "木", "金"]
    
    for day in days:
        for period in range(1, 7):
            teacher_assignments = {}
            
            # 各クラスの教師を収集
            for class_name, schedule in output_data.items():
                subject = schedule.get((day, period), "")
                if subject and subject not in ["", "欠", "YT", "学", "総", "道", "学総", "行"]:
                    # 教師を特定
                    grade = int(class_name[0]) if class_name[0].isdigit() else 0
                    class_num = class_name.split('年')[1].split('組')[0] if '年' in class_name and '組' in class_name else ""
                    key = f"{grade}年{class_num}組_{subject}"
                    teacher = teacher_mapping.get(key, f"{subject}担当")
                    
                    if teacher not in teacher_assignments:
                        teacher_assignments[teacher] = []
                    teacher_assignments[teacher].append(class_name)
            
            # 重複をチェック（正常パターンを除外）
            for teacher, classes in teacher_assignments.items():
                if len(classes) > 1:
                    # 5組の合同授業は正常
                    if set(classes) == {"1年5組", "2年5組", "3年5組"}:
                        continue
                    
                    # テスト期間の巡回監督は正常
                    if (day, period) in test_periods:
                        # 同一学年のテストかチェック
                        grades = set(int(cls[0]) for cls in classes if cls[0].isdigit())
                        if len(grades) == 1:
                            continue
                    
                    # 交流学級と親学級の体育は正常
                    exchange_pairs = [
                        ("1年1組", "1年6組"), ("1年2組", "1年7組"),
                        ("2年3組", "2年6組"), ("2年2組", "2年7組"),
                        ("3年3組", "3年6組"), ("3年2組", "3年7組")
                    ]
                    is_normal_pair = False
                    for parent, exchange in exchange_pairs:
                        if set(classes) == {parent, exchange}:
                            # 両方とも体育かチェック
                            parent_subj = output_data[parent].get((day, period), "")
                            exchange_subj = output_data[exchange].get((day, period), "")
                            if parent_subj == "保" and exchange_subj == "保":
                                is_normal_pair = True
                                break
                    
                    if not is_normal_pair:
                        conflicts.append({
                            'day': day,
                            'period': period,
                            'teacher': teacher,
                            'classes': classes
                        })
    
    return conflicts


def main():
    print("=== 入力と出力の差分分析 ===\n")
    
    # データ読み込み
    input_data = read_csv_data('data/input/input.csv')
    output_data = read_csv_data('data/output/output.csv')
    
    # 1. 固定科目の不正な変更をチェック
    print("【1. 固定科目の不正な変更】")
    fixed_violations = analyze_fixed_subject_changes(input_data, output_data)
    
    if fixed_violations:
        print(f"⚠️  固定科目が不正に変更された箇所: {len(fixed_violations)}件")
        for v in fixed_violations:
            print(f"  {v['class']} {v['day']}曜{v['period']}限: {v['input']} → {v['output']} (変更禁止)")
    else:
        print("✅ 固定科目の不正な変更はありません")
    
    # 2. 空きスロットのチェック
    print("\n【2. 空きスロット】")
    empty_slots = analyze_empty_slots(input_data, output_data)
    
    if empty_slots:
        print(f"⚠️  空きスロット: {len(empty_slots)}個")
        # クラスごとにグループ化
        by_class = {}
        for slot in empty_slots:
            if slot['class'] not in by_class:
                by_class[slot['class']] = []
            by_class[slot['class']].append(f"{slot['day']}{slot['period']}")
        
        for class_name, slots in by_class.items():
            print(f"  {class_name}: {', '.join(slots)}")
    else:
        print("✅ 空きスロットはありません")
    
    # 3. 真の教師重複（正常パターンを除外）
    print("\n【3. 真の教師重複】")
    conflicts = analyze_teacher_conflicts()
    
    if conflicts:
        print(f"⚠️  真の教師重複: {len(conflicts)}件")
        for c in conflicts:
            print(f"  {c['day']}曜{c['period']}限: {c['teacher']}先生 - {', '.join(c['classes'])}")
    else:
        print("✅ 教師重複はありません（正常なパターンを除く）")
    
    # 4. 月曜6限の特別チェック
    print("\n【4. 月曜6限の状況】")
    monday_6_status = []
    
    for class_name in sorted(input_data.keys()):
        input_subj = input_data[class_name].get(("月", 6), "")
        output_subj = output_data.get(class_name, {}).get(("月", 6), "")
        
        if input_subj or output_subj:
            status = "✅" if input_subj == output_subj else "❌"
            monday_6_status.append({
                'class': class_name,
                'input': input_subj or "(空き)",
                'output': output_subj or "(空き)",
                'status': status
            })
    
    print("月曜6限の入力と出力の比較:")
    for s in monday_6_status:
        print(f"  {s['status']} {s['class']}: 入力={s['input']}, 出力={s['output']}")
    
    # 5. サマリー
    print("\n【サマリー】")
    print(f"- 固定科目の不正変更: {len(fixed_violations)}件")
    print(f"- 空きスロット: {len(empty_slots)}個")
    print(f"- 真の教師重複: {len(conflicts)}件")
    
    if fixed_violations:
        print("\n⚠️  重要: 固定科目（YT、欠、学、総合など）が勝手に変更されています。")
        print("これは基本ルール違反です。システムの修正が必要です。")


if __name__ == "__main__":
    main()