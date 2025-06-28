#!/usr/bin/env python3
"""非常勤講師を削除して元の教師配置に戻す"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import shutil
from datetime import datetime
from collections import defaultdict
from src.infrastructure.config.path_config import path_config

class OriginalTeacherRestorer:
    """元の教師配置に戻すクラス"""
    
    def __init__(self):
        self.config_dir = path_config.config_dir
        self.backup_dir = self.config_dir / "backups"
        
        # 削除する教師のパターン
        self.remove_patterns = [
            '非常勤',  # 全ての非常勤講師
            '教諭',    # 追加された教諭（教諭2、教諭3など）
        ]
        
        # 元の教師リスト（これらは残す）
        self.original_teachers = {
            '寺田', '小野塚', '蒲地', '北', '梶永', '井上', '森山',
            '金子ひ', '智田', '白石', '塚本', '青井', '金子み',
            '永山', '野口', '財津', '林', '井野口', '林田', '箱崎'
        }
        
    def analyze_current_mapping(self):
        """現在の教師マッピングを分析"""
        print("=== 現在の教師マッピング分析 ===\n")
        
        df = pd.read_csv(self.config_dir / "teacher_subject_mapping.csv")
        
        # 教師を分類
        original = []
        additional = []
        
        unique_teachers = df['教員名'].unique()
        
        for teacher in unique_teachers:
            if teacher in self.original_teachers:
                original.append(teacher)
            else:
                additional.append(teacher)
        
        print(f"元の教師: {len(original)}人")
        print(f"追加された教師: {len(additional)}人")
        
        if additional:
            print("\n【削除対象の教師】")
            for teacher in sorted(additional):
                count = len(df[df['教員名'] == teacher])
                print(f"  - {teacher}: {count}クラス担当")
        
        return df, additional
    
    def restore_original_teachers(self, df, additional_teachers):
        """元の教師配置に戻す"""
        print("\n=== 元の教師配置への復元 ===\n")
        
        # バックアップを作成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_file = self.config_dir / "teacher_subject_mapping.csv"
        backup_file = self.backup_dir / f"teacher_subject_mapping_before_restore_{timestamp}.csv"
        self.backup_dir.mkdir(exist_ok=True)
        shutil.copy2(original_file, backup_file)
        print(f"バックアップ作成: {backup_file}")
        
        # 追加された教師の行を削除
        rows_before = len(df)
        df_restored = df[~df['教員名'].isin(additional_teachers)]
        rows_after = len(df_restored)
        
        print(f"削除された行数: {rows_before - rows_after}")
        
        # 保存
        df_restored.to_csv(original_file, index=False)
        print(f"✓ 復元完了: {original_file}")
        
        return df_restored
    
    def verify_5_group_integrity(self, df):
        """5組の合同授業設定が保持されているか確認"""
        print("\n=== 5組の設定確認 ===\n")
        
        # 5組の科目別教師を確認
        grade5_classes = [(1, 5), (2, 5), (3, 5)]
        grade5_subjects = defaultdict(lambda: defaultdict(set))
        
        for _, row in df.iterrows():
            if (row['学年'], row['組']) in grade5_classes:
                subject = row['教科']
                teacher = row['教員名']
                grade5_subjects[subject][(row['学年'], row['組'])].add(teacher)
        
        all_ok = True
        for subject, classes in grade5_subjects.items():
            teachers = set()
            for grade_class, teacher_set in classes.items():
                teachers.update(teacher_set)
            
            if len(teachers) > 1:
                print(f"⚠️ {subject}: 複数の教師が担当 ({', '.join(teachers)})")
                all_ok = False
        
        if all_ok:
            print("✓ 5組の合同授業設定は正しく保持されています")
        
        return all_ok
    
    def analyze_teacher_load(self, df):
        """教師の負担を分析"""
        print("\n=== 教師負担分析（復元後） ===\n")
        
        teacher_count = defaultdict(int)
        teacher_subjects = defaultdict(set)
        
        for _, row in df.iterrows():
            teacher = row['教員名']
            subject = row['教科']
            teacher_count[teacher] += 1
            teacher_subjects[teacher].add(subject)
        
        print(f"{'教師名':<10} {'担当クラス数':>12} {'担当科目':>30}")
        print("-" * 55)
        
        for teacher in sorted(teacher_count.keys(), 
                             key=lambda x: teacher_count[x], 
                             reverse=True):
            subjects = ', '.join(sorted(teacher_subjects[teacher]))
            print(f"{teacher:<10} {teacher_count[teacher]:>12} {subjects:>30}")
        
        # 過負荷の教師を特定
        overloaded = [t for t, c in teacher_count.items() if c > 15]
        if overloaded:
            print(f"\n⚠️ 過負荷の教師（15クラス以上）: {', '.join(overloaded)}")
    
    def generate_report(self, removed_count):
        """レポートを生成"""
        report = {
            "execution_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "元の教師配置への復元",
            "removed_teachers_count": removed_count,
            "notes": [
                "非常勤講師と追加教諭を全て削除",
                "元の20人の教師のみに戻す",
                "5組の合同授業設定は維持"
            ],
            "next_steps": [
                "時間割の構造を見直す（同時開講を減らす）",
                "input.csvを修正して、学年ごとに主要教科の時間をずらす",
                "必要に応じて一部の授業を合同授業化"
            ]
        }
        
        report_path = Path("teacher_restoration_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ レポートを保存: {report_path}")

def main():
    """メイン処理"""
    print("=== 元の教師配置への復元 ===\n")
    print("このプログラムは追加された非常勤講師を削除し、")
    print("元の教師配置に戻します。\n")
    
    restorer = OriginalTeacherRestorer()
    
    # 1. 現在のマッピングを分析
    df, additional_teachers = restorer.analyze_current_mapping()
    
    if not additional_teachers:
        print("\n追加された教師はありません。")
        return
    
    # 2. 確認
    print(f"\n{len(additional_teachers)}人の追加教師を削除します。")
    response = input("続行しますか？ (y/n): ")
    
    if response.lower() != 'y':
        print("処理を中止しました。")
        return
    
    # 3. 復元を実行
    df_restored = restorer.restore_original_teachers(df, additional_teachers)
    
    # 4. 5組の設定を確認
    restorer.verify_5_group_integrity(df_restored)
    
    # 5. 教師負担を分析
    restorer.analyze_teacher_load(df_restored)
    
    # 6. レポートを生成
    restorer.generate_report(len(additional_teachers))
    
    print("\n" + "="*50)
    print("✅ 元の教師配置への復元が完了しました！")
    print("\n重要：")
    print("- 教師数が元に戻ったため、制約違反が増える可能性があります")
    print("- 時間割の構造的な見直しが必要です")
    print("- input.csvを修正して同時開講を減らすことを推奨します")

if __name__ == "__main__":
    main()