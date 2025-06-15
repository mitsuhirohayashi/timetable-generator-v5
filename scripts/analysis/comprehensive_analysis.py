import csv
from collections import defaultdict, Counter

def comprehensive_analysis():
    """時間割の包括的な問題分析"""
    
    # ファイルパス
    timetable_path = "/Users/hayashimitsuhiro/Desktop/timetable_v5/data/output/output.csv"
    actual_mapping_path = "/Users/hayashimitsuhiro/Desktop/timetable_v5/data/config/actual_teacher_mapping.csv"
    
    # 時間割読み込み
    timetable = []
    with open(timetable_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0]:
                timetable.append(row)
    
    # 実際の教師マッピング読み込み
    teacher_mapping = {}  # 科目 -> 教師のマッピング
    teacher_constraints = defaultdict(list)  # 教師 -> 制約リスト
    
    with open(actual_mapping_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            teacher = row['実際の教員名']
            subject = row['担当教科']
            grade = row['担当学年']
            class_num = row['担当クラス']
            constraint = row['備考']
            
            key = f"{grade}年{class_num}組_{subject}"
            teacher_mapping[key] = teacher
            
            if constraint:
                teacher_constraints[teacher].append(constraint)
    
    # クラス行のインデックス取得
    class_rows = {}
    for i, row in enumerate(timetable):
        if i >= 2 and row[0] and row[0] not in ['', '基本時間割']:
            class_rows[row[0]] = i
    
    print("=== 時間割の包括的分析結果 ===\n")
    
    # 1. 空きコマの分析
    print("1. 空きコマの詳細分析:")
    empty_slots = []
    for class_name, row_idx in sorted(class_rows.items()):
        row = timetable[row_idx]
        class_empty = []
        for col_idx in range(1, 31):
            if col_idx == 6:  # 月6は欠席
                continue
            if col_idx in [12, 18, 30]:  # 火6、水6、金6はYT
                continue
            
            subject = row[col_idx].strip() if col_idx < len(row) else ''
            if not subject:
                day_idx = (col_idx - 1) // 6
                period = (col_idx - 1) % 6 + 1
                days = ['月', '火', '水', '木', '金']
                class_empty.append(f"{days[day_idx]}{period}")
        
        if class_empty:
            print(f"  {class_name}: {', '.join(class_empty)}")
            empty_slots.extend([(class_name, slot) for slot in class_empty])
    
    # 2. 教師の制約違反チェック
    print("\n2. 教師の制約違反（赤いセル）:")
    
    # 各時間の教師割り当てを収集
    time_teacher_assignments = defaultdict(lambda: defaultdict(list))
    
    for class_name, row_idx in class_rows.items():
        row = timetable[row_idx]
        # クラス名から学年と組を抽出
        grade = class_name[0]
        class_num = class_name[2]
        
        for col_idx in range(1, 31):
            if col_idx < len(row) and row[col_idx]:
                subject = row[col_idx].strip()
                if subject and subject not in ['欠', 'YT', '']:
                    key = f"{grade}年{class_num}組_{subject}"
                    teacher = teacher_mapping.get(key, subject)
                    time_teacher_assignments[col_idx][teacher].append(class_name)
    
    # 制約違反のチェック
    violations = defaultdict(list)
    
    # 月曜日の制約違反（小野塚、北、井野口）
    monday_absent_teachers = ['小野塚', '北', '井野口']
    for period in range(1, 7):  # 月1-6
        for teacher in time_teacher_assignments[period]:
            if teacher in monday_absent_teachers:
                violations['月曜日不在違反'].append(f"月{period}: {teacher}先生 ({', '.join(time_teacher_assignments[period][teacher])})")
    
    # 火曜日の制約違反（金子ひ）
    for period in range(7, 13):  # 火1-6
        if '金子ひ' in time_teacher_assignments[period]:
            violations['火曜日不在違反'].append(f"火{period-6}: 金子ひ先生 ({', '.join(time_teacher_assignments[period]['金子ひ'])})")
    
    # 水曜午後の制約違反（永山）
    for period in range(15, 19):  # 水3-6
        if '永山' in time_teacher_assignments[period]:
            violations['水曜午後不在違反'].append(f"水{period-12}: 永山先生 ({', '.join(time_teacher_assignments[period]['永山'])})")
    
    # 金曜日の制約違反
    friday_all_day_absent = ['梶永']  # 金曜終日不在
    friday_pm_absent = ['井野口', '塚本', '野口', '財津']  # 金曜午後不在
    
    for period in range(25, 31):  # 金1-6
        day_period = period - 24
        for teacher in time_teacher_assignments[period]:
            if teacher in friday_all_day_absent:
                violations['金曜終日不在違反'].append(f"金{day_period}: {teacher}先生 ({', '.join(time_teacher_assignments[period][teacher])})")
            elif teacher in friday_pm_absent and day_period >= 3:
                violations['金曜午後不在違反'].append(f"金{day_period}: {teacher}先生 ({', '.join(time_teacher_assignments[period][teacher])})")
    
    # 制約違反の出力
    for violation_type, violation_list in violations.items():
        if violation_list:
            print(f"\n  {violation_type}:")
            for v in violation_list:
                print(f"    - {v}")
    
    # 3. 同時間帯の教師重複
    print("\n3. 同時間帯の教師重複（物理的に不可能）:")
    for col_idx in range(1, 31):
        conflicts = []
        for teacher, classes in time_teacher_assignments[col_idx].items():
            if len(classes) > 1:
                conflicts.append(f"{teacher}先生: {', '.join(classes)}")
        
        if conflicts:
            day_idx = (col_idx - 1) // 6
            period = (col_idx - 1) % 6 + 1
            days = ['月', '火', '水', '木', '金']
            print(f"  {days[day_idx]}{period}:")
            for c in conflicts:
                print(f"    - {c}")
    
    # 4. 非担当教員の授業割り当て
    print("\n4. 非担当教員の問題（校長、児玉、吉村）:")
    non_teaching_staff = ['校長', '児玉', '吉村']
    for class_name, row_idx in class_rows.items():
        row = timetable[row_idx]
        for col_idx in range(1, 31):
            if col_idx < len(row) and row[col_idx]:
                subject = row[col_idx].strip()
                if subject in non_teaching_staff:
                    day_idx = (col_idx - 1) // 6
                    period = (col_idx - 1) % 6 + 1
                    days = ['月', '火', '水', '木', '金']
                    print(f"  {class_name} {days[day_idx]}{period}: {subject}")
    
    # 5. 各教師の週間授業数
    print("\n5. 教師別週間授業数（問題のある教師）:")
    teacher_weekly_count = Counter()
    for col_idx in range(1, 31):
        for teacher, classes in time_teacher_assignments[col_idx].items():
            teacher_weekly_count[teacher] += len(classes)
    
    # 授業数が異常な教師（30コマ以上または5コマ以下）
    for teacher, count in sorted(teacher_weekly_count.items(), key=lambda x: x[1], reverse=True):
        if count >= 30 or count <= 5:
            constraints = teacher_constraints.get(teacher, [])
            constraint_str = f" ({', '.join(constraints)})" if constraints else ""
            print(f"  {teacher}: {count}コマ{constraint_str}")
    
    # 6. 改善提案
    print("\n6. システムの改善提案:")
    print("  1) 教師の不在制約の厳格な適用:")
    print("     - 月曜日: 小野塚、北、井野口の完全除外")
    print("     - 火曜日: 金子ひの完全除外")
    print("     - 水曜午後: 永山の除外")
    print("     - 金曜日: 梶永の完全除外、井野口・塚本・野口・財津の午後除外")
    print("\n  2) 制約チェックの強化:")
    print("     - 事前検証: 割り当て前に制約違反をチェック")
    print("     - リアルタイム検証: 各割り当て時に即座に違反を検出")
    print("     - 最終検証: 生成完了後の包括的チェック")
    print("\n  3) 空きコマの自動補完:")
    print("     - 各クラスの不足科目を自動検出")
    print("     - 利用可能な教師から適切に割り当て")
    print("     - 制約を考慮した上での最適化")
    print("\n  4) UI/UXの改善:")
    print("     - 制約違反のリアルタイム表示")
    print("     - 教師の負荷バランス可視化")
    print("     - 修正候補の自動提案")

if __name__ == "__main__":
    comprehensive_analysis()