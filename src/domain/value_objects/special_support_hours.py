"""特別支援学級（5組）の時数表記管理システム（統合版）"""
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
import logging


@dataclass(frozen=True)
class SpecialSupportHour:
    """特別支援学級の時数表記"""
    hour_code: str  # 例: "5支", "16支", "26支"
    subject_name: str  # 元の教科名
    teacher_name: Optional[str] = None
    
    def __str__(self):
        return self.hour_code


@dataclass(frozen=True)
class Grade5SupportHour:
    """5組の時数表記（後方互換性のため維持）"""
    hour_code: str
    subject_name: str
    teacher_name: Optional[str] = None
    
    def __str__(self):
        return self.hour_code


class SpecialSupportHourMapping:
    """5組の時数表記マッピング管理（統合版）
    
    このクラスは以下の機能を統合:
    - SpecialSupportHourMapping（基本版）
    - SpecialSupportHourMappingEnhanced（強化版）
    - Grade5SupportHourSystem（5組特化版）
    """
    
    def __init__(self, enhanced_mode: bool = True):
        self.logger = logging.getLogger(__name__)
        self.enhanced_mode = enhanced_mode
        
        if enhanced_mode:
            self._init_enhanced()
        else:
            self._init_basic()
        
        # 5組固有のパターン（Grade5SupportHourSystemから統合）
        self._init_grade5_patterns()
    
    def _init_basic(self):
        """基本的な初期化（旧SpecialSupportHourMapping）"""
        # 時数コードと教科の対応表
        self._hour_mappings: Dict[str, List[str]] = {
            "5支": ["音", "理", "社", "英", "数"],  # 基礎教科
            "16支": ["道", "YT"],  # 特定の固定時間
            "26支": ["国", "英"],  # 複数教科対応
            "27支": ["保", "美", "家"],  # 実技系
            "31支": ["数", "理"],  # 理数系
            "32支": ["社", "技"],  # 社会・技術系
            "33支": ["英", "国"],  # 言語系
            "37支": ["家", "音", "美"],  # 芸術・実技系
        }
        
        # 基礎教科の時数
        self._basic_subject_hours = ["5支"]
        
        # 時間割での配置パターン（曜日・時限）
        self._placement_patterns: Dict[Tuple[str, int], str] = {
            ("月", 5): "27支",
            ("火", 1): "5支",
            ("水", 5): "27支",
            ("木", 6): "16支",
            ("金", 3): "27支",
        }
    
    def _init_enhanced(self):
        """強化版の初期化（旧SpecialSupportHourMappingEnhanced）"""
        # 詳細なマッピング情報
        self._hour_mappings_enhanced: Dict[str, Dict] = {
            "5支": {
                "subjects": ["音", "理", "社", "英", "数", "国"],
                "teacher": None,
                "priority": 1,
                "preferred_periods": [1, 2, 3, 4],
            },
            "16支": {
                "subjects": ["道", "YT", "総"],
                "teacher": None,
                "priority": 2,
                "preferred_periods": [6],
            },
            "26支": {
                "subjects": ["国", "英", "音", "理"],
                "teacher": None,
                "priority": 3,
                "preferred_periods": [2, 3, 5],
            },
            "27支": {
                "subjects": ["保", "美", "家", "技"],
                "teacher": None,
                "priority": 3,
                "preferred_periods": [3, 5],
            },
            "31支": {
                "subjects": ["数", "理", "英"],
                "teacher": None,
                "priority": 4,
                "preferred_periods": [4, 5],
            },
            "32支": {
                "subjects": ["社", "技", "家"],
                "teacher": None,
                "priority": 4,
                "preferred_periods": [3, 4],
            },
            "33支": {
                "subjects": ["英", "国", "社", "理"],
                "teacher": None,
                "priority": 4,
                "preferred_periods": [2, 4, 5],
            },
            "37支": {
                "subjects": ["家", "音", "美", "技"],
                "teacher": None,
                "priority": 4,
                "preferred_periods": [2, 3],
            },
        }
        
        # 基本版との互換性のため
        self._hour_mappings = {
            code: info["subjects"] 
            for code, info in self._hour_mappings_enhanced.items()
        }
        self._basic_subject_hours = ["5支"]
        
        # 詳細な配置パターン
        self._placement_patterns_list: Dict[Tuple[str, int], List[str]] = {
            # 月曜日
            ("月", 1): ["5支", "31支"],
            ("月", 2): ["5支", "26支", "33支"],
            ("月", 3): ["5支", "27支"],
            ("月", 4): ["5支", "31支"],
            ("月", 5): ["27支"],
            # 火曜日
            ("火", 1): ["5支"],
            ("火", 2): ["26支", "33支"],
            ("火", 3): ["27支", "32支"],
            ("火", 4): ["5支", "33支"],
            ("火", 5): ["37支"],
            ("火", 6): ["16支"],
            # 水曜日
            ("水", 1): ["5支"],
            ("水", 2): ["26支", "31支"],
            ("水", 3): ["5支", "32支"],
            ("水", 4): ["26支", "33支"],
            ("水", 5): ["27支", "31支"],
            ("水", 6): ["16支"],
            # 木曜日
            ("木", 1): ["5支", "作業"],
            ("木", 2): ["26支", "33支"],
            ("木", 3): ["31支", "32支"],
            ("木", 4): ["16支"],
            ("木", 5): ["5支", "31支"],
            ("木", 6): ["27支", "37支"],
            # 金曜日
            ("金", 1): ["5支"],
            ("金", 2): ["5支", "31支"],
            ("金", 3): ["27支", "37支"],
            ("金", 4): ["5支", "33支"],
            ("金", 5): ["26支", "33支"],
            ("金", 6): ["16支"],
        }
        
        # 教科別の優先時数コード
        self._subject_preference: Dict[str, List[str]] = {
            "音": ["5支", "37支", "26支"],
            "理": ["5支", "31支", "33支"],
            "社": ["5支", "32支", "33支"],
            "英": ["5支", "33支", "26支", "31支"],
            "数": ["5支", "31支"],
            "国": ["5支", "26支", "33支"],
            "保": ["27支"],
            "美": ["27支", "37支"],
            "家": ["27支", "37支", "32支"],
            "技": ["27支", "37支", "32支"],
            "道": ["16支"],
            "YT": ["16支"],
            "総": ["16支"],
        }
    
    def _init_grade5_patterns(self):
        """5組固有のパターンを初期化（旧Grade5SupportHourSystem）"""
        # 学年・曜日・時限ごとの具体的な時数コード
        self._actual_patterns: Dict[Tuple[int, str, int], str] = {
            # 1年5組のパターン
            (1, "月", 1): "日生",
            (1, "月", 2): "国",
            (1, "月", 3): "数",
            (1, "月", 4): "社",
            (1, "月", 5): "27支",
            (1, "月", 6): "欠",
            (1, "火", 1): "5支",
            (1, "火", 2): "音",
            (1, "火", 3): "数",
            (1, "火", 4): "英",
            (1, "火", 5): "技",
            (1, "火", 6): "YT",
            (1, "水", 1): "5支",
            (1, "水", 2): "数",
            (1, "水", 3): "英",
            (1, "水", 4): "国",
            (1, "水", 5): "27支",
            (1, "水", 6): "YT",
            (1, "木", 1): "作業",
            (1, "木", 2): "国",
            (1, "木", 3): "数",
            (1, "木", 4): "道",
            (1, "木", 5): "理",
            (1, "木", 6): "27支",
            (1, "金", 1): "5支",
            (1, "金", 2): "理",
            (1, "金", 3): "27支",
            (1, "金", 4): "英",
            (1, "金", 5): "国",
            (1, "金", 6): "YT",
            # 2年5組（1年と同じパターン）
            (2, "月", 1): "日生",
            (2, "月", 2): "国",
            (2, "月", 3): "数",
            (2, "月", 4): "社",
            (2, "月", 5): "27支",
            (2, "月", 6): "欠",
            (2, "火", 1): "5支",
            (2, "火", 2): "音",
            (2, "火", 3): "数",
            (2, "火", 4): "英",
            (2, "火", 5): "技",
            (2, "火", 6): "YT",
            (2, "水", 1): "5支",
            (2, "水", 2): "数",
            (2, "水", 3): "英",
            (2, "水", 4): "国",
            (2, "水", 5): "27支",
            (2, "水", 6): "YT",
            (2, "木", 1): "作業",
            (2, "木", 2): "国",
            (2, "木", 3): "数",
            (2, "木", 4): "道",
            (2, "木", 5): "理",
            (2, "木", 6): "27支",
            (2, "金", 1): "5支",
            (2, "金", 2): "理",
            (2, "金", 3): "27支",
            (2, "金", 4): "英",
            (2, "金", 5): "国",
            (2, "金", 6): "YT",
            # 3年5組（同じパターン）
            (3, "月", 1): "日生",
            (3, "月", 2): "国",
            (3, "月", 3): "数",
            (3, "月", 4): "社",
            (3, "月", 5): "27支",
            (3, "月", 6): "欠",
            (3, "火", 1): "5支",
            (3, "火", 2): "音",
            (3, "火", 3): "数",
            (3, "火", 4): "英",
            (3, "火", 5): "技",
            (3, "火", 6): "YT",
            (3, "水", 1): "5支",
            (3, "水", 2): "数",
            (3, "水", 3): "英",
            (3, "水", 4): "国",
            (3, "水", 5): "27支",
            (3, "水", 6): "YT",
            (3, "木", 1): "作業",
            (3, "木", 2): "国",
            (3, "木", 3): "数",
            (3, "木", 4): "道",
            (3, "木", 5): "理",
            (3, "木", 6): "27支",
            (3, "金", 1): "5支",
            (3, "金", 2): "理",
            (3, "金", 3): "27支",
            (3, "金", 4): "英",
            (3, "金", 5): "国",
            (3, "金", 6): "YT",
        }
        
        # 時数コードの意味
        self._hour_code_meanings = {
            "5支": "特別支援基礎",
            "16支": "道徳・総合的な学習",
            "26支": "言語・コミュニケーション",
            "27支": "実技・作業",
            "31支": "理数系",
            "32支": "社会・技術",
            "33支": "英語・国語",
            "37支": "芸術・実技",
        }
    
    def get_hour_code(self, subject: str, day: str, period: int, 
                      teacher: Optional[str] = None,
                      existing_codes: Optional[Set[str]] = None) -> str:
        """教科名から時数コードを取得（統合版）"""
        if self.enhanced_mode:
            return self._get_hour_code_enhanced(subject, day, period, teacher, existing_codes)
        else:
            return self._get_hour_code_basic(subject, day, period, teacher)
    
    def _get_hour_code_basic(self, subject: str, day: str, period: int, 
                            teacher: Optional[str] = None) -> str:
        """基本的な時数コード取得（旧SpecialSupportHourMapping）"""
        # 基礎教科の場合は5支を優先
        if subject in ["音", "理", "社", "英", "数"]:
            return "5支"
        
        # 配置パターンに基づく判定
        pattern_key = (day, period)
        if pattern_key in self._placement_patterns:
            pattern_hour = self._placement_patterns[pattern_key]
            # パターンの時数に該当教科が含まれているか確認
            if subject in self._hour_mappings.get(pattern_hour, []):
                return pattern_hour
        
        # 教科名から適切な時数コードを検索
        for hour_code, subjects in self._hour_mappings.items():
            if subject in subjects:
                # 5支は基礎教科専用
                if hour_code == "5支" and subject not in ["音", "理", "社", "英", "数"]:
                    continue
                return hour_code
        
        # デフォルトは31支（汎用）
        return "31支"
    
    def _get_hour_code_enhanced(self, subject: str, day: str, period: int, 
                               teacher: Optional[str] = None,
                               existing_codes: Optional[Set[str]] = None) -> str:
        """強化版の時数コード取得（旧SpecialSupportHourMappingEnhanced）"""
        # 特別な教科はそのまま
        if subject in ["欠", "日生", "自立", "作業"]:
            return subject
        
        # 基礎教科の場合は5支を優先
        if subject in self._hour_mappings_enhanced["5支"]["subjects"]:
            return "5支"
        
        # 配置パターンから候補を取得
        pattern_key = (day, period)
        pattern_codes = self._placement_patterns_list.get(pattern_key, [])
        
        # 教科の優先順位から候補を取得
        subject_codes = self._subject_preference.get(subject, [])
        
        # パターンと教科の両方に含まれるコードを優先
        for code in subject_codes:
            if code in pattern_codes:
                # 既存のコードとの重複を避ける
                if existing_codes and code in existing_codes:
                    continue
                # 対応する教科リストに含まれているか確認
                if subject in self._hour_mappings_enhanced.get(code, {}).get("subjects", []):
                    return code
        
        # パターンのみから選択
        for code in pattern_codes:
            if subject in self._hour_mappings_enhanced.get(code, {}).get("subjects", []):
                if not existing_codes or code not in existing_codes:
                    return code
        
        # 教科の優先順位のみから選択
        for code in subject_codes:
            if not existing_codes or code not in existing_codes:
                return code
        
        # デフォルト判定
        if subject in ["道", "YT", "総"]:
            return "16支"
        elif subject in ["保", "美", "家", "技"]:
            return "27支"
        elif subject in ["数", "理"]:
            return "31支"
        elif subject in ["英", "国"]:
            return "33支"
        else:
            return "31支"  # 汎用
    
    def get_teacher_for_hour(self, hour_code: str) -> Optional[str]:
        """時数コードから担当教師を取得"""
        if self.enhanced_mode:
            mapping = self._hour_mappings_enhanced.get(hour_code, {})
            return mapping.get("teacher")
        else:
            # 5支は特定の教師なし
            if hour_code in self._basic_subject_hours:
                return None
            return None
    
    def is_valid_placement(self, hour_code: str, day: str, period: int) -> bool:
        """配置の妥当性をチェック"""
        pattern_key = (day, period)
        
        if self.enhanced_mode:
            if pattern_key in self._placement_patterns_list:
                return hour_code in self._placement_patterns_list[pattern_key]
            
            # 一般的な制約
            mapping = self._hour_mappings_enhanced.get(hour_code, {})
            preferred = mapping.get("preferred_periods", [])
            if preferred:
                return period in preferred
        else:
            if pattern_key in self._placement_patterns:
                return self._placement_patterns[pattern_key] == hour_code
            
            # 一般的な制約
            if hour_code == "16支" and period != 6:
                return False
        
        return True
    
    def get_subjects_for_hour(self, hour_code: str) -> List[str]:
        """時数コードに対応する教科リストを取得"""
        if self.enhanced_mode:
            mapping = self._hour_mappings_enhanced.get(hour_code, {})
            return mapping.get("subjects", [])
        else:
            return self._hour_mappings.get(hour_code, [])
    
    # Grade5SupportHourSystemとの互換性メソッド
    def get_grade5_assignment(self, grade: int, day: str, period: int) -> str:
        """5組の時間割を取得（理想の結果に基づく）"""
        key = (grade, day, period)
        return self._actual_patterns.get(key, "")
    
    def is_support_hour(self, assignment: str) -> bool:
        """時数表記かどうか判定"""
        return "支" in assignment
    
    def get_original_subject(self, hour_code: str) -> Optional[str]:
        """時数コードから元の教科を推測"""
        hour_to_subject = {
            "5支": "自立",
            "27支": "保",
            "16支": "道",
            "26支": "国",
            "31支": "数",
            "32支": "社",
            "33支": "英",
            "37支": "美",
        }
        return hour_to_subject.get(hour_code)
    
    def should_use_support_hour(self, class_ref, subject: str, day: str, period: int) -> bool:
        """5組で時数表記を使用すべきか判定"""
        if class_ref.class_number != 5:
            return False
        
        # 特別な教科はそのまま表示
        if subject in ["日生", "自立", "作業", "道", "YT", "欠"]:
            return False
        
        # 理想の結果でその時間が時数表記になっているかチェック
        pattern = self.get_grade5_assignment(class_ref.grade, day, period)
        return self.is_support_hour(pattern)
    
    def get_support_hour_code(self, class_ref, subject: str, day: str, period: int) -> str:
        """適切な時数コードを取得"""
        if not self.should_use_support_hour(class_ref, subject, day, period):
            return subject
        
        # 理想の結果から時数コードを取得
        pattern = self.get_grade5_assignment(class_ref.grade, day, period)
        if self.is_support_hour(pattern):
            return pattern
        
        # デフォルトの時数コード割り当て
        default_mapping = {
            "音": "5支",
            "理": "5支",
            "社": "5支",
            "英": "5支",
            "数": "5支",
            "国": "5支",
            "保": "27支",
            "美": "27支",
            "家": "27支",
            "技": "27支",
        }
        
        return default_mapping.get(subject, "31支")
    
    def optimize_hour_distribution(self, assignments: Dict[Tuple[str, int], str]) -> Dict[str, int]:
        """時数配分を最適化して統計を返す（強化版のみ）"""
        if not self.enhanced_mode:
            self.logger.warning("optimize_hour_distribution is only available in enhanced mode")
            return {}
        
        hour_counts = {}
        for (day, period), hour_code in assignments.items():
            if hour_code in self._hour_mappings_enhanced:
                hour_counts[hour_code] = hour_counts.get(hour_code, 0) + 1
        
        # 理想的な配分（週あたり）
        ideal_distribution = {
            "5支": 10,
            "16支": 3,
            "26支": 4,
            "27支": 6,
            "31支": 4,
            "32支": 3,
            "33支": 4,
            "37支": 3,
        }
        
        # 偏差を計算
        deviations = {}
        for code, ideal in ideal_distribution.items():
            actual = hour_counts.get(code, 0)
            deviations[code] = actual - ideal
        
        self.logger.info(f"時数配分: {hour_counts}")
        self.logger.info(f"理想との偏差: {deviations}")
        
        return hour_counts


# 後方互換性のためのエイリアス
SpecialSupportHourMappingEnhanced = SpecialSupportHourMapping
Grade5SupportHourSystem = SpecialSupportHourMapping