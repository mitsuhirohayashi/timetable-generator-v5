"""5組の国語教師選択問題をデバッグするスクリプト"""
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.domain.value_objects.time_slot import Subject, ClassReference
from src.domain.services.grade5_teacher_selector import Grade5TeacherSelector

def debug_grade5_teachers():
    """5組の国語教師設定を調査"""
    print("=== 5組の国語教師選択デバッグ ===\n")
    
    # 学校データを読み込み
    base_path = project_root / "data" / "config"
    repo = CSVSchoolRepository(base_path)
    school = repo.load_school_data("base_timetable.csv")
    
    # 国語の科目
    kokugo = Subject("国")
    
    # 5組のクラス
    grade5_classes = [
        ClassReference(1, 5),
        ClassReference(2, 5),
        ClassReference(3, 5)
    ]
    
    print("1. 国語を担当できる全教師:")
    kokugo_teachers = school.get_subject_teachers(kokugo)
    for teacher in kokugo_teachers:
        print(f"   - {teacher.name}")
    print()
    
    print("2. 各5組クラスに割り当てられた国語教師:")
    for class_ref in grade5_classes:
        assigned_teacher = school.get_assigned_teacher(kokugo, class_ref)
        print(f"   {class_ref}: {assigned_teacher.name if assigned_teacher else '未割当'}")
    print()
    
    print("3. Grade5TeacherSelectorでの選択テスト:")
    selector = Grade5TeacherSelector()
    
    # 複数回選択してみる
    selection_counts = {}
    for i in range(10):
        for class_ref in grade5_classes:
            selected = selector.select_teacher(school, kokugo, class_ref)
            if selected:
                teacher_name = selected.name
                if teacher_name not in selection_counts:
                    selection_counts[teacher_name] = 0
                selection_counts[teacher_name] += 1
    
    print("   10回の選択結果:")
    for teacher_name, count in selection_counts.items():
        print(f"   - {teacher_name}: {count}回")
    print()
    
    # 選択レポート
    print("4. 選択レポート:")
    report = selector.get_selection_report()
    if "国" in report["details"]:
        print("   国語の選択状況:")
        for teacher, count in report["details"]["国"].items():
            print(f"   - {teacher}: {count}回")
    
    # デバッグ情報を追加
    print("\n5. デバッグ情報:")
    print(f"   school._subject_teachers[国]に登録されている教師数: {len(kokugo_teachers)}")
    print(f"   selector.teacher_ratios: {selector.teacher_ratios}")
    
    # 金子み先生が登録されているか確認
    kaneko_found = False
    for teacher in kokugo_teachers:
        if "金子み" in teacher.name:
            kaneko_found = True
            print(f"   金子み先生が見つかりました: {teacher.name}")
    
    if not kaneko_found:
        print("   ⚠️ 金子み先生が国語教師として登録されていません！")

if __name__ == "__main__":
    debug_grade5_teachers()