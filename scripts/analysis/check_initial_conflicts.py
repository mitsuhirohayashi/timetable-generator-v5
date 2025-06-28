"""初期スケジュールの教師重複をチェック"""
import csv
from collections import defaultdict

def check_initial_conflicts():
    """input.csvの教師重複をチェック"""
    
    teacher_assignments = defaultdict(list)  # 教師 -> [(day, period, class)]
    
    # 交流学級と親学級のマッピング
    exchange_parent_map = {
        "1年6組": "1年1組",
        "1年7組": "1年2組",
        "2年6組": "2年3組",
        "2年7組": "2年2組",
        "3年6組": "3年3組",
        "3年7組": "3年2組"
    }
    
    with open('/Users/hayashimitsuhiro/Desktop/timetable_v5/data/input/input.csv', 'r', encoding='utf-8-sig') as f:
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
                if not subject or subject in ["YT", "欠", "道", "学", "総", "学総", "行", "テスト", "技家"]:
                    continue
                    
                # 曜日と時限を計算
                day_idx = (col_idx - 1) // 6
                period = ((col_idx - 1) % 6) + 1
                day = days[day_idx]
                
                # 教師を推定
                teacher = get_teacher_for_subject(subject, class_name)
                if teacher:
                    teacher_assignments[teacher].append((day, period, class_name))
    
    # 教師重複を分析
    print("=== input.csv（初期スケジュール）の教師重複 ===")
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
    
    return teacher_conflicts

def get_teacher_for_subject(subject, class_name):
    """科目とクラスから教師を推定"""
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
    
    teacher_map = {
        ("国", "1"): "寺田",
        ("国", "2-1"): "寺田", 
        ("国", "2-2"): "小野塚",
        ("国", "2-3"): "小野塚",
        ("国", "3"): "小野塚",
        ("数", "1"): "梶永",
        ("数", "2"): "井上",
        ("数", "3"): "森山",
        ("英", "1"): "井野口",
        ("英", "2"): "箱崎",
        ("英", "3"): "林田",
        ("理", "1"): "金子ひ",
        ("理", "2-1"): "智田",
        ("理", "2-2"): "智田", 
        ("理", "2-3"): "金子ひ",
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
    
    # 学年とクラスを抽出
    if "年" in class_name:
        parts = class_name.split("年")
        grade = parts[0]
        class_num = parts[1].replace("組", "")
        
        # 2年の国語と理科は特殊
        if grade == "2" and subject in ["国", "理"]:
            key = f"{grade}-{class_num}"
            if (subject, key) in teacher_map:
                return teacher_map[(subject, key)]
    else:
        grade = ""
    
    # 教師を検索
    if (subject, grade) in teacher_map:
        return teacher_map[(subject, grade)]
    elif (subject, "") in teacher_map:
        return teacher_map[(subject, "")]
    
    return None

if __name__ == "__main__":
    check_initial_conflicts()