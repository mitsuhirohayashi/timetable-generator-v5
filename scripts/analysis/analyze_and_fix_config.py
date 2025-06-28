#!/usr/bin/env python3
"""設定ファイルの分析と修正案作成"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from collections import defaultdict
import json
from src.infrastructure.config.path_config import path_config

class ConfigAnalyzer:
    """設定ファイル分析クラス"""
    
    def __init__(self):
        self.config_dir = path_config.config_dir
        self.data = {}
        
    def load_all_configs(self):
        """全ての設定ファイルを読み込み"""
        print("=== 設定ファイルの読み込み ===\n")
        
        # 1. teacher_subject_mapping.csv
        self.data['teacher_mapping'] = pd.read_csv(
            self.config_dir / "teacher_subject_mapping.csv"
        )
        print(f"✓ teacher_subject_mapping.csv: {len(self.data['teacher_mapping'])}行")
        
        # 2. base_timetable.csv (標準時数)
        # ヘッダーが複数行あるので、スキップして読み込み
        self.data['base_timetable'] = pd.read_csv(
            self.config_dir / "base_timetable.csv",
            skiprows=1  # 最初の説明行をスキップ
        )
        print(f"✓ base_timetable.csv: {len(self.data['base_timetable'])}行")
        
        # 3. output.csv (生成された時間割)
        output_path = path_config.output_dir / "output.csv"
        if output_path.exists():
            self.data['output'] = pd.read_csv(output_path)
            print(f"✓ output.csv: {len(self.data['output'])}行")
        
    def analyze_teacher_workload(self):
        """教師の負担を分析"""
        print("\n=== 教師負担分析 ===\n")
        
        df = self.data['teacher_mapping']
        
        # 教師ごとの担当クラス数を集計
        teacher_stats = defaultdict(lambda: {
            'subjects': defaultdict(list),
            'total_classes': 0,
            'total_hours': 0
        })
        
        for _, row in df.iterrows():
            teacher = row['教員名']
            subject = row['教科']
            grade = row['学年']
            class_num = row['組']
            class_ref = f"{grade}年{class_num}組"
            
            teacher_stats[teacher]['subjects'][subject].append(class_ref)
            teacher_stats[teacher]['total_classes'] += 1
        
        # 標準時数から必要授業時間を計算
        base_df = self.data['base_timetable']
        subject_hours = {}
        
        # base_timetableの最初の列がクラス名
        for idx, row in base_df.iterrows():
            if idx == 0:  # ヘッダー行をスキップ
                continue
            class_ref = row.iloc[0]  # 最初の列がクラス名
            if pd.isna(class_ref) or class_ref == '':
                continue
                
            for col_idx, col in enumerate(base_df.columns[1:], 1):
                value = row.iloc[col_idx]
                if pd.notna(value) and isinstance(value, (int, float)) and value > 0:
                    if col not in subject_hours:
                        subject_hours[col] = {}
                    subject_hours[col][class_ref] = int(value)
        
        # 各教師の週当たり必要授業時間を計算
        for teacher, stats in teacher_stats.items():
            total_hours = 0
            for subject, classes in stats['subjects'].items():
                for class_ref in classes:
                    if subject in subject_hours and class_ref in subject_hours[subject]:
                        total_hours += subject_hours[subject][class_ref]
            stats['total_hours'] = total_hours
        
        # 問題のある教師を特定（週30時間を超える）
        MAX_HOURS_PER_WEEK = 30
        problematic_teachers = []
        
        print("【教師別負担状況】")
        print(f"{'教師名':<10} {'担当クラス数':>12} {'週授業時間':>10} {'状態':>10}")
        print("-" * 50)
        
        for teacher, stats in sorted(teacher_stats.items(), 
                                   key=lambda x: x[1]['total_hours'], 
                                   reverse=True):
            status = "過負荷" if stats['total_hours'] > MAX_HOURS_PER_WEEK else "適正"
            if status == "過負荷":
                problematic_teachers.append((teacher, stats))
            
            print(f"{teacher:<10} {stats['total_classes']:>12} "
                  f"{stats['total_hours']:>10} {status:>10}")
        
        return teacher_stats, problematic_teachers
    
    def analyze_subject_coverage(self):
        """科目別の教師カバレッジを分析"""
        print("\n=== 科目別教師配置分析 ===\n")
        
        df = self.data['teacher_mapping']
        
        # 科目別の教師数を集計
        subject_teachers = defaultdict(set)
        subject_classes = defaultdict(set)
        
        for _, row in df.iterrows():
            teacher = row['教員名']
            subject = row['教科']
            class_ref = f"{row['学年']}年{row['組']}組"
            
            subject_teachers[subject].add(teacher)
            subject_classes[subject].add(class_ref)
        
        print(f"{'科目':<10} {'教師数':>8} {'クラス数':>10} {'教師/クラス比':>15}")
        print("-" * 50)
        
        insufficient_subjects = []
        
        for subject in sorted(subject_teachers.keys()):
            num_teachers = len(subject_teachers[subject])
            num_classes = len(subject_classes[subject])
            ratio = num_teachers / num_classes if num_classes > 0 else 0
            
            print(f"{subject:<10} {num_teachers:>8} {num_classes:>10} {ratio:>15.2f}")
            
            # 教師不足の科目を特定（比率が0.5未満）
            if ratio < 0.5:
                insufficient_subjects.append({
                    'subject': subject,
                    'teachers': list(subject_teachers[subject]),
                    'classes': list(subject_classes[subject]),
                    'shortage': int(num_classes * 0.7 - num_teachers)  # 理想は0.7倍
                })
        
        return subject_teachers, insufficient_subjects
    
    def calculate_required_teachers(self):
        """必要な教師数を計算"""
        print("\n=== 必要教師数の計算 ===\n")
        
        # 時間割から実際の配置状況を分析
        if 'output' not in self.data:
            print("警告: output.csvが見つかりません")
            return
        
        df = self.data['output']
        
        # 各時間帯の科目配置を収集
        time_subject_count = defaultdict(lambda: defaultdict(int))
        
        # 列名から曜日と時限を抽出
        days = ["月", "火", "水", "木", "金"]
        periods = list(range(1, 7))
        
        for day in days:
            for period in periods:
                col_name = f"{day}.{period}" if f"{day}.{period}" in df.columns else None
                if not col_name:
                    # 別の形式を試す
                    for col in df.columns:
                        if day in col and str(period) in col:
                            col_name = col
                            break
                
                if col_name and col_name in df.columns:
                    for _, row in df.iterrows():
                        if pd.notna(row[col_name]) and row[col_name] not in ['', ' ']:
                            subject = row[col_name]
                            time_subject_count[(day, period)][subject] += 1
        
        # 各科目の最大同時開講数を計算
        max_concurrent = defaultdict(int)
        
        for (day, period), subjects in time_subject_count.items():
            for subject, count in subjects.items():
                if count > max_concurrent[subject]:
                    max_concurrent[subject] = count
        
        print("【科目別必要教師数】")
        print(f"{'科目':<10} {'最大同時開講数':>15} {'現在の教師数':>15} {'必要追加数':>12}")
        print("-" * 60)
        
        df_mapping = self.data['teacher_mapping']
        current_teachers = defaultdict(set)
        
        for _, row in df_mapping.iterrows():
            current_teachers[row['教科']].add(row['教員名'])
        
        additional_needs = {}
        
        for subject in sorted(max_concurrent.keys()):
            if subject in ['欠', 'YT', '道', '学', '総', '行', 'テスト']:
                continue  # 固定科目は除外
            
            max_count = max_concurrent[subject]
            current_count = len(current_teachers.get(subject, set()))
            needed = max(0, max_count - current_count)
            
            if needed > 0:
                additional_needs[subject] = needed
            
            print(f"{subject:<10} {max_count:>15} {current_count:>15} {needed:>12}")
        
        return max_concurrent, additional_needs
    
    def generate_fix_proposals(self, problematic_teachers, insufficient_subjects, additional_needs):
        """修正案を生成"""
        print("\n=== 設定ファイル修正案 ===\n")
        
        proposals = []
        
        # 1. 過負荷教師の負担軽減
        print("【1. 過負荷教師の負担軽減】")
        for teacher, stats in problematic_teachers[:5]:  # 上位5名
            print(f"\n{teacher}先生（週{stats['total_hours']}時間）:")
            
            # 最も多くのクラスを担当している科目から軽減
            for subject, classes in sorted(stats['subjects'].items(), 
                                         key=lambda x: len(x[1]), 
                                         reverse=True):
                if len(classes) > 3:
                    # 半分のクラスを他の教師に移管する提案
                    move_count = len(classes) // 2
                    print(f"  - {subject}: {len(classes)}クラス → {len(classes) - move_count}クラス"
                          f"（{move_count}クラスを他教師へ）")
                    
                    proposals.append({
                        'type': 'reduce_load',
                        'teacher': teacher,
                        'subject': subject,
                        'current_classes': classes,
                        'reduce_to': len(classes) - move_count
                    })
        
        # 2. 教師不足科目への追加
        print("\n【2. 教師不足科目への追加配置】")
        for need in insufficient_subjects[:5]:  # 上位5科目
            subject = need['subject']
            shortage = need['shortage']
            
            print(f"\n{subject}: {shortage}名の教師追加が必要")
            print(f"  現在の教師: {', '.join(need['teachers'])}")
            
            # 追加教師の提案
            for i in range(shortage):
                new_teacher_name = f"{subject}教諭{len(need['teachers']) + i + 1}"
                print(f"  + {new_teacher_name}を追加")
                
                proposals.append({
                    'type': 'add_teacher',
                    'subject': subject,
                    'teacher_name': new_teacher_name,
                    'assign_classes': need['classes'][i::shortage]  # 均等に分配
                })
        
        # 3. 同時開講対応
        print("\n【3. 同時開講対応の教師追加】")
        for subject, needed in sorted(additional_needs.items(), 
                                    key=lambda x: x[1], 
                                    reverse=True)[:5]:
            print(f"{subject}: {needed}名の追加が必要")
            
            for i in range(needed):
                proposals.append({
                    'type': 'concurrent_teaching',
                    'subject': subject,
                    'teacher_name': f"{subject}非常勤{i+1}",
                    'reason': '同時開講対応'
                })
        
        return proposals
    
    def create_modified_config(self, proposals):
        """修正した設定ファイルを作成"""
        print("\n=== 修正設定ファイルの作成 ===\n")
        
        # 現在の設定をコピー
        modified_df = self.data['teacher_mapping'].copy()
        
        # 新しい行を追加するリスト
        new_rows = []
        
        for proposal in proposals:
            if proposal['type'] == 'add_teacher':
                # 新しい教師を追加
                for class_ref in proposal['assign_classes']:
                    grade = int(class_ref[0])
                    class_num = int(class_ref[2])
                    
                    new_rows.append({
                        '教員名': proposal['teacher_name'],
                        '教科': proposal['subject'],
                        '学年': grade,
                        '組': class_num
                    })
            
            elif proposal['type'] == 'reduce_load':
                # 負担軽減（既存のマッピングから一部を削除）
                # 実際の実装では、どのクラスを移管するか詳細な検討が必要
                pass
            
            elif proposal['type'] == 'concurrent_teaching':
                # 同時開講対応の教師追加
                # 全クラスに対して補助的に配置
                subject = proposal['subject']
                
                # この科目を必要とする全クラスを取得
                base_df = self.data['base_timetable']
                for idx, row in base_df.iterrows():
                    if idx == 0:  # ヘッダー行をスキップ
                        continue
                    class_ref = row.iloc[0]
                    if pd.isna(class_ref) or class_ref == '':
                        continue
                    
                    # 科目の列を確認
                    if subject in base_df.columns:
                        value = row[subject]
                        if pd.notna(value) and isinstance(value, (int, float)) and value > 0:
                            # クラス名から学年と組を抽出
                            if '年' in class_ref and '組' in class_ref:
                                grade = int(class_ref.split('年')[0])
                                class_num = int(class_ref.split('年')[1].replace('組', ''))
                                
                                new_rows.append({
                                    '教員名': proposal['teacher_name'],
                                    '教科': subject,
                                    '学年': grade,
                                    '組': class_num
                                })
        
        # 新しい行を追加
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            modified_df = pd.concat([modified_df, new_df], ignore_index=True)
        
        # 修正版を保存
        output_path = self.config_dir / "teacher_subject_mapping_modified.csv"
        modified_df.to_csv(output_path, index=False)
        
        print(f"✓ 修正版を保存: {output_path}")
        print(f"  - 元の行数: {len(self.data['teacher_mapping'])}")
        print(f"  - 修正後の行数: {len(modified_df)}")
        print(f"  - 追加された行: {len(new_rows)}")
        
        return modified_df
    
    def generate_summary_report(self, teacher_stats, problematic_teachers, 
                              insufficient_subjects, additional_needs, proposals):
        """サマリーレポートを生成"""
        report = {
            'analysis_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current_status': {
                'total_teachers': len(teacher_stats),
                'overloaded_teachers': len(problematic_teachers),
                'insufficient_subjects': len(insufficient_subjects),
                'total_additional_teachers_needed': sum(additional_needs.values())
            },
            'problematic_teachers': [
                {
                    'name': teacher,
                    'weekly_hours': stats['total_hours'],
                    'total_classes': stats['total_classes'],
                    'subjects': {
                        subject: len(classes) 
                        for subject, classes in stats['subjects'].items()
                    }
                }
                for teacher, stats in problematic_teachers
            ],
            'insufficient_subjects': insufficient_subjects,
            'additional_needs': additional_needs,
            'proposals': proposals,
            'recommendations': [
                "1. 主要5教科（国語、数学、英語、理科、社会）に各学年1名以上の専任教師を配置",
                "2. 音楽、美術、技術、家庭科などの実技系科目は非常勤講師の活用を検討",
                "3. 過負荷教師の担当クラスを段階的に削減（1学期に2-3クラスずつ）",
                "4. 新任教師の採用時は、不足科目を優先的に補充",
                "5. 緊急措置として、管理職や専科教員の授業担当も検討"
            ]
        }
        
        # レポートを保存
        report_path = Path("config_analysis_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 分析レポートを保存: {report_path}")
        
        return report

def main():
    """メイン処理"""
    print("=== 設定ファイル分析・修正ツール ===\n")
    
    analyzer = ConfigAnalyzer()
    
    # 1. 設定ファイルを読み込み
    analyzer.load_all_configs()
    
    # 2. 教師負担を分析
    teacher_stats, problematic_teachers = analyzer.analyze_teacher_workload()
    
    # 3. 科目別カバレッジを分析
    subject_teachers, insufficient_subjects = analyzer.analyze_subject_coverage()
    
    # 4. 必要教師数を計算
    max_concurrent, additional_needs = analyzer.calculate_required_teachers()
    
    # 5. 修正案を生成
    proposals = analyzer.generate_fix_proposals(
        problematic_teachers, insufficient_subjects, additional_needs
    )
    
    # 6. 修正設定ファイルを作成
    modified_df = analyzer.create_modified_config(proposals)
    
    # 7. サマリーレポートを生成
    report = analyzer.generate_summary_report(
        teacher_stats, problematic_teachers, insufficient_subjects,
        additional_needs, proposals
    )
    
    print("\n=== 完了 ===")
    print("\n生成されたファイル:")
    print("1. teacher_subject_mapping_modified.csv - 修正された教師配置")
    print("2. config_analysis_report.json - 詳細分析レポート")
    print("\n次のステップ:")
    print("1. 修正案を確認し、必要に応じて手動で調整")
    print("2. teacher_subject_mapping.csvを修正版で置き換え")
    print("3. 時間割を再生成して検証")

if __name__ == "__main__":
    main()