
"""教師の重複を解消するサービス"""
import pandas as pd
from typing import List, Tuple, Dict, Set
from ....shared.mixins.logging_mixin import LoggingMixin

class TeacherConflictResolverService(LoggingMixin):
    """教師の重複競合を解消するサービス"""

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df.copy()
        self.fixes: List[str] = []
        self.teacher_mapping = self._load_teacher_mapping()

    def _load_teacher_mapping(self) -> Dict[Tuple[str, str], str]:
        """教師と教科のマッピングを読み込む"""
        try:
            from ....infrastructure.config.path_config import path_config
            from ....shared.utils.csv_operations import CSVOperations
            mapping_file = path_config.config_dir / "teacher_subject_mapping.csv"
            rows = CSVOperations().read_csv(mapping_file)
            mapping = {}
            if rows is not None and not rows.empty:
                for _, row in rows.iterrows():
                    key = (row['学年'], row['教科'])
                    mapping[key] = row['教員名']
            return mapping
        except Exception as e:
            self.logger.error(f"教師マッピングの読み込みに失敗: {e}")
            return {}

    def resolve_conflicts(self) -> Tuple[pd.DataFrame, List[str]]:
        """すべての教師の重複を解消する"""
        conflicts = self._find_conflicts()
        self.logger.info(f"発見された教師の重複: {len(conflicts)}件")

        for (teacher, time_slot), classes in conflicts.items():
            self.logger.info(f"競合解消中: {teacher}先生, {time_slot}, クラス: {classes}")
            self._resolve_conflict(teacher, time_slot, classes)

        return self.df, self.fixes

    def _find_conflicts(self) -> Dict[Tuple[str, str], List[str]]:
        """教師の重複を見つける"""
        teacher_schedule: Dict[Tuple[str, str], List[str]] = {}
        
        for day_idx, day in enumerate(["月", "火", "水", "木", "金"]):
            for period in range(1, 7):
                time_slot = f"{day}{period}"
                col_idx = day_idx * 6 + period
                
                for _, row in self.df.iterrows():
                    class_name = row[0]
                    subject = row[col_idx]
                    
                    if pd.isna(subject) or subject == "":
                        continue

                    grade = class_name.split('年')[0]
                    teacher = self.teacher_mapping.get((grade, subject))

                    if not teacher:
                        continue

                    key = (teacher, time_slot)
                    if key not in teacher_schedule:
                        teacher_schedule[key] = []
                    teacher_schedule[key].append(class_name)

        return {k: v for k, v in teacher_schedule.items() if len(v) > 1}

    def _resolve_conflict(self, teacher: str, time_slot: str, classes: List[str]):
        """個別の競合を解消する"""
        # 1つのクラスを残し、残りを移動する
        class_to_keep = classes[0]
        classes_to_move = classes[1:]

        for class_to_move in classes_to_move:
            subject = self._get_subject(class_to_move, time_slot)
            if not subject:
                continue

            # 移動先の空きスロットを探す
            empty_slot = self._find_empty_slot(teacher, class_to_move)
            if empty_slot:
                # 授業を移動
                self._move_class(class_to_move, time_slot, empty_slot, subject)
                self.fixes.append(f"{teacher}先生の {time_slot} の {class_to_move} ({subject}) を {empty_slot} に移動しました。")
            else:
                self.logger.warning(f"{teacher}先生の {class_to_move} ({subject}) を移動できる空きスロットが見つかりませんでした。")

    def _get_subject(self, class_name: str, time_slot: str) -> str:
        """指定されたクラスと時間枠の教科を取得"""
        day = time_slot[0]
        period = int(time_slot[1])
        day_idx = ["月", "火", "水", "木", "金"].index(day)
        col_idx = day_idx * 6 + period
        
        class_row = self.df[self.df[0] == class_name]
        if not class_row.empty:
            return class_row.iloc[0, col_idx]
        return ""

    def _find_empty_slot(self, teacher: str, class_name: str) -> str:
        """指定された教師とクラスの空きスロットを探す"""
        for day_idx, day in enumerate(["月", "火", "水", "木", "金"]):
            for period in range(1, 7):
                time_slot = f"{day}{period}"
                col_idx = day_idx * 6 + period
                
                class_row = self.df[self.df[0] == class_name]
                if not class_row.empty and pd.isna(class_row.iloc[0, col_idx]):
                    if self._is_teacher_free(teacher, time_slot):
                        return time_slot
        return ""

    def _is_teacher_free(self, teacher: str, time_slot: str) -> bool:
        """指定された教師がその時間に空いているか"""
        # 現在のスケジュールから、その時間に教師が担当しているクラスを調べる
        day = time_slot[0]
        period = int(time_slot[1])
        day_idx = ["月", "火", "水", "木", "金"].index(day)
        col_idx = day_idx * 6 + period

        for _, row in self.df.iterrows():
            class_name = row[0]
            subject = row[col_idx]
            if pd.isna(subject) or subject == "":
                continue

            grade = class_name.split('年')[0]
            current_teacher = self.teacher_mapping.get((grade, subject))
            if current_teacher == teacher:
                return False # 既に担当している
        return True

    def _move_class(self, class_name: str, from_slot: str, to_slot: str, subject: str):
        """授業を移動する"""
        # 移動元のセルを空にする
        from_day_idx = ["月", "火", "水", "木", "金"].index(from_slot[0])
        from_col_idx = from_day_idx * 6 + int(from_slot[1])
        self.df.loc[self.df[0] == class_name, from_col_idx] = None

        # 移動先のセルに設定
        to_day_idx = ["月", "火", "水", "木", "金"].index(to_slot[0])
        to_col_idx = to_day_idx * 6 + int(to_slot[1])
        self.df.loc[self.df[0] == class_name, to_col_idx] = subject
