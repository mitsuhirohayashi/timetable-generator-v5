"""
学習ルール適用サービス
QandAシステムから学習したルールを解析し、時間割生成に適用する
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.value_objects.time_slot import TimeSlot
from ...domain.value_objects.assignment import Assignment
from .qanda_service import ImprovedQandAService as QandAService


class LearnedRuleApplicationService:
    """QandAシステムから学習したルールを時間割生成に適用するサービス"""
    
    def __init__(self, qanda_service: Optional[QandAService] = None):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("LearnedRuleApplicationServiceを初期化中")
        self.qanda_service = qanda_service or QandAService()
        self.parsed_rules = []
        self.forbidden_assignments = []  # 禁止する配置のリスト
        
    def parse_and_load_rules(self) -> int:
        """
        QandAシステムから学習したルールを解析してロード
        
        Returns:
            解析されたルール数
        """
        learned_rules = self.qanda_service.apply_learned_rules()
        # ハードコードされたルールを保持するため、リストをクリアしない
        # self.parsed_rules = []
        # self.forbidden_assignments = []
        
        # 制約に関するルールを解析
        for rule_info in learned_rules.get('constraint_rules', []):
            parsed = self._parse_constraint_rule(rule_info)
            if parsed:
                self.parsed_rules.append(parsed)
        
        # 教師に関するルールを解析
        for rule_info in learned_rules.get('teacher_rules', []):
            parsed = self._parse_teacher_rule(rule_info)
            if parsed:
                self.parsed_rules.append(parsed)
        
        self.logger.info(f"学習したルールを{len(self.parsed_rules)}件解析しました")
        return len(self.parsed_rules)
    
    def _parse_constraint_rule(self, rule_info: Dict[str, str]) -> Optional[Dict[str, any]]:
        """制約ルールを解析"""
        question = rule_info['question']
        answer = rule_info['rule']
        
        self.logger.debug(f"制約ルール解析: Q={question[:50]}..., A={answer[:50]}...")
        
        # 教師の同時複数クラス担当問題のパターン
        # パターン1: 「井上先生が火曜5限に2-1, 2-2, 2-3の3クラスで数学を同時に教えることはできません」
        teacher_conflict_pattern1 = r'(.+?)先生?が(.+?)に(.+?)の(\d+)クラスで(.+?)を同時に教える'
        match = re.search(teacher_conflict_pattern1, question)
        
        if not match:
            # パターン2: 「○○先生が○曜○限に○○の3クラス」
            teacher_conflict_pattern2 = r'(.+?)先生?が(.+?)に(.+?)の(\d+)クラス'
            match = re.search(teacher_conflict_pattern2, question)
        
        if match:
            teacher_name = match.group(1).replace('先生', '')
            time_str = match.group(2)
            classes_str = match.group(3)
            subject_from_question = match.group(5) if len(match.groups()) >= 5 else None
            
            self.logger.debug(f"教師重複パターンマッチ: teacher={teacher_name}, time={time_str}, subject={subject_from_question}")
            
            # 時間を解析（例: "火曜5限" -> ("火", 5)）
            day_match = re.search(r'([月火水木金])', time_str)
            period_match = re.search(r'(\d+)限', time_str)
            
            if day_match and period_match:
                day = day_match.group(1)
                period = int(period_match.group(1))
                
                # 回答から具体的な指示を解析
                # 例: "火曜の5時間目を見たところ2−1と2−2に数学が入っています。どちらかの数学を移動させて対応して下さい。"
                if '移動' in answer or '変更' in answer or '教えることはできません' in question:
                    # クラス名を抽出 - 質問と回答の両方から
                    class_pattern = r'(\d[-−]\d)'
                    class_matches_answer = re.findall(class_pattern, answer)
                    class_matches_question = re.findall(class_pattern, classes_str) if classes_str else []
                    
                    # クラスリストを統合
                    all_classes = list(set([c.replace('−', '-') for c in class_matches_answer + class_matches_question]))
                    
                    # 教科を特定（質問から優先、なければ回答から）
                    subject = subject_from_question or self._extract_subject_from_answer(answer)
                    
                    if all_classes:
                        rule = {
                            'type': 'teacher_time_conflict',
                            'teacher': teacher_name,
                            'day': day,
                            'period': period,
                            'affected_classes': all_classes,
                            'action': 'prevent_multiple_assignment',
                            'subject': subject
                        }
                        self.logger.info(f"教師重複ルール解析成功: {rule}")
                        return rule
        
        return None
    
    def _parse_teacher_rule(self, rule_info: Dict[str, str]) -> Optional[Dict[str, any]]:
        """教師ルールを解析"""
        question = rule_info['question']
        answer = rule_info['rule']
        
        # 教師配置調整のパターン
        if '教師配置' in question and '調整' in question:
            teacher_pattern = r'(.+?)先生'
            teacher_match = re.search(teacher_pattern, question)
            
            if teacher_match:
                teacher_name = teacher_match.group(1)
                
                # 時間帯の抽出
                time_pattern = r'([月火水木金])(\d+)限'
                time_match = re.search(time_pattern, question)
                
                if time_match:
                    return {
                        'type': 'teacher_availability',
                        'teacher': teacher_name,
                        'day': time_match.group(1),
                        'period': int(time_match.group(2)),
                        'action': 'restrict_assignment'
                    }
        
        return None
    
    def _extract_subject_from_answer(self, answer: str) -> Optional[str]:
        """回答から科目名を抽出"""
        # 一般的な科目名パターン
        subjects = ['数学', '数', '英語', '英', '国語', '国', '理科', '理', '社会', '社', 
                   '音楽', '音', '美術', '美', '保体', '保', '技術', '技', '家庭', '家']
        
        for subject in subjects:
            if subject in answer:
                return subject
        
        return None
    
    def apply_rules_to_schedule(self, schedule: Schedule, school: School) -> int:
        """
        解析したルールをスケジュールに適用
        
        Args:
            schedule: 時間割
            school: 学校情報
            
        Returns:
            適用されたルール数
        """
        applied_count = 0
        
        for rule in self.parsed_rules:
            if rule['type'] == 'teacher_time_conflict':
                if self._apply_teacher_conflict_rule(rule, schedule, school):
                    applied_count += 1
            elif rule['type'] == 'teacher_availability':
                if self._apply_teacher_availability_rule(rule, schedule, school):
                    applied_count += 1
        
        self.logger.info(f"{applied_count}個のルールを時間割に適用しました")
        return applied_count
    
    def _apply_teacher_conflict_rule(self, rule: Dict[str, any], schedule: Schedule, school: School) -> bool:
        """教師の時間衝突ルールを適用"""
        teacher_name = rule['teacher']
        day = rule['day']
        period = rule['period']
        affected_classes = rule['affected_classes']
        subject = rule['subject']
        
        self.logger.info(f"教師衝突ルール適用開始: {teacher_name}先生 @ {day}{period}限")
        
        # 該当する時間帯の割り当てを確認
        time_slot = TimeSlot(day=day, period=period)
        assignments_at_time = []
        
        # 全クラスから名前で検索
        all_classes = school.get_all_classes()
        for class_name in affected_classes:
            # クラス名の正規化（例：2-1 -> 2年1組）
            if '-' in class_name:
                parts = class_name.split('-')
                full_class_name = f"{parts[0]}年{parts[1]}組"
            else:
                full_class_name = class_name
            
            # full_nameでクラスを検索
            class_obj = None
            for cls in all_classes:
                if cls.full_name == full_class_name:
                    class_obj = cls
                    break
            
            if class_obj:
                assignment = schedule.get_assignment(time_slot, class_obj)
                if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                    assignments_at_time.append((class_obj, assignment))
                    self.logger.debug(f"  - {class_obj.full_name}: {assignment.subject.name} ({assignment.teacher.name}先生)")
        
        self.logger.info(f"同時刻の{teacher_name}先生の授業数: {len(assignments_at_time)}")
        
        # 複数のクラスで同じ教師が同時に教えている場合
        if len(assignments_at_time) > 1:
            # 最初のクラス以外の割り当てを削除
            for i, (class_obj, assignment) in enumerate(assignments_at_time[1:], 1):
                self.logger.info(f"ルール適用: {teacher_name}先生の{day}{period}限の{class_obj.name}での授業を削除")
                schedule.remove_assignment(class_obj, time_slot)
                
                # 削除した授業を別の時間に移動する必要がある場合の処理
                # ここでは禁止リストに追加して、今後の配置で同じ問題が起きないようにする
                self.forbidden_assignments.append({
                    'teacher': teacher_name,
                    'time_slot': time_slot,
                    'max_classes': 1  # 同時に1クラスまで
                })
            
            return True
        else:
            # 今後の配置を防ぐため禁止リストに追加
            self.forbidden_assignments.append({
                'teacher': teacher_name,
                'time_slot': time_slot,
                'max_classes': 1
            })
            self.logger.info(f"{teacher_name}先生の{day}{period}限での複数クラス担当を今後防止するルールを追加")
        
        return False
    
    def _apply_teacher_availability_rule(self, rule: Dict[str, any], schedule: Schedule, school: School) -> bool:
        """教師の利用可能性ルールを適用"""
        teacher_name = rule['teacher']
        day = rule['day']
        period = rule['period']
        
        # 該当する時間帯での教師の配置を制限
        self.forbidden_assignments.append({
            'teacher': teacher_name,
            'time_slot': TimeSlot(day=day, period=period),
            'max_classes': 0  # この時間は配置不可
        })
        
        return True
    
    def is_assignment_allowed(self, teacher_name: str, time_slot: TimeSlot, 
                            current_assignments: List[Assignment]) -> bool:
        """
        学習したルールに基づいて、特定の割り当てが許可されるかチェック
        
        Args:
            teacher_name: 教師名
            time_slot: 時間帯
            current_assignments: 現在の同時刻の割り当てリスト
            
        Returns:
            割り当てが許可される場合True（違反の場合False）
        """
        # 同じ教師の同時刻の割り当て数をカウント
        same_teacher_count = len(current_assignments)
        
        # デバッグ出力
        if time_slot.day == "火" and time_slot.period == 5:
            self.logger.warning(f"学習ルールチェック: {teacher_name}先生 @ {time_slot}, 現在{same_teacher_count}クラス（新配置含む）")
        
        # 禁止ルールをチェック
        for forbidden in self.forbidden_assignments:
            # 教師名のバリエーションを考慮（「先生」付き/なし、「担当」付き）
            forbidden_teacher = forbidden['teacher']
            teacher_matches = (
                forbidden_teacher == teacher_name or 
                forbidden_teacher + '先生' == teacher_name or
                forbidden_teacher == teacher_name.replace('先生', '') or
                forbidden_teacher == teacher_name.replace('担当', '') or
                teacher_name == forbidden_teacher + '担当' or
                forbidden_teacher + '担当' == teacher_name
            )
            
            if (teacher_matches and
                forbidden['time_slot'].day == time_slot.day and
                forbidden['time_slot'].period == time_slot.period
            ):
                max_allowed = forbidden['max_classes']
                
                # デバッグ出力
                if time_slot.day == "火" and time_slot.period == 5:
                    self.logger.warning(f"禁止ルール発見: {forbidden_teacher}先生は{time_slot}に最大{max_allowed}クラスまで")
                
                # 既に上限を超えている場合は追加を許可しない
                # current_assignmentsには新しい配置も含まれているため、既存+新規 > max_allowedで判定
                if same_teacher_count > max_allowed:
                    self.logger.warning(f"学習ルールにより{teacher_name}先生の{time_slot}での配置を拒否 (配置数{same_teacher_count} > 上限{max_allowed})")
                    return False
        
        return True
    
    def get_rule_summary(self) -> Dict[str, any]:
        """適用中のルールのサマリーを取得"""
        summary = {
            'total_rules': len(self.parsed_rules),
            'forbidden_assignments': len(self.forbidden_assignments),
            'rule_types': defaultdict(int)
        }
        
        for rule in self.parsed_rules:
            summary['rule_types'][rule['type']] += 1
        
        return summary
    
