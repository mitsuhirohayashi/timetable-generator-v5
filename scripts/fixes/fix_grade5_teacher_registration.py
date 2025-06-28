"""5組の複数教師登録を修正するスクリプト"""
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.domain.value_objects.time_slot import Subject, ClassReference, Teacher
from typing import List, Dict, Optional

class EnhancedTeacherMappingRepository(TeacherMappingRepository):
    """複数教師対応を強化したTeacherMappingRepository"""
    
    def get_all_teachers_for_subject_class(
        self, 
        mapping: Dict, 
        subject: Subject, 
        class_ref: ClassReference
    ) -> List[Teacher]:
        """指定された教科・クラスの全ての担当教員を取得
        
        複数の教師が同じクラス・教科を担当している場合、
        全ての教師を返します。
        """
        teachers = []
        for teacher_name, assignments in mapping.items():
            for assigned_subject, assigned_classes in assignments:
                if assigned_subject == subject and class_ref in assigned_classes:
                    teacher = Teacher(teacher_name)
                    if teacher not in teachers:
                        teachers.append(teacher)
        return teachers

def test_enhanced_repository():
    """修正されたリポジトリのテスト"""
    base_path = project_root / "data" / "config"
    repo = EnhancedTeacherMappingRepository(base_path)
    
    # 教師マッピングを読み込み
    mapping = repo.load_teacher_mapping("teacher_subject_mapping.csv")
    
    # 5組の国語教師を確認
    kokugo = Subject("国")
    grade5_classes = [
        ClassReference(1, 5),
        ClassReference(2, 5),
        ClassReference(3, 5)
    ]
    
    print("=== 5組の国語教師（修正版） ===")
    for class_ref in grade5_classes:
        teachers = repo.get_all_teachers_for_subject_class(mapping, kokugo, class_ref)
        print(f"\n{class_ref}の国語教師:")
        for teacher in teachers:
            print(f"  - {teacher.name}")
    
    # その他の科目もチェック
    print("\n=== 5組のその他の科目（複数教師がいる場合） ===")
    subjects = ["美", "家", "保", "理"]
    
    for subject_name in subjects:
        subject = Subject(subject_name)
        has_multiple = False
        
        for class_ref in grade5_classes:
            teachers = repo.get_all_teachers_for_subject_class(mapping, subject, class_ref)
            if len(teachers) > 1:
                if not has_multiple:
                    print(f"\n{subject_name}:")
                    has_multiple = True
                print(f"  {class_ref}: {', '.join(t.name for t in teachers)}")

def create_modified_csv_repository():
    """修正版のCSVSchoolRepositoryを作成する案"""
    print("\n=== CSVSchoolRepositoryの修正案 ===")
    print("""
修正箇所: CSVSchoolRepository.load_school_data()メソッド

現在のコード（266-279行）:
    # 教員マッピングから実際の教員を取得
    teacher = teacher_mapping_repo.get_teacher_for_subject_class(teacher_mapping, subject, class_ref)
    
    # マッピングにない場合はスキップ（実在の教員のみを使用）
    if not teacher:
        ...
        continue
    
    school.assign_teacher_subject(teacher, subject)
    school.assign_teacher_to_class(teacher, subject, class_ref)

修正案:
    # 教員マッピングから全ての教員を取得（複数教師対応）
    if hasattr(teacher_mapping_repo, 'get_all_teachers_for_subject_class'):
        teachers = teacher_mapping_repo.get_all_teachers_for_subject_class(teacher_mapping, subject, class_ref)
    else:
        # 後方互換性のため
        teacher = teacher_mapping_repo.get_teacher_for_subject_class(teacher_mapping, subject, class_ref)
        teachers = [teacher] if teacher else []
    
    # マッピングにない場合はスキップ（実在の教員のみを使用）
    if not teachers:
        ...
        continue
    
    # 全ての教師を登録
    for teacher in teachers:
        school.assign_teacher_subject(teacher, subject)
        # 注：assign_teacher_to_classは1人しか登録できないため、
        # 最初の教師のみを「正式な担当」として登録
        if teachers.index(teacher) == 0:
            school.assign_teacher_to_class(teacher, subject, class_ref)
""")

if __name__ == "__main__":
    test_enhanced_repository()
    create_modified_csv_repository()