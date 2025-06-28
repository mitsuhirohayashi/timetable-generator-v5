#!/usr/bin/env python3
"""時間割生成システムの問題診断（簡易版）

現在の出力の問題パターンを分析します。
"""
import os
import sys
import csv
from collections import defaultdict, Counter

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def read_schedule(filename):
    """CSVファイルから時間割を読み込む"""
    filepath = os.path.join(project_root, "data/output", filename)
    schedule = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        time_headers = next(reader)
        
        for row in reader:
            if not row or not row[0]:
                continue
            
            class_name = row[0]
            schedule[class_name] = {}
            
            for i, value in enumerate(row[1:], 1):
                if i < len(time_headers):
                    day = headers[i]
                    period = time_headers[i]
                    time_key = f"{day}{period}"
                    schedule[class_name][time_key] = value
    
    return schedule


def analyze_grade5_sync(schedule):
    """5組の同期状況を分析"""
    print("\n=== 5組同期分析 ===")
    
    grade5_classes = ["1年5組", "2年5組", "3年5組"]
    violations = []
    
    # 各時間枠での同期状況をチェック
    time_slots = []
    for day in ["月", "火", "水", "木", "金"]:
        for period in ["1", "2", "3", "4", "5", "6"]:
            time_slots.append(f"{day}{period}")
    
    for time_slot in time_slots:
        subjects = []
        for class_name in grade5_classes:
            if class_name in schedule and time_slot in schedule[class_name]:
                subjects.append(schedule[class_name][time_slot])
        
        if subjects and len(set(subjects)) > 1:
            violations.append({
                'time': time_slot,
                'subjects': dict(zip(grade5_classes, subjects))
            })
    
    print(f"5組同期違反: {len(violations)}件")
    
    # 違反パターンの分析
    if violations:
        print("\n違反の詳細（最初の10件）:")
        for v in violations[:10]:
            time = v['time']
            day = time[0]
            period = time[1]
            print(f"  {day}曜{period}限: {v['subjects']}")
    
    # 同期可能性の分析
    print("\n同期改善の可能性:")
    subject_match_count = defaultdict(int)
    
    for v in violations:
        subjects = list(v['subjects'].values())
        # 最も多い科目を特定
        counter = Counter(subjects)
        most_common = counter.most_common(1)[0]
        if most_common[1] >= 2:
            subject_match_count[most_common[0]] += 1
    
    for subject, count in sorted(subject_match_count.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {subject}: {count}回（2/3クラスが一致）")
    
    return len(violations)


def analyze_teacher_conflicts(schedule):
    """教師重複を分析（簡易版）"""
    print("\n=== 教師重複分析 ===")
    
    # 教師マッピング（主要なもののみ）
    teacher_mapping = {
        "算": "井上",
        "数": "井上",
        "国": "野口",
        "英": "林田",
        "理": "白石",
        "社": "梶永",
        "音": "智田",
        "美": "北",
        "保": "川嶋",
        "技": "野口",
        "家": "森山",
        "道": "担任",
        "学": "担任",
        "総": "担任",
        "日生": "金子み",
        "自立": "財津/智田",
        "作業": "金子み"
    }
    
    conflicts = []
    
    # 各時間枠での教師配置をチェック
    time_slots = []
    for day in ["月", "火", "水", "木", "金"]:
        for period in ["1", "2", "3", "4", "5", "6"]:
            time_slots.append(f"{day}{period}")
    
    for time_slot in time_slots:
        teacher_classes = defaultdict(list)
        
        for class_name, class_schedule in schedule.items():
            if time_slot in class_schedule:
                subject = class_schedule[time_slot]
                if subject and subject in teacher_mapping:
                    teacher = teacher_mapping[subject]
                    teacher_classes[teacher].append((class_name, subject))
        
        # 重複チェック
        for teacher, assignments in teacher_classes.items():
            if len(assignments) > 1:
                # 5組の合同授業は除外
                grade5_count = sum(1 for c, _ in assignments if "5組" in c)
                if grade5_count < len(assignments):
                    conflicts.append({
                        'time': time_slot,
                        'teacher': teacher,
                        'assignments': assignments
                    })
    
    print(f"教師重複: {len(conflicts)}件")
    
    if conflicts:
        print("\n重複の詳細（最初の10件）:")
        for c in conflicts[:10]:
            time = c['time']
            day = time[0]
            period = time[1]
            classes_str = ", ".join([f"{cls}({subj})" for cls, subj in c['assignments']])
            print(f"  {day}曜{period}限 - {c['teacher']}先生: {classes_str}")
    
    return len(conflicts)


def analyze_daily_duplicates(schedule):
    """日内重複を分析"""
    print("\n=== 日内重複分析 ===")
    
    violations = []
    
    for class_name, class_schedule in schedule.items():
        for day in ["月", "火", "水", "木", "金"]:
            # その日の科目をカウント
            day_subjects = []
            for period in ["1", "2", "3", "4", "5", "6"]:
                time_slot = f"{day}{period}"
                if time_slot in class_schedule:
                    subject = class_schedule[time_slot]
                    if subject and subject not in ["欠", "YT", "学", "総", "道", "学総", "行"]:
                        day_subjects.append(subject)
            
            # 重複チェック
            subject_counts = Counter(day_subjects)
            for subject, count in subject_counts.items():
                if count > 1:
                    violations.append({
                        'class': class_name,
                        'day': day,
                        'subject': subject,
                        'count': count
                    })
    
    print(f"日内重複: {len(violations)}件")
    
    if violations:
        print("\n重複の詳細（最初の10件）:")
        for v in violations[:10]:
            print(f"  {v['class']} {v['day']}曜: {v['subject']}が{v['count']}回")
    
    return len(violations)


def suggest_improvements():
    """改善提案"""
    print("\n=== 改善提案 ===")
    
    print("\n【優先度1: 5組同期の根本的解決】")
    print("現在の問題: 100件以上の5組同期違反")
    print("原因: 5組を個別に配置してから同期を試みている")
    print("解決策:")
    print("  1. 5組専用の配置フェーズを作成")
    print("  2. 3クラス一括で同じ科目・教師を配置")
    print("  3. 金子み先生を5組専任として優先配置")
    
    print("\n【優先度2: 教師重複の解消】")
    print("現在の問題: 18件の教師重複")
    print("原因: 教師の可用性チェックが不完全")
    print("解決策:")
    print("  1. 教師スケジュール管理の強化")
    print("  2. 配置前の完全な可用性チェック")
    print("  3. 学習ルール（井上先生、白石先生）の確実な適用")
    
    print("\n【優先度3: アルゴリズムの改善】")
    print("推奨アプローチ:")
    print("  1. 制約充足問題（CSP）の完全実装")
    print("  2. バックトラッキングの強化")
    print("  3. ヒューリスティックの改善")
    print("     - 最も制約の厳しいスロットから配置")
    print("     - 最も配置の難しい科目を優先")


def main():
    """メイン処理"""
    print("時間割生成システム診断レポート")
    print("="*50)
    
    # 時間割を読み込む
    schedule = read_schedule("output.csv")
    
    # 各種分析を実行
    grade5_violations = analyze_grade5_sync(schedule)
    teacher_conflicts = analyze_teacher_conflicts(schedule)
    daily_duplicates = analyze_daily_duplicates(schedule)
    
    # サマリー
    print("\n=== サマリー ===")
    print(f"総違反数: {grade5_violations + teacher_conflicts + daily_duplicates}件")
    print(f"  - 5組同期違反: {grade5_violations}件")
    print(f"  - 教師重複: {teacher_conflicts}件")
    print(f"  - 日内重複: {daily_duplicates}件")
    
    # 改善提案
    suggest_improvements()
    
    print("\n診断完了")


if __name__ == "__main__":
    main()