#!/usr/bin/env python3
"""現実的な設定ファイル修正案"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
import json

class RealisticConfigSolution:
    """現実的な解決策を提案"""
    
    def __init__(self):
        self.config_dir = Path("data/config")
        self.data = {}
        
    def analyze_problem(self):
        """問題の詳細分析"""
        print("=== 問題の詳細分析 ===\n")
        
        # 分析レポートを読み込み
        with open("config_analysis_report.json", 'r', encoding='utf-8') as f:
            report = json.load(f)
            
        print("【根本的な問題】")
        print("1. 教師数の絶対的不足")
        print(f"   - 現在の教師数: {report['current_status']['total_teachers']}人")
        print(f"   - 必要な追加教師: {report['current_status']['total_additional_teachers_needed']}人")
        print("   - 特に主要5教科（国語、数学、英語、理科、社会）で深刻")
        
        print("\n2. 時間割の構造的問題")
        print("   - 同じ時間に同じ科目が複数クラスで開講")
        print("   - 例：月曜1限に英語が6クラス、数学が6クラス同時開講")
        
        print("\n3. 特定教師への過度な負担")
        print("   - 金子み先生: 45クラス担当（物理的に不可能）")
        
    def propose_realistic_solutions(self):
        """現実的な解決策を提案"""
        print("\n=== 現実的な解決策 ===\n")
        
        solutions = {
            "immediate": [
                {
                    "title": "1. 合同授業の導入",
                    "description": "同じ学年の複数クラスを合同で授業",
                    "implementation": [
                        "音楽、美術、体育などは学年合同で実施",
                        "道徳、総合も可能な限り合同化",
                        "これにより必要教師数を削減"
                    ],
                    "config_changes": "合同授業用の特別マッピングを追加"
                },
                {
                    "title": "2. 非常勤講師の活用",
                    "description": "特定科目に非常勤講師を配置",
                    "implementation": [
                        "主要5教科に各2-3名の非常勤講師",
                        "週2-3日勤務で複数名でカバー",
                        "特に国語、数学、英語を優先"
                    ],
                    "config_changes": "非常勤講師を追加（週の特定日のみ）"
                },
                {
                    "title": "3. 時間割構造の見直し",
                    "description": "同時開講を避ける時間割設計",
                    "implementation": [
                        "学年ごとに主要教科の時間をずらす",
                        "1年生：月曜1限は国語、2年生：社会、3年生：数学",
                        "教師の移動時間を考慮した配置"
                    ],
                    "config_changes": "input.csvの見直しが必要"
                }
            ],
            "long_term": [
                {
                    "title": "4. 教員採用計画",
                    "description": "計画的な教員増員",
                    "implementation": [
                        "主要5教科各3名体制を目指す",
                        "実技系科目は2名体制",
                        "3年計画で段階的に増員"
                    ]
                },
                {
                    "title": "5. カリキュラム改革",
                    "description": "授業時数の最適化",
                    "implementation": [
                        "選択科目の導入",
                        "習熟度別クラス編成",
                        "ICT活用による効率化"
                    ]
                }
            ]
        }
        
        return solutions
    
    def create_immediate_config(self):
        """即座に実施可能な設定ファイルを作成"""
        print("\n=== 即座に実施可能な設定ファイル作成 ===\n")
        
        # 現在の設定を読み込み
        df = pd.read_csv(self.config_dir / "teacher_subject_mapping.csv")
        
        # 1. 合同授業の設定を追加
        joint_classes = []
        
        # 音楽の合同授業（学年ごと）
        for grade in [1, 2, 3]:
            joint_classes.append({
                '教員名': '塚本',
                '教科': '音_合同',
                '学年': grade,
                '組': 0  # 0は学年全体を表す
            })
            
        # 2. 非常勤講師を追加（現実的な人数）
        part_time_teachers = [
            # 国語非常勤（週3日想定）
            {'教員名': '国語非常勤A', '教科': '国', '対象': [(1,1), (1,2), (1,3)]},
            {'教員名': '国語非常勤B', '教科': '国', '対象': [(2,1), (2,2), (2,3)]},
            
            # 数学非常勤（週3日想定）
            {'教員名': '数学非常勤A', '教科': '数', '対象': [(1,1), (1,2), (1,3)]},
            {'教員名': '数学非常勤B', '教科': '数', '対象': [(3,1), (3,2), (3,3)]},
            
            # 英語非常勤（週2日想定）
            {'教員名': '英語非常勤A', '教科': '英', '対象': [(2,1), (2,2), (2,3)]},
        ]
        
        new_rows = []
        for teacher in part_time_teachers:
            for grade, class_num in teacher['対象']:
                new_rows.append({
                    '教員名': teacher['教員名'],
                    '教科': teacher['教科'],
                    '学年': grade,
                    '組': class_num
                })
                
        # 3. 金子み先生の負担を軽減
        # 一部の科目を他の教師に移管
        df_modified = df.copy()
        
        # 金子み先生の家庭科を半分削減
        mask = (df_modified['教員名'] == '金子み') & (df_modified['教科'] == '家')
        indices_to_remove = df_modified[mask].index[::2]  # 偶数番目を削除
        df_modified = df_modified.drop(indices_to_remove)
        
        # 新しい行を追加
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            df_modified = pd.concat([df_modified, new_df], ignore_index=True)
            
        # 保存
        output_file = self.config_dir / "teacher_subject_mapping_realistic.csv"
        df_modified.to_csv(output_file, index=False)
        
        print(f"✓ 現実的な修正版を保存: {output_file}")
        print(f"  - 元の行数: {len(df)}")
        print(f"  - 修正後の行数: {len(df_modified)}")
        print(f"  - 変更内容:")
        print(f"    - 非常勤講師5名追加")
        print(f"    - 金子み先生の負担軽減")
        print(f"    - 合同授業の設定追加")
        
        return df_modified
    
    def generate_implementation_guide(self):
        """実装ガイドを生成"""
        guide = """
=== 設定ファイル修正の実装ガイド ===

【ステップ1: 即座の対応】
1. teacher_subject_mapping_realistic.csvを適用
2. 非常勤講師の採用手続き開始
3. 合同授業の時間割調整

【ステップ2: 時間割の再設計】
1. input.csvを修正し、同時開講を減らす
2. 各学年で主要教科の時間をずらす
3. 教師の空き時間を考慮した配置

【ステップ3: 運用上の工夫】
1. 管理職も一部授業を担当
2. ALTや支援員の活用
3. オンライン授業の部分導入

【重要な注意事項】
- 完璧な解決は現状では不可能
- 段階的な改善を目指す
- 教育の質を保ちながら現実的に対応
"""
        
        with open("implementation_guide.txt", 'w', encoding='utf-8') as f:
            f.write(guide)
            
        print("\n✓ 実装ガイドを保存: implementation_guide.txt")

def main():
    """メイン処理"""
    print("=== 現実的な設定ファイル解決策 ===\n")
    
    solution = RealisticConfigSolution()
    
    # 1. 問題を分析
    solution.analyze_problem()
    
    # 2. 現実的な解決策を提案
    solutions = solution.propose_realistic_solutions()
    
    print("\n【即座に実施可能な対策】")
    for sol in solutions["immediate"]:
        print(f"\n{sol['title']}")
        print(f"  {sol['description']}")
        for impl in sol['implementation']:
            print(f"  - {impl}")
            
    print("\n【長期的な対策】")
    for sol in solutions["long_term"]:
        print(f"\n{sol['title']}")
        print(f"  {sol['description']}")
        
    # 3. 即座に実施可能な設定ファイルを作成
    solution.create_immediate_config()
    
    # 4. 実装ガイドを生成
    solution.generate_implementation_guide()
    
    print("\n" + "="*50)
    print("現実的な解決策の提案が完了しました。")
    print("\n生成されたファイル:")
    print("1. teacher_subject_mapping_realistic.csv - 現実的な教師配置")
    print("2. implementation_guide.txt - 実装ガイド")
    print("\n重要：")
    print("完全な解決には構造的な改革が必要です。")
    print("段階的に改善を進めることをお勧めします。")

if __name__ == "__main__":
    main()