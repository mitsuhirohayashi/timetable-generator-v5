#!/usr/bin/env python3
"""制約の実現可能性を事前にチェックするツール"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from collections import defaultdict
from typing import Dict
import networkx as nx
import matplotlib.pyplot as plt

class ConstraintFeasibilityChecker:
    """制約の実現可能性を分析"""
    
    def __init__(self):
        self.repo = CSVSchoolRepository('data')
        self.school = self.repo.load_school_data("config/base_timetable.csv")
        
    def check_teacher_capacity(self) -> Dict:
        """教師のキャパシティチェック"""
        # 必要な授業時数を計算
        required_hours = defaultdict(lambda: defaultdict(int))
        
        # 各クラスの必要時数を集計
        for class_name, subjects in self.school.class_subjects.items():
            for subject, hours in subjects.items():
                if hours > 0:
                    # 教師を特定
                    teachers = self.school.subject_teachers.get(subject, [])
                    if teachers:
                        # 簡単のため最初の教師に割り当て
                        teacher = teachers[0]
                        required_hours[teacher][class_name] += hours
        
        # 教師の利用可能時間を計算（週5日×6時限）
        max_hours_per_teacher = 30
        
        # キャパシティ分析
        capacity_issues = []
        teacher_load = {}
        
        for teacher, classes in required_hours.items():
            total_hours = sum(classes.values())
            teacher_load[teacher] = {
                'required': total_hours,
                'available': max_hours_per_teacher,
                'utilization': total_hours / max_hours_per_teacher * 100
            }
            
            if total_hours > max_hours_per_teacher:
                capacity_issues.append({
                    'teacher': teacher,
                    'required': total_hours,
                    'shortage': total_hours - max_hours_per_teacher,
                    'classes': dict(classes)
                })
        
        return {
            'teacher_load': teacher_load,
            'capacity_issues': capacity_issues,
            'feasible': len(capacity_issues) == 0
        }
    
    def check_constraint_conflicts(self) -> Dict:
        """制約間の競合をチェック"""
        conflicts = []
        
        # 1. 固定科目と必要時数の競合
        fixed_slots = 0
        for class_name in self.school.classes:
            # 月曜6限（1-2年は欠）
            if not class_name.startswith('3'):
                fixed_slots += 1
            # 火水金6限（1-2年はYT）
            if not class_name.startswith('3'):
                fixed_slots += 3
        
        total_slots = len(self.school.classes) * 30  # 週30コマ
        available_slots = total_slots - fixed_slots
        
        # 必要な総授業時数
        total_required = 0
        for class_name, subjects in self.school.class_subjects.items():
            total_required += sum(subjects.values())
        
        if total_required > available_slots:
            conflicts.append({
                'type': '時数不足',
                'detail': f'必要時数({total_required}) > 利用可能スロット({available_slots})',
                'severity': 'CRITICAL'
            })
        
        # 2. 5組同期と教師制約の競合
        grade5_classes = ['1年5組', '2年5組', '3年5組']
        grade5_subjects = set()
        for class_name in grade5_classes:
            if class_name in self.school.class_subjects:
                grade5_subjects.update(self.school.class_subjects[class_name].keys())
        
        # 5組で必要な教師数をチェック
        for subject in grade5_subjects:
            teachers = self.school.subject_teachers.get(subject, [])
            if len(teachers) < 1:
                conflicts.append({
                    'type': '教師不足',
                    'detail': f'5組の{subject}に教師が割り当てられていない',
                    'severity': 'HIGH'
                })
        
        # 3. 交流学級の制約競合
        exchange_pairs = {
            '1年6組': '1年1組',
            '1年7組': '1年2組',
            '2年6組': '2年3組',
            '2年7組': '2年2組',
            '3年6組': '3年3組',
            '3年7組': '3年2組'
        }
        
        for exchange, parent in exchange_pairs.items():
            # 自立活動の時数チェック
            if exchange in self.school.class_subjects:
                jiritsu_hours = self.school.class_subjects[exchange].get('自立', 0)
                if jiritsu_hours != 2:
                    conflicts.append({
                        'type': '自立活動時数',
                        'detail': f'{exchange}の自立活動が{jiritsu_hours}時間（2時間必要）',
                        'severity': 'MEDIUM'
                    })
        
        return {
            'conflicts': conflicts,
            'conflict_count': len(conflicts),
            'has_critical': any(c['severity'] == 'CRITICAL' for c in conflicts)
        }
    
    def visualize_constraint_dependencies(self):
        """制約の依存関係を可視化"""
        G = nx.DiGraph()
        
        # ノードを追加
        constraints = [
            '固定科目', '教師重複', '5組同期', '交流学級同期',
            '体育館使用', '日内重複', 'テスト期間', '教師不在'
        ]
        
        for c in constraints:
            G.add_node(c)
        
        # エッジ（依存関係）を追加
        dependencies = [
            ('固定科目', 'テスト期間'),  # テスト期間は固定科目に依存
            ('5組同期', '教師重複'),      # 5組同期は教師重複に影響
            ('交流学級同期', '教師重複'), # 交流学級も教師重複に影響
            ('体育館使用', '交流学級同期'), # 体育の同期は体育館使用に影響
            ('教師不在', '教師重複'),     # 教師不在は重複制約に影響
        ]
        
        G.add_edges_from(dependencies)
        
        # グラフを描画
        plt.figure(figsize=(10, 8))
        pos = nx.spring_layout(G, seed=42)
        
        # ノードを描画
        nx.draw_networkx_nodes(G, pos, node_size=3000, node_color='lightblue')
        nx.draw_networkx_labels(G, pos, font_size=10, font_family='sans-serif')
        
        # エッジを描画
        nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True, 
                              arrowsize=20, arrowstyle='->')
        
        plt.title('制約の依存関係図')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig('constraint_dependencies.png', dpi=150)
        plt.close()
        
        return G
    
    def generate_feasibility_report(self) -> Dict:
        """実現可能性の総合レポート"""
        print("=== 制約実現可能性チェック ===\n")
        
        # 教師キャパシティチェック
        print("1. 教師キャパシティ分析")
        capacity_result = self.check_teacher_capacity()
        
        if capacity_result['feasible']:
            print("  ✓ 教師のキャパシティは十分です")
        else:
            print("  ✗ 教師のキャパシティ不足:")
            for issue in capacity_result['capacity_issues'][:3]:  # 上位3件
                print(f"    - {issue['teacher']}: {issue['shortage']}時間不足")
        
        # 制約競合チェック
        print("\n2. 制約競合分析")
        conflict_result = self.check_constraint_conflicts()
        
        if conflict_result['conflict_count'] == 0:
            print("  ✓ 制約間の競合はありません")
        else:
            print(f"  ✗ {conflict_result['conflict_count']}件の競合を検出:")
            for conflict in conflict_result['conflicts']:
                print(f"    - [{conflict['severity']}] {conflict['type']}: {conflict['detail']}")
        
        # 依存関係の可視化
        print("\n3. 制約依存関係の可視化")
        graph = self.visualize_constraint_dependencies()
        print("  constraint_dependencies.png に保存しました")
        
        # 実現可能性の判定
        feasibility_score = 100
        if not capacity_result['feasible']:
            feasibility_score -= 40
        if conflict_result['has_critical']:
            feasibility_score -= 30
        feasibility_score -= conflict_result['conflict_count'] * 5
        
        feasibility_score = max(0, feasibility_score)
        
        print(f"\n=== 実現可能性スコア: {feasibility_score}% ===")
        
        if feasibility_score >= 80:
            print("現在の制約セットは実現可能です。")
        elif feasibility_score >= 50:
            print("部分的な制約緩和により実現可能です。")
        else:
            print("大幅な制約緩和が必要です。")
        
        return {
            'capacity_analysis': capacity_result,
            'conflict_analysis': conflict_result,
            'feasibility_score': feasibility_score,
            'recommendation': self._generate_recommendations(capacity_result, conflict_result)
        }
    
    def _generate_recommendations(self, capacity_result, conflict_result):
        """改善推奨事項を生成"""
        recommendations = []
        
        if not capacity_result['feasible']:
            recommendations.append({
                'priority': 'HIGH',
                'action': '教師リソースの追加または授業分担の見直し',
                'details': '特に負荷の高い教師の授業を他の教師に分散'
            })
        
        for conflict in conflict_result['conflicts']:
            if conflict['severity'] == 'CRITICAL':
                recommendations.append({
                    'priority': 'CRITICAL',
                    'action': f"{conflict['type']}の解決",
                    'details': conflict['detail']
                })
        
        return recommendations

def main():
    checker = ConstraintFeasibilityChecker()
    report = checker.generate_feasibility_report()
    
    # レポートを保存
    import json
    with open('feasibility_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print("\n詳細は feasibility_report.json を参照してください。")

if __name__ == "__main__":
    main()