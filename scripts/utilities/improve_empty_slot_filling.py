#!/usr/bin/env python3
"""空きスロット埋めの改善スクリプト

SmartEmptySlotFillerを改良して、教師不在を考慮した
より効果的な空きスロット埋めを実現する
"""

import logging
from pathlib import Path
import shutil
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def improve_smart_empty_slot_filler():
    """SmartEmptySlotFillerの改良"""
    
    file_path = Path("src/domain/services/smart_empty_slot_filler.py")
    if not file_path.exists():
        logger.error("smart_empty_slot_filler.pyが見つかりません")
        return False
    
    # バックアップ作成
    backup_dir = Path("src/domain/services/backup")
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"smart_empty_slot_filler.py.backup_{timestamp}"
    shutil.copy2(file_path, backup_path)
    logger.info(f"バックアップ作成: {backup_path}")
    
    # ファイル読み込み
    content = file_path.read_text(encoding='utf-8')
    
    # 1. _fill_single_slotメソッドの改良（詳細な失敗理由を記録）
    old_fill_single = '''    def _fill_single_slot(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        strategy: FillStrategy,
        check_level: str
    ) -> bool:
        """単一スロットを埋める"""
        # まず交流学級の同期をチェック
        if self.exchange_service.is_exchange_class(class_ref):
            parent_class = self.exchange_service.get_parent_class(class_ref)
            if parent_class:
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                    # 親学級が数学・英語以外なので自立活動は配置できない
                    return False
        
        # 戦略に基づいて配置候補を取得
        subjects = strategy.get_placeable_subjects(schedule, school, time_slot, class_ref)
        
        for subject in subjects:
            teacher = school.get_assigned_teacher(subject, class_ref)
            if not teacher:
                continue
            
            assignment = Assignment(class_ref, subject, teacher)
            can_place, error_msg = self.constraint_validator.can_place_assignment(
                schedule, school, time_slot, assignment, check_level
            )
            
            if can_place:
                try:
                    schedule.assign(time_slot, assignment)
                    self.stats['filled'] += 1
                    self.logger.debug(
                        f"配置成功: {time_slot} {class_ref} - {subject.name} ({teacher.name})"
                    )
                    return True
                except Exception as e:
                    self.logger.debug(f"配置エラー: {str(e)}")
            else:
                # エラーメッセージをカテゴリ分類して統計
                self.stats[f'blocked_by_{self._categorize_error(error_msg)}'] += 1
        
        return False'''
    
    new_fill_single = '''    def _fill_single_slot(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        strategy: FillStrategy,
        check_level: str
    ) -> bool:
        """単一スロットを埋める（改良版：詳細な失敗理由を記録）"""
        slot_id = f"{time_slot.day}{time_slot.period}限 {class_ref}"
        failure_reasons = []
        
        # まず交流学級の同期をチェック
        if self.exchange_service.is_exchange_class(class_ref):
            parent_class = self.exchange_service.get_parent_class(class_ref)
            if parent_class:
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                if parent_assignment and parent_assignment.subject.name not in ["数", "英"]:
                    # 親学級が数学・英語以外なので自立活動は配置できない
                    reason = f"親学級（{parent_class}）が{parent_assignment.subject.name}のため自立活動不可"
                    failure_reasons.append(reason)
                    self.logger.debug(f"{slot_id}: {reason}")
                    return False
        
        # 戦略に基づいて配置候補を取得
        subjects = strategy.get_placeable_subjects(schedule, school, time_slot, class_ref)
        
        if not subjects:
            reason = "配置可能な科目がありません（標準時数達成または固定科目）"
            failure_reasons.append(reason)
            self.logger.info(f"{slot_id}: {reason}")
            self._record_unfilled_slot(slot_id, failure_reasons)
            return False
        
        # 各科目を試行
        subject_attempts = []
        
        for subject in subjects:
            teacher = school.get_assigned_teacher(subject, class_ref)
            if not teacher:
                subject_attempts.append(f"{subject.name}: 担当教師未設定")
                continue
            
            assignment = Assignment(class_ref, subject, teacher)
            can_place, error_msg = self.constraint_validator.can_place_assignment(
                schedule, school, time_slot, assignment, check_level
            )
            
            if can_place:
                try:
                    schedule.assign(time_slot, assignment)
                    self.stats['filled'] += 1
                    self.logger.info(
                        f"配置成功: {slot_id} - {subject.name} ({teacher.name})"
                    )
                    return True
                except Exception as e:
                    subject_attempts.append(f"{subject.name}（{teacher.name}）: 配置エラー - {str(e)}")
            else:
                # エラーメッセージを詳細に記録
                subject_attempts.append(f"{subject.name}（{teacher.name}）: {error_msg}")
                self.stats[f'blocked_by_{self._categorize_error(error_msg)}'] += 1
        
        # 全ての試行が失敗した場合
        failure_reasons.extend(subject_attempts)
        self._record_unfilled_slot(slot_id, failure_reasons)
        
        return False'''
    
    content = content.replace(old_fill_single, new_fill_single)
    
    # 2. 未配置スロット記録メソッドの追加
    if "_record_unfilled_slot" not in content:
        # __init__メソッドに追加
        init_addition = '''        
        # 未配置スロットの詳細記録
        self.unfilled_slots = {}'''
        
        # __init__の最後に追加
        init_pos = content.find("self.stats = defaultdict(int)")
        if init_pos > 0:
            end_pos = content.find("\n", init_pos)
            content = content[:end_pos] + init_addition + content[end_pos:]
        
        # メソッドの追加
        record_method = '''
    
    def _record_unfilled_slot(self, slot_id: str, reasons: List[str]):
        """未配置スロットとその理由を記録"""
        self.unfilled_slots[slot_id] = reasons
    
    def get_unfilled_slots_report(self) -> str:
        """未配置スロットの詳細レポートを生成"""
        if not self.unfilled_slots:
            return "全ての空きスロットが埋まりました。"
        
        report = ["\\n=== 未配置スロットの詳細 ===\\n"]
        
        # 理由別に集計
        reason_counts = defaultdict(int)
        teacher_absence_slots = []
        
        for slot_id, reasons in sorted(self.unfilled_slots.items()):
            report.append(f"\\n{slot_id}:")
            for reason in reasons:
                report.append(f"  - {reason}")
                
                # 教師不在を特別に記録
                if "不在" in reason or "研修" in reason or "年休" in reason:
                    teacher_absence_slots.append((slot_id, reason))
                    reason_counts["教師不在"] += 1
                elif "日内重複" in reason:
                    reason_counts["日内重複制約"] += 1
                elif "標準時数" in reason:
                    reason_counts["標準時数達成"] += 1
                elif "担当教師未設定" in reason:
                    reason_counts["教師未割当"] += 1
                else:
                    reason_counts["その他の制約"] += 1
        
        # サマリー
        report.append("\\n\\n=== サマリー ===")
        report.append(f"未配置スロット総数: {len(self.unfilled_slots)}")
        report.append("\\n理由別内訳:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            report.append(f"  {reason}: {count}件")
        
        # 教師不在による未配置を強調
        if teacher_absence_slots:
            report.append("\\n\\n=== 教師不在による未配置（物理的制約） ===")
            for slot_id, reason in teacher_absence_slots:
                report.append(f"  {slot_id}: {reason}")
        
        return "\\n".join(report)'''
        
        # クラスの最後に追加
        class_end = content.rfind("\n\n")
        if class_end > 0:
            content = content[:class_end] + record_method + content[class_end:]
    
    # 3. fill_empty_slots_smartlyメソッドの最後にレポート出力を追加
    old_end = '''        self.logger.info(f"\\n総計: {total_filled}スロット埋め完了")
        
        return total_filled'''
    
    new_end = '''        self.logger.info(f"\\n総計: {total_filled}スロット埋め完了")
        
        # 未配置スロットのレポートを出力
        report = self.get_unfilled_slots_report()
        if self.unfilled_slots:
            self.logger.warning(report)
        
        return total_filled'''
    
    content = content.replace(old_end, new_end)
    
    # ファイル書き込み
    file_path.write_text(content, encoding='utf-8')
    logger.info("smart_empty_slot_filler.pyを改良しました")
    return True

def main():
    logger.info("=== 空きスロット埋めの改善 ===")
    
    if improve_smart_empty_slot_filler():
        logger.info("\n改善が完了しました。")
        logger.info("次回の時間割生成時から、空きスロットが埋まらなかった詳細な理由が表示されます。")
        logger.info("\n推奨される次のステップ:")
        logger.info("1. python3 main.py generate を実行")
        logger.info("2. 出力される未配置スロットレポートを確認")
        logger.info("3. 教師不在による物理的制約を把握")

if __name__ == "__main__":
    main()