#!/usr/bin/env python3
"""
教師不在違反をチェックし、既存教師での修正案を提示するスクリプト
"""
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import csv

from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject


class TeacherAbsenceChecker:
    """教師不在違反チェッカー"""
    
    def __init__(self):
        self.data_dir = project_root / "data"
        self.followup_parser = EnhancedFollowUpParser(self.data_dir / "input")
        self.teacher_mapping_repo = TeacherMappingRepository(self.data_dir)
        self.teacher_mapping = self.teacher_mapping_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
        
        # 教科別の教師リストを作成
        self.subject_teachers = self._build_subject_teacher_mapping()
        
    def _build_subject_teacher_mapping(self) -> Dict[str, List[str]]:
        """教科別の教師リストを構築"""
        subject_teachers = defaultdict(list)
        
        # teacher_subject_mapping.csvから教科別教師リストを作成
        # 構造: Dict[教員名, List[Tuple[教科, List[担当クラス]]]]
        for teacher_name, subject_list in self.teacher_mapping.items():
            if teacher_name in ["欠課", "未定", "TBA"]:
                continue
            for subject, class_refs in subject_list:
                subject_name = subject.name
                if teacher_name not in subject_teachers[subject_name]:
                    subject_teachers[subject_name].append(teacher_name)
        
        # 手動で追加（CLAUDE.mdの情報より）
        known_mappings = {
            "国": ["寺田", "小野塚"],
            "数": ["梶永", "井上", "森山"],
            "英": ["井野口", "箱崎", "林田"],
            "社": ["蒲地", "北"],
            "理": ["金子ひ", "智田", "白石"],
            "音": ["塚本"],
            "美": ["青井", "金子み"],
            "保": ["永山", "野口", "財津"],
            "技": ["林"],
            "家": ["金子み"],
            "道": ["各担任"],  # 担任が担当
            "学": ["各担任"],  # 担任が担当
            "総": ["各担任"],  # 担任が担当
            "学総": ["各担任"],  # 担任が担当
        }
        
        # 既知のマッピングで補強
        for subject, teachers in known_mappings.items():
            if subject not in subject_teachers:
                subject_teachers[subject] = teachers
            else:
                for teacher in teachers:
                    if teacher not in subject_teachers[subject] and teacher != "各担任":
                        subject_teachers[subject].append(teacher)
        
        return dict(subject_teachers)
    
    def check_input_csv(self, input_file: str = "input/input.csv") -> List[Dict]:
        """input.csvの教師不在違反をチェック"""
        # Follow-up.csvから教師不在情報を読み込み
        followup_result = self.followup_parser.parse_file()
        teacher_absences = followup_result.get("teacher_absences", [])
        
        # TeacherAbsenceLoaderに情報を設定
        absence_loader = TeacherAbsenceLoader()
        absence_loader.update_absences_from_parsed_data(teacher_absences)
        
        violations = []
        
        # input.csvを読み込み
        input_path = self.data_dir / input_file
        with open(input_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # 曜日行
            periods = next(reader)  # 時限行
            
            # タイムスロットのマッピングを作成
            time_slots = []
            for i in range(1, len(periods)):
                if periods[i]:
                    day_index = (i - 1) // 6
                    days = ["月", "火", "水", "木", "金"]
                    if day_index < len(days):
                        time_slots.append(TimeSlot(days[day_index], int(periods[i])))
            
            # 各クラスの行を処理
            for row in reader:
                if not row or not row[0] or row[0] == '':
                    continue
                    
                class_name = row[0]
                try:
                    class_ref = self._parse_class_name(class_name)
                except:
                    continue
                
                # 各時限の授業をチェック
                for i, subject_name in enumerate(row[1:]):
                    if i >= len(time_slots):
                        break
                        
                    subject_name = subject_name.strip()
                    if not subject_name or subject_name == "0":
                        continue
                    
                    # 特殊記号をスキップ
                    if subject_name.startswith("非"):  # 非○○制約
                        continue
                    if subject_name in ["行", "欠", "0"]:  # 行事、欠課
                        continue
                    
                    time_slot = time_slots[i]
                    
                    # 教師を特定
                    teacher = self._get_teacher_for_subject(subject_name, class_ref)
                    if not teacher:
                        continue
                    
                    # 教師不在チェック
                    if absence_loader.is_teacher_absent(teacher, time_slot.day, time_slot.period):
                        # 不在理由を取得
                        reason = self._get_absence_reason(teacher_absences, teacher, time_slot)
                        
                        violations.append({
                            "class": class_name,
                            "time_slot": time_slot,
                            "subject": subject_name,
                            "teacher": teacher,
                            "reason": reason,
                            "alternatives": self._find_alternative_teachers(subject_name, time_slot, teacher)
                        })
        
        return violations
    
    def _parse_class_name(self, class_name: str) -> ClassReference:
        """クラス名をパース"""
        # 例: "1年1組" -> ClassReference(1, 1)
        import re
        match = re.match(r'(\d+)年(\d+)組', class_name)
        if match:
            return ClassReference(int(match.group(1)), int(match.group(2)))
        raise ValueError(f"Invalid class name: {class_name}")
    
    def _get_teacher_for_subject(self, subject_name: str, class_ref: ClassReference) -> Optional[str]:
        """教科とクラスから教師を特定"""
        if not subject_name or subject_name in ["行", "欠", "0"]:
            return None
            
        # teacher_mappingから教師を探す
        # 構造: Dict[教員名, List[Tuple[教科, List[担当クラス]]]]
        try:
            subject = Subject(subject_name)
        except:
            # 無効な教科名の場合はNone
            return None
        
        for teacher_name, subject_list in self.teacher_mapping.items():
            if teacher_name in ["欠課", "未定", "TBA"]:
                continue
            for subj, class_refs in subject_list:
                if subj.name == subject.name and class_ref in class_refs:
                    return teacher_name
        
        # 担任科目の場合
        if subject_name in ["道", "学", "総", "学総", "YT"]:
            return self._get_homeroom_teacher(class_ref)
        
        return None
    
    def _get_homeroom_teacher(self, class_ref: ClassReference) -> Optional[str]:
        """担任教師を取得"""
        homeroom_teachers = {
            (1, 1): "金子ひ", (1, 2): "井野口", (1, 3): "梶永",
            (2, 1): "塚本", (2, 2): "野口", (2, 3): "永山",
            (3, 1): "白石", (3, 2): "森山", (3, 3): "北",
            (1, 5): "金子み", (2, 5): "金子み", (3, 5): "金子み",
            (1, 6): "財津", (2, 6): "財津", (3, 6): "財津",
            (1, 7): "智田", (2, 7): "智田", (3, 7): "智田",
        }
        return homeroom_teachers.get((class_ref.grade, class_ref.class_number))
    
    def _get_absence_reason(self, teacher_absences, teacher: str, time_slot: TimeSlot) -> str:
        """教師の不在理由を取得"""
        for absence in teacher_absences:
            if absence.teacher_name == teacher and absence.day == time_slot.day:
                if not absence.periods or time_slot.period in absence.periods:
                    return absence.reason
        return "不在"
    
    def _find_alternative_teachers(self, subject: str, time_slot: TimeSlot, absent_teacher: str) -> List[str]:
        """代替可能な教師を探す"""
        alternatives = []
        
        # 同じ教科を教えられる教師を探す
        if subject in self.subject_teachers:
            for teacher in self.subject_teachers[subject]:
                if teacher != absent_teacher and teacher != "各担任":
                    # TODO: その時間に空いているかチェック（現在のスケジュールが必要）
                    alternatives.append(teacher)
        
        return alternatives
    
    def print_violations_report(self, violations: List[Dict]):
        """違反レポートを出力"""
        print("\n" + "="*80)
        print("教師不在違反チェック結果")
        print("="*80)
        
        if not violations:
            print("\n✅ 教師不在違反は見つかりませんでした。")
            return
        
        print(f"\n❌ {len(violations)}件の教師不在違反が見つかりました：\n")
        
        # 教師別にグループ化
        by_teacher = defaultdict(list)
        for v in violations:
            by_teacher[v["teacher"]].append(v)
        
        for teacher, teacher_violations in sorted(by_teacher.items()):
            print(f"\n【{teacher}先生】")
            reason = teacher_violations[0]["reason"]
            print(f"  不在理由: {reason}")
            print("  違反配置:")
            
            for v in sorted(teacher_violations, key=lambda x: (x["time_slot"].day, x["time_slot"].period)):
                alt_str = ""
                if v["alternatives"]:
                    alt_str = f" → 代替候補: {', '.join(v['alternatives'])}"
                else:
                    alt_str = " → 代替候補なし（削除推奨）"
                
                print(f"    - {v['time_slot']} {v['class']} {v['subject']}{alt_str}")
        
        print("\n" + "-"*80)
        print("修正方法:")
        print("1. scripts/fixes/reassign_with_existing_teachers.py を実行して自動修正")
        print("2. 手動で代替教師を割り当て")
        print("3. 代替不可能な場合は空きコマにする")
        print("="*80)


def main():
    """メイン処理"""
    print("教師不在違反チェックを開始します...")
    
    checker = TeacherAbsenceChecker()
    violations = checker.check_input_csv()
    checker.print_violations_report(violations)
    
    # 違反情報を保存（次のスクリプトで使用）
    if violations:
        import json
        output_file = project_root / "data" / "output" / "teacher_absence_violations.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(violations, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n違反情報を保存しました: {output_file}")


if __name__ == "__main__":
    main()