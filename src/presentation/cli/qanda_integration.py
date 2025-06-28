"""
QandAシステムのCLI統合
時間割生成の前後でQandAシステムと連携する
"""

import logging
from typing import List, Dict, Optional
from colorama import Fore, Style, init

from ...application.services.qanda_service import ImprovedQandAService as QandAService
from ...application.services.constraint_violation_analyzer import ConstraintViolationAnalyzer
from ...shared.mixins.logging_mixin import LoggingMixin


class QandAIntegration(LoggingMixin):
    """QandAシステムをCLIに統合するクラス"""
    
    def __init__(self):
        super().__init__()
        init(autoreset=True)  # colorama初期化
        self.qanda_service = QandAService()
        self.violation_analyzer = ConstraintViolationAnalyzer(self.qanda_service)
    
    def check_unanswered_questions(self) -> bool:
        """
        未回答の質問をチェックし、ユーザーに通知
        
        Returns:
            未回答の質問がある場合True
        """
        unanswered = self.qanda_service.get_unanswered_questions()
        
        if unanswered:
            print(f"\n{Fore.YELLOW}━━━ 未回答の質問があります ━━━{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}QandA/QA.txtに{len(unanswered)}件の未回答質問があります。{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}より良い時間割を生成するために、回答をお願いします。{Style.RESET_ALL}\n")
            
            # 最新の3件を表示
            for i, qa in enumerate(unanswered[:3]):
                print(f"{Fore.CYAN}[{qa['timestamp']}]{Style.RESET_ALL}")
                print(f"Q: {qa['question']}")
                if qa.get('context'):
                    print(f"   Context: {qa['context']}")
                print()
            
            if len(unanswered) > 3:
                print(f"{Fore.YELLOW}他に{len(unanswered) - 3}件の未回答質問があります。{Style.RESET_ALL}")
            
            print(f"\n{Fore.GREEN}回答方法: QandA/QA.txtを開いて、「[回答をここに追加]」の部分に回答を記入してください。{Style.RESET_ALL}")
            return True
        
        return False
    
    def display_learned_rules(self) -> None:
        """学習済みのルールを表示"""
        rules = self.qanda_service.apply_learned_rules()
        
        total_rules = sum(len(r) for r in rules.values())
        if total_rules > 0:
            print(f"\n{Fore.GREEN}━━━ 学習済みルール ━━━{Style.RESET_ALL}")
            print(f"{Fore.GREEN}システムは{total_rules}個のルールを学習しています。{Style.RESET_ALL}\n")
            
            # カテゴリー別に表示
            if rules['teacher_rules']:
                print(f"{Fore.CYAN}教師配置ルール ({len(rules['teacher_rules'])}件):{Style.RESET_ALL}")
                for rule in rules['teacher_rules'][:2]:  # 最初の2件のみ表示
                    print(f"  • {rule['rule'][:80]}...")
                print()
            
            if rules['subject_rules']:
                print(f"{Fore.CYAN}科目配置ルール ({len(rules['subject_rules'])}件):{Style.RESET_ALL}")
                for rule in rules['subject_rules'][:2]:
                    print(f"  • {rule['rule'][:80]}...")
                print()
            
            if rules['constraint_rules']:
                print(f"{Fore.CYAN}制約ルール ({len(rules['constraint_rules'])}件):{Style.RESET_ALL}")
                for rule in rules['constraint_rules'][:2]:
                    print(f"  • {rule['rule'][:80]}...")
                print()
    
    def analyze_and_generate_questions(self, violations: List) -> Dict[str, any]:
        """
        制約違反を分析し、質問を生成
        
        Args:
            violations: 制約違反のリスト
            
        Returns:
            分析結果
        """
        print(f"\n{Fore.CYAN}━━━ 制約違反の分析 ━━━{Style.RESET_ALL}")
        
        analysis = self.violation_analyzer.analyze_violations(violations)
        
        print(f"総違反数: {analysis['total_violations']}件")
        print(f"\n違反タイプ別:")
        for vtype, vlist in analysis['by_type'].items():
            print(f"  • {vtype}: {len(vlist)}件")
        
        if analysis['questions_generated']:
            print(f"\n{Fore.GREEN}システムが{len(analysis['questions_generated'])}個の質問を生成しました。{Style.RESET_ALL}")
            print(f"{Fore.GREEN}QandA/QA.txtに追加されました。{Style.RESET_ALL}")
            
            # 生成された質問を表示
            for q in analysis['questions_generated'][:2]:  # 最初の2件のみ
                print(f"\n新しい質問:")
                print(f"  {q['text']}")
        
        # 解決策の提案
        suggestions = self.violation_analyzer.suggest_solutions(analysis)
        if suggestions:
            print(f"\n{Fore.YELLOW}━━━ 改善の提案 ━━━{Style.RESET_ALL}")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion}")
        
        return analysis
    
    def pre_generation_check(self) -> None:
        """時間割生成前のチェック"""
        print(f"\n{Fore.BLUE}━━━ QandAシステムチェック ━━━{Style.RESET_ALL}")
        
        # 未回答質問のチェック
        has_unanswered = self.check_unanswered_questions()
        
        # 学習済みルールの表示
        self.display_learned_rules()
        
        if has_unanswered:
            print(f"\n{Fore.YELLOW}注意: 未回答の質問があるため、最適な時間割が生成できない可能性があります。{Style.RESET_ALL}")
    
    def post_generation_analysis(self, violations: List) -> None:
        """時間割生成後の分析"""
        if violations:
            self.analyze_and_generate_questions(violations)
        else:
            print(f"\n{Fore.GREEN}━━━ 完璧な時間割が生成されました！ ━━━{Style.RESET_ALL}")
            print(f"{Fore.GREEN}制約違反はありません。{Style.RESET_ALL}")
    
    def interactive_question_session(self) -> None:
        """対話的な質問セッション（オプション機能）"""
        print(f"\n{Fore.CYAN}━━━ 対話的質問セッション ━━━{Style.RESET_ALL}")
        print("システムに質問したいことがあれば入力してください。")
        print("（終了するには 'exit' と入力）\n")
        
        while True:
            question = input(f"{Fore.CYAN}あなたの質問: {Style.RESET_ALL}")
            if question.lower() in ['exit', 'quit', '終了']:
                break
            
            if question.strip():
                # ユーザーの質問として追加
                self.qanda_service.add_system_question(
                    f"[ユーザー質問] {question}",
                    context="対話セッションから"
                )
                print(f"{Fore.GREEN}質問をQA.txtに追加しました。{Style.RESET_ALL}")
                print("後ほど回答を記入してください。\n")