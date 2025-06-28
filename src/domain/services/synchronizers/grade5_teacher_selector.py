"""5組の教師選択サービス - 比率制御機能付き"""
import logging
import random
from typing import Dict, Optional, List, Set
from collections import defaultdict
from ....shared.mixins.logging_mixin import LoggingMixin

from ...value_objects.time_slot import Teacher, Subject, ClassReference
from ...entities.school import School


class Grade5TeacherSelector(LoggingMixin):
    """5組の教師を適切な比率で選択するサービス
    
    特定の科目に複数の教師が登録されている場合、
    設定された比率に基づいて教師を選択します。
    """
    
    def __init__(self, teacher_ratios=None):
        super().__init__()
        
        # 教師選択の履歴を記録
        # {(subject, teacher_name): count}
        self.selection_history: Dict[tuple, int] = defaultdict(int)
        
        # 科目ごとの教師比率設定（QA.txtから読み込み）
        # 例: {"国": {"金子み": 0.5, "寺田": 0.5}}
        self.teacher_ratios = teacher_ratios or {}
        
        # 5組のクラス
        self.grade5_classes = {"1年5組", "2年5組", "3年5組"}
    
    def select_teacher(
        self,
        school: School,
        subject: Subject,
        class_ref: ClassReference,
        available_teachers: Optional[Set[Teacher]] = None
    ) -> Optional[Teacher]:
        """5組の教師を選択する
        
        Args:
            school: 学校データ
            subject: 科目
            class_ref: クラス
            available_teachers: 利用可能な教師のセット（指定がない場合は全教師から選択）
            
        Returns:
            選択された教師、または None
        """
        # 5組でない場合は通常の選択
        if class_ref.full_name not in self.grade5_classes:
            return school.get_assigned_teacher(subject, class_ref)
        
        # 利用可能な教師を取得
        if available_teachers is None:
            all_teachers = list(school.get_subject_teachers(subject))
        else:
            all_teachers = [t for t in school.get_subject_teachers(subject) if t in available_teachers]
        
        if not all_teachers:
            return None
        
        # 比率設定がある科目の場合
        if subject.name in self.teacher_ratios:
            return self._select_by_ratio(subject, all_teachers)
        
        # 比率設定がない場合は、履歴に基づいて均等に選択
        return self._select_balanced(subject, all_teachers)
    
    def _select_by_ratio(self, subject: Subject, teachers: List[Teacher]) -> Optional[Teacher]:
        """設定された比率に基づいて教師を選択"""
        ratio_config = self.teacher_ratios[subject.name]
        
        # 利用可能な教師の中から、比率設定に含まれる教師をフィルタ
        ratio_teachers = []
        for teacher in teachers:
            if teacher.name in ratio_config:
                ratio_teachers.append(teacher)
        
        if not ratio_teachers:
            # 比率設定に含まれる教師がいない場合は、最初の教師を返す
            return teachers[0]
        
        # 現在の選択履歴を取得
        current_counts = {}
        total_count = 0
        for teacher in ratio_teachers:
            count = self.selection_history[(subject.name, teacher.name)]
            current_counts[teacher.name] = count
            total_count += count
        
        # 目標比率と現在の比率の差を計算
        if total_count == 0:
            # 初回選択時はランダムに選択
            selected = random.choice(ratio_teachers)
        else:
            # 最も比率が低い教師を選択
            teacher_scores = []
            for teacher in ratio_teachers:
                target_ratio = ratio_config[teacher.name]
                current_ratio = current_counts[teacher.name] / total_count
                # スコアが低いほど優先度が高い
                score = current_ratio - target_ratio
                teacher_scores.append((score, teacher))
            
            # スコアでソートして最も低い教師を選択
            teacher_scores.sort(key=lambda x: x[0])
            selected = teacher_scores[0][1]
        
        # 選択履歴を更新
        self.selection_history[(subject.name, selected.name)] += 1
        
        self.logger.debug(
            f"5組 {subject.name} 教師選択: {selected.name} "
            f"(現在の比率: {self._get_current_ratios(subject.name, ratio_teachers)})"
        )
        
        return selected
    
    def _select_balanced(self, subject: Subject, teachers: List[Teacher]) -> Optional[Teacher]:
        """履歴に基づいて均等に選択"""
        if not teachers:
            return None
        
        # 各教師の選択回数を取得
        teacher_counts = []
        for teacher in teachers:
            count = self.selection_history[(subject.name, teacher.name)]
            teacher_counts.append((count, teacher))
        
        # 選択回数でソート（少ない順）
        teacher_counts.sort(key=lambda x: x[0])
        
        # 最も選択回数が少ない教師たちを取得
        min_count = teacher_counts[0][0]
        candidates = [t for c, t in teacher_counts if c == min_count]
        
        # ランダムに選択
        selected = random.choice(candidates)
        
        # 選択履歴を更新
        self.selection_history[(subject.name, selected.name)] += 1
        
        self.logger.debug(
            f"5組 {subject.name} 教師選択（均等）: {selected.name} "
            f"(選択回数: {min_count + 1})"
        )
        
        return selected
    
    def _get_current_ratios(self, subject_name: str, teachers: List[Teacher]) -> str:
        """現在の選択比率を文字列で返す"""
        total = sum(self.selection_history[(subject_name, t.name)] for t in teachers)
        if total == 0:
            return "未選択"
        
        ratios = []
        for teacher in teachers:
            count = self.selection_history[(subject_name, teacher.name)]
            ratio = count / total
            ratios.append(f"{teacher.name}:{ratio:.2%}")
        
        return ", ".join(ratios)
    
    def get_selection_report(self) -> Dict:
        """選択履歴のレポートを取得"""
        report = {
            "summary": {},
            "details": defaultdict(dict)
        }
        
        # 科目ごとに集計
        subject_totals = defaultdict(int)
        for (subject, teacher), count in self.selection_history.items():
            subject_totals[subject] += count
            report["details"][subject][teacher] = count
        
        # サマリー作成
        for subject, teachers in report["details"].items():
            total = subject_totals[subject]
            report["summary"][subject] = {
                "total_selections": total,
                "teacher_ratios": {}
            }
            
            for teacher, count in teachers.items():
                ratio = count / total if total > 0 else 0
                report["summary"][subject]["teacher_ratios"][teacher] = {
                    "count": count,
                    "ratio": ratio
                }
        
        return report
    
    def reset_history(self):
        """選択履歴をリセット"""
        self.selection_history.clear()
        self.logger.info("5組教師選択履歴をリセットしました")