#!/usr/bin/env python3
"""違反の簡易分析スクリプト"""

import pandas as pd
import csv

def load_timetable():
    """時間割データを読み込む"""
    timetable = {}
    with open('data/output/output.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行
        time_slots = next(reader)  # 時限行
        
        for row in reader:
            if not row or not row[0]:  # 空行スキップ
                continue
            class_name = row[0]
            timetable[class_name] = {}
            
            for i in range(1, len(row)):
                if i < len(headers) and i < len(time_slots):
                    day = headers[i]
                    period = time_slots[i]
                    subject = row[i] if i < len(row) else ""
                    
                    if day not in timetable[class_name]:
                        timetable[class_name][day] = {}
                    timetable[class_name][day][period] = subject
    
    return timetable

def analyze_teacher_conflicts():
    """教師重複の詳細分析"""
    print("\n=== 教師重複の詳細分析 ===")
    
    # 教師マッピングを読み込む
    teacher_mapping = {}
    try:
        df = pd.read_csv('data/config/teacher_subject_mapping.csv')
        for _, row in df.iterrows():
            key = f"{row['学年']}年{row['組']}組_{row['教科']}"
            teacher_mapping[key] = row['教員名']
    except Exception as e:
        print(f"教師マッピングファイルの読み込みエラー: {e}")
        return
    
    # 時間割を読み込む
    timetable = load_timetable()
    
    # テスト期間
    test_periods = [
        ("月", "1"), ("月", "2"), ("月", "3"),
        ("火", "1"), ("火", "2"), ("火", "3"),
        ("水", "1"), ("水", "2")
    ]
    
    # 時間ごとの教師配置を確認
    conflicts = []
    for day in ["月", "火", "水", "木", "金"]:
        for period in ["1", "2", "3", "4", "5", "6"]:
            teacher_assignments = {}
            
            for class_name, class_schedule in timetable.items():
                if day in class_schedule and period in class_schedule[day]:
                    subject = class_schedule[day][period]
                    if subject and subject not in ["", "欠", "YT"]:
                        # 教師を特定
                        # クラス名から学年と組を抽出
                        if "年" in class_name and "組" in class_name:
                            key = f"{class_name}_{subject}"
                            teacher = teacher_mapping.get(key, f"{subject}担当")
                            
                            if teacher not in teacher_assignments:
                                teacher_assignments[teacher] = []
                            teacher_assignments[teacher].append(class_name)
            
            # 重複をチェック
            for teacher, classes in teacher_assignments.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    if set(classes) == {"1年5組", "2年5組", "3年5組"}:
                        continue
                    
                    # テスト期間の巡回監督は除外
                    is_test_period = (day, period) in test_periods
                    if is_test_period:
                        # 同じ学年のテストかチェック
                        grades = set()
                        subjects = set()
                        for cls in classes:
                            if "年" in cls:
                                grade = int(cls[0])
                                grades.add(grade)
                            if day in timetable[cls] and period in timetable[cls][day]:
                                subjects.add(timetable[cls][day][period])
                        
                        # 同じ学年で同じ科目なら巡回監督として正常
                        if len(grades) == 1 and len(subjects) == 1:
                            print(f"  {day}曜{period}限: {teacher}先生 - テスト巡回監督 ({', '.join(classes)})")
                            continue
                    
                    # 交流学級と親学級の体育は除外
                    exchange_pairs = [
                        ("1年1組", "1年6組"), ("1年2組", "1年7組"),
                        ("2年3組", "2年6組"), ("2年2組", "2年7組"),
                        ("3年3組", "3年6組"), ("3年2組", "3年7組")
                    ]
                    is_exchange_pair = False
                    for parent, exchange in exchange_pairs:
                        if set(classes) == {parent, exchange}:
                            # 両方とも体育かチェック
                            parent_subj = timetable[parent][day][period] if parent in timetable and day in timetable[parent] and period in timetable[parent][day] else ""
                            exchange_subj = timetable[exchange][day][period] if exchange in timetable and day in timetable[exchange] and period in timetable[exchange][day] else ""
                            if parent_subj == "保" and exchange_subj == "保":
                                is_exchange_pair = True
                                print(f"  {day}曜{period}限: {teacher}先生 - 交流学級ペアの体育 ({parent}, {exchange})")
                                break
                    
                    if not is_exchange_pair:
                        conflicts.append({
                            'day': day,
                            'period': period,
                            'teacher': teacher,
                            'classes': classes,
                            'is_test': is_test_period
                        })
    
    # 結果を表示
    print(f"\n真の教師重複: {len(conflicts)}件")
    for conflict in conflicts:
        test_note = " (テスト期間)" if conflict['is_test'] else ""
        print(f"  {conflict['day']}曜{conflict['period']}限: {conflict['teacher']}先生 - {', '.join(conflict['classes'])}{test_note}")

def analyze_other_violations():
    """その他の違反の詳細分析"""
    print("\n\n=== その他の違反の詳細分析 ===")
    
    timetable = load_timetable()
    
    # 月曜6限の固定違反
    print("\n【月曜6限固定違反】")
    monday_6_violations = []
    for class_name, class_schedule in timetable.items():
        if "年" in class_name and "組" in class_name:
            grade = int(class_name[0])
            if grade in [1, 2]:  # 1・2年生のみ
                if "月" in class_schedule and "6" in class_schedule["月"]:
                    subject = class_schedule["月"]["6"]
                    if subject and subject != "欠":
                        monday_6_violations.append({
                            'class': class_name,
                            'subject': subject
                        })
    
    print(f"月曜6限違反: {len(monday_6_violations)}件")
    for v in monday_6_violations:
        print(f"  {v['class']}: {v['subject']} (欠であるべき)")
    
    # 空きコマの確認
    print("\n【空きコマ】")
    empty_slots = []
    for class_name, class_schedule in timetable.items():
        for day in ["月", "火", "水", "木", "金"]:
            for period in ["1", "2", "3", "4", "5", "6"]:
                if day in class_schedule and period in class_schedule[day]:
                    subject = class_schedule[day][period]
                    if not subject or subject == "":
                        empty_slots.append({
                            'class': class_name,
                            'day': day,
                            'period': period
                        })
    
    print(f"空きコマ総数: {len(empty_slots)}個")
    for slot in empty_slots:
        print(f"  {slot['class']}: {slot['day']}曜{slot['period']}限")

def analyze_jiritsu_violations():
    """自立活動違反の詳細分析"""
    print("\n\n=== 自立活動違反の詳細分析 ===")
    
    timetable = load_timetable()
    
    exchange_mapping = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    violations = []
    for exchange_class, parent_class in exchange_mapping.items():
        if exchange_class in timetable and parent_class in timetable:
            for day in ["月", "火", "水", "木", "金"]:
                for period in ["1", "2", "3", "4", "5", "6"]:
                    if day in timetable[exchange_class] and period in timetable[exchange_class][day]:
                        exchange_subject = timetable[exchange_class][day][period]
                        
                        if exchange_subject == "自立":
                            if day in timetable[parent_class] and period in timetable[parent_class][day]:
                                parent_subject = timetable[parent_class][day][period]
                                if parent_subject not in ["数", "英"]:
                                    violations.append({
                                        'day': day,
                                        'period': period,
                                        'exchange': exchange_class,
                                        'parent': parent_class,
                                        'parent_subject': parent_subject
                                    })
    
    print(f"自立活動違反: {len(violations)}件")
    for v in violations:
        print(f"  {v['day']}曜{v['period']}限: {v['exchange']}が自立活動、{v['parent']}が{v['parent_subject']} (数学か英語であるべき)")

def main():
    analyze_teacher_conflicts()
    analyze_other_violations()
    analyze_jiritsu_violations()

if __name__ == "__main__":
    main()