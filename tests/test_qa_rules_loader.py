"""QARulesLoaderのテスト"""
import pytest
from pathlib import Path
from src.infrastructure.config.qa_rules_loader import QARulesLoader


class TestQARulesLoader:
    """QARulesLoaderのテストクラス"""
    
    def test_load_rules(self, tmp_path):
        """ルール読み込みのテスト"""
        # テスト用のQA.txtを作成
        qa_content = """# 📚 時間割生成システム - Q&Aマネジメント

## 📌 恒久的ルール（常に適用）

### 🏫 各クラスの担任教師（2025-06-21追加）
**通常学級**：
- 1年1組：金子ひ先生
- 1年2組：井野口先生
- 2年1組：塚本先生

### 🕐 非常勤教師の勤務時間（2025-06-21追加）
**青井先生（美術）**：
- 水曜：2、3、4校時
- 木曜：1、2、3校時

### 🏢 定例会議の詳細（2025-06-21追加）
**企画会議**：
- 時間：火曜3限
- 参加者：校長、教頭、青井、児玉、吉村

**HF会議**：
- 時間：火曜4限
- 参加者：校長、教頭、青井、児玉、吉村

### 👨‍🏫 教師の役職（2025-06-21追加）
- 青井先生：企画委員、3年主任
- 児玉先生：企画委員、生徒指導主任

### 📅 教師の定期的な不在（2025-06-21追加）
**毎週の終日不在**：
- 月曜：井野口先生
- 金曜：校長、森山先生

### ⏰ 6限目の学年別詳細ルール（2025-06-21追加）
**3年生（通常学級：3-1、3-2、3-3）**：
- 月曜6限：通常授業可能
- 火曜6限：通常授業可能
- 金曜6限：YT（特別活動）

**1・2年生、交流学級、5組**：
- 月曜6限：欠（欠課）
- 火曜6限：YT（特別活動）
- 金曜6限：YT（特別活動）

### 📊 標準授業時数（週あたり）（2025-06-21追加）
**主要5教科**：
- 国語：4時間
- 数学：3時間

### 📚 教科配置の優先順位（2025-06-21追加）
**空きスロットを埋める際の優先順位**：
1. 主要教科（算、国、理、社、英、数）を最優先

### 🎯 5組の国語教師割り当てルール（2025-06-21追加）
- 理想的には週全体で寺田先生と金子み先生の比率を1:1に近づける
"""
        
        qa_file = tmp_path / "QA.txt"
        qa_file.write_text(qa_content, encoding='utf-8')
        
        # ローダーを初期化
        loader = QARulesLoader(str(qa_file))
        
        # 担任教師のテスト
        assert loader.get_homeroom_teacher('1年1組') == '金子ひ'
        assert loader.get_homeroom_teacher('1年2組') == '井野口'
        assert loader.get_homeroom_teacher('2年1組') == '塚本'
        assert loader.get_homeroom_teacher('3年1組') is None  # 記載なし
        
        # 非常勤教師の勤務時間のテスト
        aoi_slots = loader.get_part_time_slots('青井')
        assert ('水', 2) in aoi_slots
        assert ('水', 3) in aoi_slots
        assert ('水', 4) in aoi_slots
        assert ('木', 1) in aoi_slots
        assert ('木', 2) in aoi_slots
        assert ('木', 3) in aoi_slots
        assert ('月', 1) not in aoi_slots  # 月曜は勤務不可
        
        # 会議情報のテスト
        enterprise_meeting = loader.get_meeting_info('enterprise')
        assert enterprise_meeting['day'] == '火'
        assert enterprise_meeting['period'] == 3
        assert '校長' in enterprise_meeting['participants']
        assert '青井' in enterprise_meeting['participants']
        
        # 教師の役職のテスト
        aoi_roles = loader.get_teacher_roles('青井')
        assert '企画委員' in aoi_roles
        assert '3年主任' in aoi_roles
        
        # 定期的な不在のテスト
        monday_absences = loader.get_regular_absences('月')
        assert '井野口' in monday_absences
        friday_absences = loader.get_regular_absences('金')
        assert '校長' in friday_absences
        assert '森山' in friday_absences
        
        # 6限目ルールのテスト
        assert loader.get_6th_period_rule(3, '月') == 'normal'
        assert loader.get_6th_period_rule(3, '火') == 'normal'
        assert loader.get_6th_period_rule(3, '金') == 'YT'
        assert loader.get_6th_period_rule(1, '月') == '欠'
        assert loader.get_6th_period_rule(1, '火') == 'YT'
        assert loader.get_6th_period_rule(2, '月') == '欠'
        
        # 標準時数のテスト
        assert loader.get_standard_hours('国語') == 4
        assert loader.get_standard_hours('数学') == 3
        
        # 教科優先順位のテスト
        priorities = loader.get_subject_priorities()
        assert '算' in priorities
        assert '国' in priorities
        assert '理' in priorities
        assert '社' in priorities
        assert '英' in priorities
        assert '数' in priorities
        
        # 教師比率のテスト
        assert loader.get_teacher_ratio('国', '寺田') == 0.5
        assert loader.get_teacher_ratio('国', '金子み') == 0.5
    
    def test_missing_file(self):
        """ファイルが存在しない場合のテスト"""
        loader = QARulesLoader('/non/existent/path/QA.txt')
        
        # ルールは空になるはず
        assert loader.rules == {}
        
        # 各メソッドはデフォルト値を返すはず
        assert loader.get_homeroom_teacher('1年1組') is None
        assert loader.get_part_time_slots('青井') == []
        assert loader.get_meeting_info('enterprise') == {}
        assert loader.get_teacher_roles('青井') == []
        assert loader.get_regular_absences('月') == []
        assert loader.get_6th_period_rule(1, '月') == ''
        assert loader.get_standard_hours('国語') == 0
        assert loader.get_subject_priorities() == []
        assert loader.get_grade5_preferred_teachers() == []
        assert loader.get_teacher_ratio('国', '寺田') == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])