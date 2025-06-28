"""V2戦略の違反を分析"""
import csv
from collections import defaultdict

def analyze_violations():
    """違反の詳細分析"""
    
    # スケジュールを読み込み
    schedule = {}
    teacher_assignments = defaultdict(list)  # 教師 -> [(day, period, class)]
    daily_subjects = defaultdict(list)  # (class, day) -> [subjects]
    gym_usage = defaultdict(list)  # (day, period) -> [classes]
    
    # 交流学級と親学級のマッピング
    exchange_parent_map = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    with open('/Users/hayashimitsuhiro/Desktop/timetable_v5/data/output/output.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)  # ヘッダー行
        days_row = next(reader)  # 曜日行
        
        class_schedules = []
        for row in reader:
            if len(row) > 2 and row[0]:
                class_schedules.append(row)
        
        # スケジュールを解析
        days = ["月", "火", "水", "木", "金"]
        for class_idx, class_row in enumerate(class_schedules):
            class_name = class_row[0]
            
            for col_idx in range(1, 31):  # 1-30列が授業
                subject = class_row[col_idx] if col_idx < len(class_row) else ""
                if not subject:
                    continue
                    
                # 曜日と時限を計算
                day_idx = (col_idx - 1) // 6
                period = ((col_idx - 1) % 6) + 1
                day = days[day_idx]
                
                # 教師を推定（簡易版）
                teacher = get_teacher_for_subject(subject, class_name)
                if teacher:
                    teacher_assignments[teacher].append((day, period, class_name))
                
                # 日内科目を記録
                daily_subjects[(class_name, day)].append(subject)
                
                # 体育館使用を記録
                if subject == "保":
                    gym_usage[(day, period)].append(class_name)
    
    # 教師重複を分析
    print("\n=== 教師重複の詳細 ===")
    teacher_conflicts = 0
    grade5_joint_count = 0
    exchange_pair_count = 0
    
    for teacher, assignments in teacher_assignments.items():
        # 同じ時間の割り当てを探す
        time_slots = defaultdict(list)
        for day, period, class_name in assignments:
            time_slots[(day, period)].append(class_name)
        
        for (day, period), classes in time_slots.items():
            if len(classes) > 1:
                # 5組合同授業をチェック
                grade5_classes = [c for c in classes if "5組" in c]
                if len(grade5_classes) >= 2:  # 5組が2つ以上含まれている場合
                    # 5組のみの場合は合同授業として正常
                    non_grade5 = [c for c in classes if "5組" not in c]
                    if len(non_grade5) == 0:
                        grade5_joint_count += 1
                        continue  # 5組だけなら違反ではない
                
                # 交流学級ペアをチェック
                if len(classes) == 2:
                    class1, class2 = classes[0], classes[1]
                    # 親学級と交流学級のペアか確認
                    if ((class1 in exchange_parent_map and exchange_parent_map[class1] == class2) or
                        (class2 in exchange_parent_map and exchange_parent_map[class2] == class1)):
                        exchange_pair_count += 1
                        continue  # 交流学級ペアは違反ではない
                    
                teacher_conflicts += 1
                print(f"  {teacher}: {day}曜{period}限 - {', '.join(classes)}")
    
    print(f"\n合計: {teacher_conflicts}件の教師重複")
    print(f"（5組合同授業として除外: {grade5_joint_count}件）")
    print(f"（交流学級ペアとして除外: {exchange_pair_count}件）")
    
    # 日内重複を分析
    print("\n=== 日内重複の詳細 ===")
    daily_duplicates = 0
    for (class_name, day), subjects in daily_subjects.items():
        subject_counts = defaultdict(int)
        for subject in subjects:
            subject_counts[subject] += 1
        
        for subject, count in subject_counts.items():
            if count > 1:
                daily_duplicates += 1
                print(f"  {class_name} {day}曜日: {subject}が{count}回")
    
    print(f"\n合計: {daily_duplicates}件の日内重複")
    
    # 体育館使用を分析
    print("\n=== 体育館使用の詳細 ===")
    gym_violations = 0
    for (day, period), classes in gym_usage.items():
        if len(classes) > 1:
            # 交流学級ペアをチェック
            exchange_pairs = [
                ("1年1組", "1年6組"), ("1年2組", "1年7組"),
                ("2年3組", "2年6組"), ("2年2組", "2年7組"),
                ("3年3組", "3年6組"), ("3年2組", "3年7組")
            ]
            
            is_valid = False
            if len(classes) == 2:
                for parent, exchange in exchange_pairs:
                    if (parent in classes and exchange in classes):
                        is_valid = True
                        break
            
            # 5組合同
            grade5_count = sum(1 for c in classes if "5組" in c)
            if grade5_count == 3 and len(classes) == 3:
                is_valid = True
            
            if not is_valid:
                gym_violations += 1
                print(f"  {day}曜{period}限: {', '.join(classes)}")
    
    print(f"\n合計: {gym_violations}件の体育館使用違反")

def get_teacher_for_subject(subject, class_name):
    """科目とクラスから教師を推定（簡易版）"""
    # 5組の特別処理
    if "5組" in class_name:
        grade5_map = {
            "国": "金子み",  # or 寺田（選択制）
            "数": "梶永",
            "英": "林田",
            "理": "智田",
            "社": "蒲地",
            "音": "塚本",
            "美": "金子み",
            "技": "林",
            "家": "金子み",
            "保": "財津",
            "日生": "金子み",
            "作業": "金子み",
            "生単": "金子み",
            "自立": "金子み",
        }
        return grade5_map.get(subject)
    
    # 主要教科のマッピング
    teacher_map = {
        ("国", "1"): "寺田",
        ("国", "2"): "小野塚",
        ("国", "3"): "小野塚",
        ("数", "1"): "梶永",
        ("数", "2"): "井上",
        ("数", "3"): "森山",
        ("英", "1"): "井野口",
        ("英", "2"): "箱崎",
        ("英", "3"): "林田",
        ("理", "1"): "金子ひ",
        ("理", "2"): "智田",
        ("理", "3"): "白石",
        ("社", "1"): "蒲地",
        ("社", "2"): "蒲地",
        ("社", "3"): "北",
        ("音", ""): "塚本",
        ("美", ""): "青井",
        ("技", ""): "林",
        ("家", ""): "金子み",
        ("保", "1"): "永山",
        ("保", "2"): "野口",
        ("保", "3"): "財津",
    }
    
    # 学年を抽出
    grade = class_name[0] if class_name else ""
    
    # 教師を検索
    if (subject, grade) in teacher_map:
        return teacher_map[(subject, grade)]
    elif (subject, "") in teacher_map:
        return teacher_map[(subject, "")]
    
    return None

if __name__ == "__main__":
    analyze_violations()