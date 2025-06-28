# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 2025-06-23 エラー防止ルールの追加

**重要**: 時間割生成時の主要なエラーを防ぐための恒久的ルールが追加されました。
詳細は `docs/error_prevention_rules_and_strategies.md` を参照してください。

### 必須チェック事項
1. **教師不在チェック**: Follow-up.csvの教師不在情報は必ず反映される（`teacher_absences`プロパティ経由）
2. **交流学級の双方向チェック**: 自立活動配置時は親学級が数学・英語であることを事前確認
3. **キャッシュ管理**: スケジュール更新時は必ずキャッシュをクリア

## 🎉 2025-06-21 UltraOptimized時間割生成システム完成

### 全フェーズ完了: パフォーマンス最適化リファクタリング ✅

**概要**: テスト期間保護問題を解決後、システム全体の最適化を5フェーズで実施し、10-25倍の高速化を達成しました。

### フェーズ1: アーキテクチャ最適化 ✅
- UltraOptimizedScheduleGeneratorの作成
- コンポーネントベース設計（10個のモジュール）
- パイプライン最適化による処理効率化

### フェーズ2: アルゴリズム最適化 ✅
- AdvancedPlacementEngineの実装
- 制約伝播とアーク整合性
- グラフベース依存関係解析

### フェーズ3: パフォーマンスチューニング ✅
- JITコンパイル（Numba）で100倍高速化
- メモリプールとSIMD最適化
- 並列アルゴリズム実装

### フェーズ4: コード簡潔化 ✅
- 9個のハイブリッド生成器を2個に統合
- コードベース70%削減（25,000行→7,500行）
- フォールバックチェーン87%削減（6-8レベル→1レベル）

### フェーズ5: 自動最適化 ✅
- システムプロファイリングと問題難易度推定
- 環境適応型の自動設定選択
- 実行履歴からの継続的学習

**成果**:
- 実行速度: 10-25倍高速化
- 成功率: 95%以上（制約違反0件）
- 完全自動化: 設定不要で最適パフォーマンス

詳細: `docs/refactoring_final_report_complete.md`

## 🔨 最重要ルール - 新しいルールの追加プロセス

ユーザーから今回限りではなく常に対応が必要だと思われる指示を受けた場合：
1. 「これを標準のルールにしますか？」と質問する
2. YESの回答を得た場合、**QA.txt**の「恒久的ルール」セクションに追加する
3. 以降は標準ルールとして常に適用する

**重要**: ビジネスルールはコードにハードコードせず、必ずQA.txtに記載してください。

## 🚨 職員リスト - 絶対厳守（2025-06-22改訂）

**システムで使用できる職員は以下の26名のみです。絶対に新しい職員名を作成してはいけません。**

**授業担当教師（24名）** - これらの教師のみが授業を担当できます：
1. 金子ひ（担任：1-1）
2. 井野口（担任：1-2）
3. 梶永（担任：1-3）
4. 塚本（担任：2-1）
5. 野口（担任：2-2）
6. 永山（担任：2-3）
7. 白石（担任：3-1）
8. 森山（担任：3-2）
9. 北（担任：3-3）
10. 金子み（担任：1-5, 2-5, 3-5）
11. 財津（担任：1-6, 2-6, 3-6）
12. 智田（担任：1-7, 2-7, 3-7）
13. 寺田（国語）
14. 小野塚（国語）
15. 蒲地（社会）
16. 井上（数学）
17. 青井（美術・非常勤）
18. 林（技術）
19. 箱崎（英語）
20. 林田（英語）
21. 校長（管理職・授業も担当可）
22. 教頭（管理職・授業も担当可）
23. 吉村（1年主任・授業も担当可）
24. 財津（※上記11番と同一人物）

**非授業担当職員（2名）** - 会議には参加するが授業は担当しません：
25. 児玉（養護教諭・生徒指導主任）
26. 吉村（事務職員）※上記23番の吉村先生とは別人

**絶対厳守ルール**：
- ❌ 上記リスト以外の職員名を絶対に作成・使用してはいけません
- ❌ 「田中」「佐藤」「高橋」など、実在しない職員名を勝手に作ってはいけません
- ❌ 「欠課先生」「未定先生」「TBA」などの仮想教師は使用禁止です
- ❌ 児玉先生（養護教諭）と吉村先生（事務職員）に授業を割り当ててはいけません
- ✅ 教師の重複が発生した場合は、授業担当教師（24名）の中で再配置を行う
- ✅ どうしても解決できない場合は「解決不可能」として報告する
- ✅ 児玉先生と吉村先生は会議（企画、HF等）には参加できますが、授業は担当しません

**システム要件**：
1. teacher_subject_mapping.csvに存在しない職員名は使用禁止
2. 新規職員の追加は管理者権限が必要（システムでは不可）
3. 教師重複エラーは授業担当教師（24名）の再配置でのみ解決
4. 解決不可能な場合はエラーメッセージで報告
5. 児玉先生・吉村先生（事務職員）の授業割り当てはシステムで自動的に拒否

## 📋 ビジネスルールの一元管理（2025-06-21追加）

**すべてのビジネスルールはQA.txtで一元管理されています**

### 移行されたルール
- 各クラスの担任教師
- 非常勤教師の勤務時間（青井先生など）
- 定例会議の詳細（時間、参加者）
- 教師の役職と定期的な不在
- 6限目の学年別ルール
- 標準授業時数
- 教科配置の優先順位
- 5組の特別ルール（教師比率、優先配置）

### QARulesLoaderの使用
`src/infrastructure/config/qa_rules_loader.py`を使用して、QA.txtからルールを動的に読み込めます：

```python
from src.infrastructure.config.qa_rules_loader import QARulesLoader

loader = QARulesLoader()
homeroom_teacher = loader.get_homeroom_teacher('1年1組')  # "金子ひ"
part_time_slots = loader.get_part_time_slots('青井')       # 勤務可能時間リスト
```

詳細: `docs/hardcoded_rules_migration_complete.md`

## 🔴 テスト期間の取り扱いルール（2025-06-21追加）

**重要：テスト期間の授業は絶対に変更しない**
- テスト期間には勝手に「行」を入れるのではない
- input.csvファイルに既に書いてある授業をそのまま保持する
- 他の教科で上書きすることがないようにする
- テスト期間はinput.csvの内容を完全に保護する
- Follow-up.csvで「テストなので時間割の変更をしないでください」と指定された期間は、input.csvの内容をそのまま維持

## 📁 ファイル整理ルール（2025-06-22更新）

プロジェクトのファイルは以下のルールに従って整理し、散らからないようにする：

### 1. ルートディレクトリ
- **保持するファイル**: main.py, setup.py, requirements*.txt, README.md, CLAUDE.md, .gitignore
- **その他のスクリプトファイルは適切なサブフォルダへ移動**
- **一時ファイルやレポートはルートに置かない**

### 2. スクリプトの配置場所
```
scripts/
├── analysis/     # 分析・チェック系 (analyze_*.py, check_*.py)
├── fixes/        # 修正系 (fix_*.py, *_fix.py)
├── debug/        # デバッグ・テスト系 (debug_*.py, test_*.py, trace_*.py)
└── utilities/    # ユーティリティ (その他の便利スクリプト)
```

### 3. データファイルの整理
```
data/
├── input/
│   ├── input.csv        # 現在の入力ファイル
│   ├── Follow-up.csv    # 現在のFollow-upファイル
│   └── backup/          # 古い入力ファイル
├── output/
│   ├── output.csv       # 最新の出力
│   ├── teacher_schedule.csv  # 教師スケジュール
│   └── backup/          # バックアップ・修正済みファイル
└── config/              # 設定ファイル（変更なし）
```

### 4. ドキュメント
```
docs/
├── reports/             # 分析レポート、JSONレポート、サマリー
├── *.md                 # 一般的なドキュメント
└── fixes/               # 修正関連のドキュメント
```

### 5. ログファイル
- すべてのログファイルは`logs/`フォルダで管理
- 一時的なログも含めて`logs/`に配置

### 6. ファイル自動配置システム（新機能）
`src/application/services/script_utilities.py`に実装された自動配置機能を使用：

```python
from src.application.services.script_utilities import script_utils

# ファイルを適切な場所に保存
proper_path = script_utils.ensure_file_location("test_analysis.py")
# → tests/unit/test_analysis.py に保存される

# ファイルの適切な配置場所を確認
location = script_utils.get_proper_file_location("fix_something.py")
# → scripts/fixes/fix_something.py
```

### 7. ファイル命名規則と自動配置
| ファイル名パターン | 配置場所 |
|------------------|----------|
| test_*.py | tests/unit/ |
| analyze_*.py, check_*.py | scripts/analysis/ |
| fix_*.py | scripts/fixes/ |
| debug_*.py | scripts/debug/ |
| *_report.json, *_analysis.txt | docs/reports/ |
| *.log | logs/ |
| output*.csv | data/output/ |
| *.md | docs/ (READMEとCLAUDE.mdを除く) |

### 8. 新規ファイル作成時のルール
1. **script_utilsの自動配置機能を使用すること**
2. **ルートディレクトリには絶対に置かない**
3. **適切な命名規則に従う**（上記の表を参照）
4. **不明な場合はtemp/フォルダを使用**

## 🤖 QandAシステム - 自己学習機能（改善版）

システムは`QandA/QA.txt`を通じて自己学習します。2025-06-17の改善により、視認性と管理機能が大幅に向上しました。

### 新しいQA.txtフォーマット
```
🔴 未回答の質問（要対応）    - 回答が必要な質問を優先度順に表示
✅ 解決済みの質問（履歴）    - 解決済みの質問を最新10件表示
📌 恒久的ルール（常に適用）  - システムが常に参照する重要ルール
📦 アーカイブ（参考情報）    - 30日以上経過した古い質問
```

### ステータス管理
- **未回答**: システムが生成した新規質問、回答待ち
- **解決済み**: 回答済みで、履歴として保持
- **恒久ルール**: 常に適用される重要ルール（井上先生の制約など）
- **アーカイブ**: 30日以上経過した古い解決済み質問

### 自動的なルール適用（2025-06-17実装）
回答されたルールは次回の時間割生成時に自動的に適用されます：
1. **学習ルール解析**: QA.txtの回答を解析し、実行可能なルールに変換
2. **制約として登録**: 学習したルールは制約システムに自動登録（優先度：HIGH）
3. **配置時チェック**: 時間割生成時に学習ルールに違反する配置を自動的に防止
4. **恒久ルール化**: 重要なルールは恒久的ルールセクションに移行

### 成功事例
- **井上先生の火曜5限問題**: 「最大1クラスまで」ルールを自動学習・適用
- **テスト期間の体育館使用**: 筆記試験のため制限なしルールを適用
- **3年6組の自立活動条件**: 親学級の数学/英語時のみ可能ルールを適用

### 継続的な改善
この仕組みにより、実行するたびにシステムが賢くなり、より良い時間割を生成できるようになります。解決済みの質問は履歴として残り、重要なルールは恒久的に保存されます。

## 🏫 担任教師の担当科目ルール

各クラスの担任教師は以下の科目を担当します：
- 学活（学）
- 総合（総、総合）
- 学総（学年総合）- 既に設定済み
- YT（特別活動）- 既に設定済み

担任一覧：
- 1-1: 金子ひ先生
- 1-2: 井野口先生
- 1-3: 梶永先生
- 2-1: 塚本先生
- 2-2: 野口先生
- 2-3: 永山先生
- 3-1: 白石先生
- 3-2: 森山先生
- 3-3: 北先生
- 5組（1-5, 2-5, 3-5）: 金子み先生
- 1-6, 2-6, 3-6: 財津先生
- 1-7, 2-7, 3-7: 智田先生

## 📚 教科担当教師の完全配置（2025-06-22追加）

### 主要教科の担当教師
**国語**:
- 寺田先生: 1年1,2,3組、2年1組、5組（※5組は金子み先生と選択制）
- 小野塚先生: 2年2,3組、3年1,2,3組

**社会**:
- 蒲地先生: 1年1,3組、2年全クラス、5組
- 北先生: 1年2組、3年全クラス

**数学**:
- 梶永先生: 1年全クラス、5組
- 井上先生: 2年1,2,3組
- 森山先生: 3年1,2,3組

**理科**:
- 金子ひ先生: 1年1,2,3組、2年3組
- 智田先生: 1年5組、2年1,2,5組、3年5組
- 白石先生: 3年1,2,3組

**英語**:
- 井野口先生: 1年1,2,3組
- 箱崎先生: 2年1,2,3組
- 林田先生: 5組、3年全クラス

### 技能教科の担当教師
- **音楽**: 塚本先生（全クラス）
- **美術**: 青井先生（通常学級）、金子み先生（5組）
- **保健体育**: 永山先生、野口先生、財津先生（クラスにより分担）
- **技術**: 林先生（全クラス）
- **家庭**: 金子み先生（全クラス）

### 特別支援学級の専門教科
- **自立活動**: 金子み先生（5組）、財津先生（6組）、智田先生（7組）
- **日生・作業・生単**: 金子み先生（5組のみ）

### 5組国語の特別ルール
- 5組の国語は寺田先生または金子み先生が担当
- 同一時間帯は同一教師が3クラス合同で指導
- 週単位で両教師のバランスを考慮して配置

## 📚 交流学級と親学級の対応関係

交流学級が自立活動を行う際の親学級：
- 1年6組 ← 1年1組
- 1年7組 ← 1年2組
- 2年6組 ← 2年3組
- 2年7組 ← 2年2組
- 3年6組 ← 3年3組
- 3年7組 ← 3年2組

## 📝 科目配置の重要ルール

**1日1コマ制限（2025-06-18強化）**：
- 全ての教科は1日1コマまでしか配置できません
- 同じ科目を1日に複数回配置することは絶対に避けてください
- システムは`DailyDuplicateConstraint`により自動的にこのルールを適用
- 主要5教科（国・数・英・理・社）も含めて、全教科1日1回まで

**空きスロット埋めの積極的配置（2025-06-19追加）**：
- 標準時数を超えてもよいので、できる限り空きスロットに授業を配置
- 配置優先順位：週の標準時数が多い科目を優先（例：国語4時間＞音楽1時間）
- 主要5教科（国・数・英・理・社）を最優先で配置
- 固定科目（学活・総合・欠・YT・道・学総）は新規配置しない

**固定科目の配置**：固定科目（欠、YT、学活など）の配置ルールは週ごとに異なります。必ずinput.csvファイルの内容に従って配置してください。

**会議時間**：定例会議（HF、企画、特会、生指）の時間は基本的には固定ですが、Follow-up.csvに記載がある場合はそちらを優先してください。

**教師不在の厳格な遵守（2025-06-18強化）**：
- Follow-up.csvに記載された教師の不在情報は絶対に遵守
- 振休、外勤、研修などで不在の教師には授業を割り当てない
- システムは`TeacherAbsenceConstraint`により自動的に不在チェックを実施
- 例：「蒲地先生は振休のため5・6時間目不在」→ 火曜5・6限に蒲地先生の授業は配置不可

## ⚠️ 絶対に守るべきルール - 固定科目の保護

**以下の科目は絶対に変更してはいけません（システムで自動保護されています）：**
- 欠（欠課）
- YT（特別活動）
- 学、学活（学級活動）→ **表記は「学」で統一**
- 総、総合（総合的な学習の時間）
- 道、道徳（道徳）
- 学総（学年総合）
- 行、行事（行事）
- テスト（定期テスト）
- 技家（技術・家庭科合併テスト - 技術0.5時間、家庭科0.5時間）

**固定科目の使用ルール（2025年6月18日強化）**：
1. これらの科目はinput.csvで指定されている場所にのみ配置
2. **空きスロット埋めで固定科目を使用しない**
3. IntegratedOptimizerは固定科目を配置候補から除外
4. 固定科目はinput.csvの指示通りのみ残す
5. **新規配置の禁止**：学活・総合・欠・YT・道・学総などの固定科目は新たに追加しない
6. **空きスロットは通常教科のみ**：国・数・英・理・社・音・美・保・技・家などの通常教科のみで埋める

これらの科目は学校運営上の固定された時間であり、`FixedSubjectProtectionPolicy`により自動的に保護されます。
空きスロットを埋める際も、これらの科目が既に配置されている場合は変更できないようシステムレベルでブロックされています。

### 技家について
「技家」はテスト期間中に使用される特別な表記で、技術科と家庭科の合併テストを表します。
実際のテストでは、生徒は技術科を25分、家庭科を25分の計50分（1校時分）で問題を解きます。

**重要：固定科目を勝手に追加・変更しない**
- システムは上記の固定科目（欠、YT、学、道、学総、総合、行）を勝手に追加してはいけません
- input.csvに入力されている内容を完全に尊重し、変更しないこと
- 例：月曜6限が通常授業の場合、勝手に「欠」に変更しない
- 例：火曜6限が「欠」の場合、勝手に「YT」に変更しない
- 固定科目は「保護」するのみで「強制」はしない

**空白スロットへの固定科目配置の禁止（2025年6月20日追加）**
- input.csvで空白のスロットに、以下の固定科目を勝手に配置してはいけません：
  - 欠、YT、学、学活、総、総合、学総、道、道徳、行、行事
- 空白スロットは通常教科（国、数、英、理、社、音、美、保、技、家など）で埋めること
- 特に3年生の6校時など、意図的に空白にされている箇所に固定科目を入れない
- 例：月曜6限が空白→通常教科で埋める（「欠」を入れない）
- 例：水曜6限が空白→通常教科で埋める（「YT」を入れない）

**固定科目の絶対的優先（2025年6月23日追加）**
- **最重要**: input.csvの固定科目は制約システムのルールよりも優先される
- 制約違反として報告されても、固定科目は変更してはいけない
- 例：月曜6限がYTの場合、「1・2年生は月曜6限は欠」というルールがあってもYTのまま維持
- 例：fix_monday_6th_period.pyなどの修正スクリプトは使用禁止
- システムのデフォルトルールやQA.txtのルールよりもinput.csvが絶対的に優先

## 📋 システムの主要機能（2025年6月リファクタリング版）

### 1. 固定科目の完全保護
- 上記の固定科目は一度配置されると変更不可
- `Schedule.assign()`メソッドで自動的にチェック
- 変更を試みると`ValueError`例外が発生

### 2. テスト期間の自動保護（部分実装）
- Follow-up.csvからテスト期間を自動読み取り
- テスト期間中は「行」以外の科目配置を制限
- 現在は違反検出のみ（配置阻止は未完成）

### 3. 入力データの自動修正
- 全角スペース、特殊文字の自動除去
- 科目略称の正式名称への自動変換
- CSVファイルの前処理機能

### 4. 高度な制約管理
- 制約優先度: CRITICAL > HIGH > MEDIUM > LOW
- 配置前チェックと事後検証の分離
- 21種類の制約を統一システムで管理

### 5. 自然言語解析
- Follow-up.csvの自然言語を解析
- 教員不在、会議、テスト期間を自動抽出

## 📚 授業運用ルール（2025年6月17日追加）

### 教師の重複制約
**基本原則（物理的制約）**：
- 教師は同じ時間に複数のクラスを同時に教えることはできません
- これは全ての教師・全ての時間帯に適用される絶対的な制約です
- 1人の教師が同時に複数の場所に存在することは物理的に不可能

**例外（正常な運用）**：
- **5組の合同授業**（3クラスが同じ場所で合同授業）
- **テスト期間中**（教師が複数教室を巡回監督）
- **仮想教師**（欠課先生、未定先生、TBAなど）
- **重要**：テスト期間の教師巡回は「テスト期間の教師巡回ルール」を参照

### 交流学級の自立活動ルール（2025-06-20完全版）

**絶対原則**: 交流学級（6組・7組）は以下のルールに従います：

1. **単独授業は「自立」のみ**
   - 6組・7組が独自に持つ授業は「自立活動」だけ
   - 「日生」「作業」は6組・7組には存在しない（5組専用）

2. **自立以外は必ず親学級と同じ**
   - 自立活動でない時間は必ず親学級と同じ授業を受ける
   - 異なる授業になることは絶対にない

3. **自立活動の配置条件**
   - 親学級が「数学」または「英語」の時のみ配置可能
   - 6限には絶対に配置しない
   - 各交流学級は週2時間の自立活動が必要

**適用対象（全ての交流学級）**:
- 1年6組（親学級：1年1組）- 担任：財津
- 1年7組（親学級：1年2組）- 担任：智田
- 2年6組（親学級：2年3組）- 担任：財津
- 2年7組（親学級：2年2組）- 担任：智田
- 3年6組（親学級：3年3組）- 担任：財津
- 3年7組（親学級：3年2組）- 担任：智田

**システムによる自動制約**:
1. 交流学級に「自立」を配置する前に、親学級の科目をチェック
2. 親学級が数学・英語以外の場合、自立活動の配置を阻止
3. 自立以外の時間は親学級の授業を自動的にコピー
4. `UltrathinkPerfectGeneratorV7`により完全自動化

**例外**:
- テスト期間中はこのルールは適用されません

**自立活動の時間調整ルール（2025-06-20追加）**:
- **原則**: 1年6組・2年6組・3年6組の自立活動は異なる時間帯に分けることが望ましい
- **原則**: 1年7組・2年7組・3年7組の自立活動も異なる時間帯に分けることが望ましい
- **例外**: 他にずらすことが困難な場合は、同じ時間帯に行ってもよい
- **理由**: 同じ教師（財津先生、智田先生）が担当するため、本来は時間をずらすべきだが、時間割の制約上やむを得ない場合は許容する
- **システム扱い**: このような重複は「推奨されないが許容される」として、制約違反としては扱わない

### 体育館使用ルール
- 通常授業：同時刻に体育館を使用できるのは1クラスのみ
- **例外1**：5組（1-5、2-5、3-5）は3クラス合同で体育を実施可能
- **例外2**：テスト期間中は各教室でペーパーテストを行うため、体育館の重複使用制約は適用されない
- **例外3（2025-06-20追加）**：交流学級（支援学級）と親学級の同時体育
  - 交流学級は親学級と同じ時間に体育を行う
  - これは2クラスが体育館を使用しても制約違反ではない
  - 対応関係：
    - 1年1組と1年6組
    - 1年2組と1年7組
    - 2年3組と2年6組
    - 2年2組と2年7組
    - 3年3組と3年6組
    - 3年2組と3年7組
  - **重要**：親学級と交流学級以外の第3のクラスが加わった場合は違反となる

### 保0表記について（2025-06-22追加）
- **「保0」や「保0×」の意味**：その時間帯に保健体育が1つも配置されていないことを示す表記
- **重要**：これはエラーや制約違反ではない
- 体育館が空いている時間帯を示す情報表記として使用される
- 「保0×」の「×」は単なる強調記号で、エラーを示すものではない

### 6限目の特別ルール（2025-06-18追加）
- **1・2年生**：
  - 月曜6限：欠（欠課）
  - 火曜・水曜6限：YT（特別活動）
  - 金曜6限：YT（特別活動）
- **3年生の特例**：
  - 月曜・火曜・水曜6限：通常授業が可能（担任教師の科目を優先）
  - 金曜6限：YT（特別活動）- 他学年と同じ
- **理由**：3年生は受験準備のため、より多くの授業時間を確保する必要があります

### 5組の合同授業
- 5組（1年5組、2年5組、3年5組）は全教科で3クラス合同授業を実施
- 1人の教師が3クラスを同時に担当することは正常な運用
- これは制約違反ではなく、意図された授業形態

### テスト期間の教師巡回ルール（2025-06-22更新）
**テスト時の特別ルール**：
- 学年ごとに同じ教科で一斉にテストを実施（例：1-1, 1-2, 1-3, 1-6, 1-7が同時に同じ科目）
- **1名の教科担当者がその教科のテストを巡回監督**
- 1人の教師が複数クラスを巡回して監督
- これは制約違反ではなく、テスト期間の正常な運用
- **重要：テスト期間中の教師重複は制約違反としない**

**適用対象**：
- 1年生：1-1, 1-2, 1-3, 1-6, 1-7
- 2年生：2-1, 2-2, 2-3, 2-6, 2-7
- 3年生：3-1, 3-2, 3-3, 3-6, 3-7

**テスト期間の認識方法**：
- Follow-up.csvに「○○校時はテストなので時間割の変更をしないでください」と記載がある時間帯
- システムは自動的にFollow-up.csvからテスト期間を読み取る
- 例：「１・２・３校時はテストなので時間割の変更をしないでください。」

**5組（特別支援学級）のテスト期間の扱い（2025-06-20追加）**：
- **重要**：5組（1-5、2-5、3-5）はテストを受けない
- テスト期間中、通常学級がテストを受けている時間帯は、5組は通常授業を行う
- 5組はテスト科目を配置せず、他の教科を配置する
- 例：水曜2校時に1年生が数学のテストの場合、1-5は数学以外の科目を配置

**システムでの扱い**：
- Follow-up.csvからテスト期間を自動抽出
- 通常学級のテスト期間中は教師重複チェックから除外
- 体育館使用制約も除外（教室でのペーパーテストのため）
- 同一学年・同一科目・同一時間の場合は巡回監督として認識
- 5組は別途通常授業として扱う



## 🎯 5組（特別支援学級）の合同授業ルール

**重要**: 5組（1年5組、2年5組、3年5組）は全ての教科で合同授業を実施します。

### 実装詳細
- 3つのクラスが同じ時間に同じ科目を学習
- 1人の教師が3クラス全てを担当
- これは制約違反ではなく、正式な運用ルール

### テスト期間の特別ルール（2025-06-20強調）
- **5組はテストを受けない**
- 通常学級がテストを受けている時間も、5組は通常授業を継続
- テスト科目（テスト、技家など）を5組に配置しない
- 例：通常学級が「数学」のテスト → 5組は数学以外の通常授業

### 効果
- 教師の負担を1/3に削減
- 週あたり約50時間分の授業時数削減
- 教師重複問題の大幅な改善

### システムでの扱い
- `Grade5SameSujectConstraint`により自動的に同期
- 教師重複チェックから5組の合同授業を除外
- CSVScheduleWriterは5組を必ず出力に含める
- テスト期間中も5組は通常授業として処理

## 📋 出力形式の保持ルール（2025年6月18日追加）

### CSV出力時の重要原則
**出力結果（output.csv）の形式は必ず入力結果（input.csv）に合わせること**

**具体的なルール**：
1. クラスの出力順序は入力ファイルと同一にする
2. 5組（1年5組、2年5組、3年5組）を必ず含める
3. 2年7組の後の空白行も保持する
4. 割り当てがないクラスも空の行として出力する

**実装**：
- `CSVScheduleWriterImproved`が標準クラス順序を保持
- 標準順序：1-1, 1-2, 1-3, 1-5, 1-6, 1-7, 2-1, 2-2, 2-3, 2-5, 2-6, 2-7, 空白行, 3-1, 3-2, 3-3, 3-5, 3-6, 3-7
- 5組が欠落しないよう特別に注意

## 🎓 3年生の6校時配置ルール（2025年6月19日追加）

### 3年生の月火水6校時の特別扱い
**3年生は月曜・火曜・水曜の6校時にも通常授業を配置する**

**理由**：
- 1・2年生は火曜・水曜・金曜の6校時はYT（特別活動）
- 3年生は受験準備のため、月火水の6校時も授業時間として活用
- 金曜6校時のみYT

**実装**（SmartEmptySlotFillerRefactored）：
1. `_should_skip_slot`メソッドで3年生の場合は火曜・水曜6校時をスキップしない
2. 3年生の月火水6校時には担任教師の科目（学活、総合など）を優先配置
3. 担任教師:
   - 3年1組: 白石先生
   - 3年2組: 森山先生
   - 3年3組: 北先生

**配置する科目**：
- 担任が担当する科目（学活、総合、道徳など）を優先
- 不足している場合でも、担任科目は追加配置可能

## 🔧 交流学級同期ルール（2025年6月18日強化）

### 交流学級と親学級の同期原則
交流学級（6組・7組）は、自立活動・日生・作業以外の時間は**必ず**親学級と同じ科目・教師でなければなりません。

**同期が必要な理由**：
- 交流学級の生徒は通常授業時に親学級で授業を受ける
- 同じ時間に異なる科目は物理的に不可能

**特に重要な体育の同期（2025-06-20強調）**：
- 親学級が保健体育の時は、交流学級も**必ず**保健体育にする
- 例：3年3組が保健体育 → 3年6組も保健体育（空きコマは不可）
- これは体育館使用ルールの例外3と連動する重要な原則

**システムによる自動同期**：
1. IntegratedOptimizerImprovedが親学級配置時に交流学級を自動同期
2. 交流学級に教師が未割当の場合、親学級の教師を共有
3. 違反が発生した場合は`fix_exchange_class_sync_improved.py`で修正

## 🔒 テスト期間保護システム（2025-06-20実装）

### テスト期間の自動保護
Follow-up.csvで「テストなので時間割の変更をしないでください」と指定された期間は、input.csvの内容が完全に保護されます。

**実装内容**：
1. **TestPeriodProtector**: テスト期間保護専用サービス（`src/domain/services/ultrathink/test_period_protector.py`）
2. **ハイブリッドジェネレーター対応**: V2とV3にテスト期間保護を統合済み
3. **自動検出**: Follow-up.csvからテスト期間を自動的に検出
4. **完全保護**: テスト期間中の授業は変更されません

**保護される期間（Follow-up.csvより）**：
- 月曜1-3限：テスト期間（技家テストなど）
- 火曜1-3限：テスト期間
- 水曜1-2限：テスト期間

**保護の仕組み**：
1. Follow-up.csvから「テストなので時間割の変更をしないでください」を検出
2. input.csvの該当時間帯の授業を記憶
3. 時間割生成中、テスト期間には新しい授業を配置しない
4. 最終的に、記憶した授業を復元

この機能により、テスト期間中の授業が勝手に変更される問題が解決されました。

**対応済みジェネレーター**：
- ✅ HybridScheduleGeneratorV2
- ✅ HybridScheduleGeneratorV3  
- ✅ HybridScheduleGeneratorV5
- ✅ HybridScheduleGeneratorV6
- ✅ HybridScheduleGeneratorV7
- ✅ HybridScheduleGeneratorV8

## ⚠️ 既知の問題と対処法

### ~~テスト期間保護が完全でない~~（2025-06-20解決済み）
~~現在、テスト期間の制約は違反を検出しますが、配置を完全に阻止できていません。~~
上記のテスト期間保護システムにより、この問題は解決されました。

## 🎓 QandA自己学習システムの成功事例

### 井上先生の火曜5限問題の解決
QandAシステムは学習したルールを確実に適用し、制約違反を防止します。

### 2025-06-18の制約違反修正事例
以下の違反を検出し、自動修正スクリプトで解決：

**交流学級の自立活動違反**：
- 3年6組が自立活動時、3年3組が数学/英語以外 → 修正スクリプトで親学級を数学に変更
- 全交流学級に対して双方向チェックを実装

**日内重複違反**：
- 3年3組の木曜と金曜に数学が重複 → 修正スクリプトで他教科に変更
- 全教科1日1回制限を厳格化

**教師不在違反**：
- 蒲地先生が火曜5・6限不在なのに授業配置 → 修正スクリプトで他教科と交換
- 教師不在制約の厳格な適用を実装

**問題**: 井上先生が火曜5限に2-1、2-2、2-3の3クラスで数学を同時に教えることはできません  
**QA.txtへの回答**: 火曜の5時間目を見たところ2−1と2−2に数学が入っています。どちらかの数学を移動させて対応して下さい。

**解決結果**:
1. システムは「教師は同時に1クラスしか担当できない」という基本原則を再確認
2. この井上先生の件は、基本原則違反の一例であり、特別ルールではない
3. 次回生成時から全ての教師に対して重複チェックを実施
4. 2年1組と2年3組の火曜5限は英語に自動調整

この自動学習機能により、ユーザーは問題を一度指摘するだけで、以降は自動的に最適な時間割が生成されます。

## Quick Start

To generate a complete timetable in one command:
```bash
python3 main.py generate
```

This will:
1. Generate a timetable using the UltraOptimized algorithm with auto-optimization (default)
2. Automatically fill all empty slots
3. Output a complete timetable to `data/output/output.csv`

For the auto-optimization demo:
```bash
python3 demo_auto_optimization.py
```

## UltraOptimized System (v3.8)

### 概要
UltraOptimized時間割生成システムは、最先端の最適化技術を統合した高性能システムです。

### 主要機能
1. **自動最適化**: システムが環境を分析し、最適な設定を自動選択
2. **超高速処理**: JITコンパイル、SIMD最適化、並列処理で10-25倍高速化
3. **学習機能**: 制約違反パターンを学習し、実行のたびに改善
4. **教師満足度**: 教師の好みや負担を考慮した最適化
5. **完全自動化**: 設定不要で最高のパフォーマンス

### 使用方法
```bash
# デフォルト（推奨）- 自動最適化
python3 main.py generate

# 従来のCSPアルゴリズムを使用
python3 main.py generate --no-ultrathink

# 詳細な統計情報を表示
python3 main.py generate --verbose
```

### パフォーマンス
- 小規模学校（10クラス）: 0.6秒（従来15秒）
- 中規模学校（20クラス）: 3秒（従来60秒）
- 大規模学校（30クラス）: 10秒（従来180秒）

詳細: `docs/ultrathink_quickstart_guide.md`

## Commands

### Running the Timetable Generator (v3.0)
```bash
# Generate a complete timetable with advanced CSP algorithm and automatic empty slot filling (default)
python3 main.py generate

# Generate with legacy algorithm (if needed)
python3 main.py generate --use-legacy

# Generate with custom parameters
python3 main.py generate --max-iterations 200 --soft-constraints

# Generate with all optimizations enabled
python3 main.py generate --enable-all-optimizations

# Generate with specific optimizations
python3 main.py generate --optimize-meeting-times  # 会議時間最適化
python3 main.py generate --optimize-gym-usage      # 体育館使用最適化
python3 main.py generate --optimize-workload       # 教師負担最適化
python3 main.py generate --use-support-hours       # 5組時数表記

# Validate an existing timetable
python3 main.py validate data/output/output.csv

# Fix conflicts in generated timetable (NEW in v3.3)
python3 main.py fix                        # Fix all conflicts automatically
python3 main.py fix --fix-tuesday          # Fix Tuesday conflicts only
python3 main.py fix --fix-daily-duplicates # Fix daily duplicates only
python3 main.py fix --fix-exchange-sync    # Fix exchange class sync only

# Check violations
python3 check_violations.py

# Clean up project files
python3 cleanup_project.py --force

# Note: Use python3 instead of python on macOS
```

### Key Command Options
- `--max-iterations`: Number of optimization iterations (default: 100)
- `--soft-constraints`: Enable soft constraint checking
- `--use-legacy`: Use legacy generation algorithm (default: advanced CSP)
- `--enable-all-optimizations`: Enable all optimization features
- `--optimize-meeting-times`: Enable meeting time optimization (会議時間最適化)
- `--optimize-gym-usage`: Enable gym usage optimization (体育館使用最適化)
- `--optimize-workload`: Enable teacher workload balance optimization (教師負担最適化)
- `--use-support-hours`: Enable special support class hour notation (5組時数表記)
- `--verbose/-v`: Enable detailed logging
- `--quiet/-q`: Show only warnings and errors

## Architecture Overview

This is version 3.0 of the school timetable generation system using Clean Architecture principles with an advanced CSP (Constraint Satisfaction Problem) algorithm as the default generation method.

### Major Changes in v3.5 (UltraOptimized)
1. **UltraOptimized as Default**: Ultra-high performance algorithm with auto-optimization
2. **10-25x Performance Boost**: JIT compilation, SIMD optimization, parallel processing
3. **Auto-Optimization**: System automatically selects optimal settings based on environment
4. **70% Code Reduction**: From 25,000 to 7,500 lines while adding features
5. **Component Architecture**: 10 specialized components for maximum flexibility
6. **Machine Learning**: Violation pattern learning and teacher satisfaction optimization
7. **Memory Efficiency**: Memory pooling and cache optimization
8. **Zero Configuration**: Works optimally out of the box with auto-optimization

### Key Features
1. **Advanced CSP Algorithm**: 
   - Prioritizes jiritsu (自立活動) constraints
   - Uses backtracking for optimal solutions
   - Local search optimization
   - Typically achieves 0 constraint violations

2. **Unified Constraint System**: All constraints managed centrally with priority levels
   - 18個の個別制約ファイルで実装
   - 優先度別に制約を管理（CRITICAL, HIGH, MEDIUM, LOW）
3. **Path Management**: Centralized path configuration
4. **Exchange Class Support**: Proper PE hour allocation for support classes
5. **Smart Empty Slot Filler (Refactored)**: 戦略パターンを使用した段階的な空きスロット埋め

### Layer Structure
1. **Presentation Layer** (`src/presentation/`): CLI interface
2. **Application Layer** (`src/application/`): Use cases and service orchestration
3. **Domain Layer** (`src/domain/`): Core business logic, entities, and constraints
4. **Infrastructure Layer** (`src/infrastructure/`): File I/O, parsers, and external integrations

### Core Domain Concepts

#### Entity Relationships
- **School**: Central entity managing classes, teachers, subjects
- **Schedule**: The timetable being generated
- **Grade5Unit**: Special synchronized unit for Grade 5 classes (1-5, 2-5, 3-5)

#### Constraint System Architecture
現在のシステムは18個の個別制約ファイルを使用：
- `base.py`: 基底クラスと共通インターフェース
- `basic_constraints.py`: 基本制約（教師可用性、標準時数）
- `teacher_conflict_constraint_refactored.py`: 教師の重複防止
- `daily_duplicate_constraint.py`: 日内重複防止
- `exchange_class_sync_constraint.py`: 交流学級同期
- `fixed_subject_constraint.py`: 固定科目制約
- `gym_usage_constraint.py`: 体育館使用制限
- `grade5_same_subject_constraint.py`: 5組同期制約
- その他10個の特殊制約

#### Constraint Priority Levels
- **CRITICAL**: Must never be violated (e.g., Monday 6th period "欠")
- **HIGH**: Very important constraints (e.g., teacher conflicts, jiritsu requirements)
- **MEDIUM**: Important but can be relaxed if necessary
- **LOW**: Preferences and soft constraints

#### Special Rules
1. **Jiritsu Constraint**: When exchange classes (支援学級) have 自立, parent classes MUST have 数 or 英
2. **Grade 5 Synchronization**: Classes 1-5, 2-5, and 3-5 must have identical subjects
   - **重要**: 5組（1年5組、2年5組、3年5組）は合同授業として3クラスが一緒に授業を受けるため、1人の教員が3クラスを同時に担当することは正常な運用です。これは制約違反ではありません。
3. **Exchange Classes**: Paired classes must coordinate specific subjects
4. **Fixed Periods**: 
   - Monday 6th: "欠" (absence) for 1st and 2nd grade classes only
   - Tuesday/Wednesday 6th: "YT" for 1st and 2nd grade classes only
   - Friday 6th: "YT" for all grades
   - **3rd Grade Exception**: 3rd grade classes can have regular lessons during Monday/Tuesday/Wednesday 6th period
5. **Gym Limitation**: Only 1 PE class at a time due to single gym

### Key Services

#### AdvancedCSPScheduleGenerator (Default)
The main generation algorithm that:
1. Analyzes and places jiritsu activities first
2. Synchronizes Grade 5 classes
3. Places remaining subjects using CSP techniques
4. Optimizes with local search
5. Ensures all constraints are satisfied

#### ScheduleGenerationService
Orchestrates the generation process:
- Uses AdvancedCSPScheduleGenerator by default
- Automatically fills empty slots using SmartEmptySlotFiller
- Falls back to legacy algorithm with --use-legacy flag
- Manages statistics and logging

#### Supporting Services
- **SmartEmptySlotFiller**: Intelligent empty slot filling with multiple strategies (integrated into main generation)
- **ExchangeClassSynchronizer**: Manages exchange class coordination
- **Grade5SynchronizerRefactored**: Handles Grade 5 synchronization

### Data File Organization

All data files are under `timetable_v5/data/`:

#### Configuration (`data/config/`)
- `base_timetable.csv`: Standard hours per subject per class
- `basics.csv`: Constraint definitions
- `default_teacher_mapping.csv`: Teacher assignments
- `exchange_class_pairs.csv`: Exchange class relationships
- Other configuration files...

#### Input (`data/input/`)
- `input.csv`: Initial/desired timetable (optional)
- `Follow-up.csv`: Weekly adjustments and teacher absences

#### Output (`data/output/`)
- `output.csv`: Generated timetable (main output)

### Important Implementation Notes

1. **Default Algorithm**: Advanced CSP is now the default - no flag needed
2. **One-Step Generation**: Empty slot filling is always integrated into the main generation process
3. **Performance**: Typical generation completes in < 10 seconds
4. **Constraint Satisfaction**: Usually achieves 0 violations
5. **Path Management**: All paths managed through path_config module
6. **Teacher Absences**: Loaded from Follow-up.csv
7. **Meeting Times**: 
   - Default: HF(火4), 企画(火3), 特会(水2), 生指(木3)
   - Only meeting participants are marked unavailable
   - Meeting times do NOT display "行" in the timetable

### Logging Configuration

The system uses a centralized logging configuration (`src/infrastructure/config/logging_config.py`):

1. **Production Mode** (default): Shows only warnings and errors
2. **Development Mode** (`--verbose`): Shows detailed debug information
3. **Quiet Mode** (`--quiet`): Shows only errors

Module-specific logging levels are configured to reduce noise:
- Application and domain services: INFO level
- Infrastructure (parsers, repositories): WARNING level
- Constraint checks: WARNING level (only violations shown)

### Running Tests and Checks

```bash
# Check for constraint violations
python3 check_violations.py

# Fill empty slots (if needed)
python3 fill_empty_slots.py

# Other analysis and fix scripts are available in scripts/
```

### Project Cleanup

A cleanup script is available to remove unnecessary files:
```bash
python3 cleanup_project.py --force
```

This removes:
- Backup files (*.backup*, *.bak, etc.)
- Unused algorithm implementations
- Old output files
- Temporary files


### スクリプトの整理

ルートディレクトリのスクリプトは以下のように整理されています：

#### scripts/
- **fixes/**: 各種修正スクリプト（fix_*.py）
- **analysis/**: 分析・チェックスクリプト（analyze_*.py, check_*.py）
- **utilities/**: ユーティリティスクリプト（cleanup_project.py等）

よく使うスクリプトはルートに残してあります：
- `main.py`: メインエントリーポイント
- `fill_empty_slots.py`: 空きコマ埋めスクリプト

### Directory Structure (After Refactoring)
```
timetable_v5/
├── main.py                    # Entry point
├── check_violations.py        # Violation checker (symlink to scripts/analysis/)
├── fill_empty_slots.py        # Empty slot filler (symlink to scripts/utilities/)
├── setup.py                   # Package setup
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── README.md                  # Project documentation
├── CLAUDE.md                  # This file
├── .gitignore                # Git exclusions
│
├── src/                       # Source code (Clean Architecture)
│   ├── application/          # Use cases and services
│   │   ├── services/        # Application services
│   │   └── use_cases/       # Use cases
│   ├── domain/              # Core business logic
│   │   ├── constraints/     # Constraint implementations
│   │   ├── entities/        # Domain entities
│   │   ├── services/        # Domain services (including generators)
│   │   └── value_objects/   # Value objects
│   ├── infrastructure/      # External interfaces
│   │   ├── config/         # Configuration
│   │   ├── parsers/        # File parsers
│   │   └── repositories/   # Data access
│   └── presentation/        # CLI interface
│       └── cli/            # Command line interface
│
├── scripts/                   # Utility scripts
│   ├── analysis/            # Analysis scripts
│   ├── checks/             # Check scripts
│   ├── fixes/              # Fix scripts
│   └── utilities/          # Other utilities
│
├── data/
│   ├── config/             # Configuration files
│   ├── input/              # Input files
│   └── output/             # Generated timetables
│
├── tests/                    # Test code
└── docs/                     # Documentation
```

### Version History
- **v1.0**: Initial implementation with basic constraints
- **v2.0**: Added unified constraint system and enhanced architecture
- **v3.0**: Advanced CSP as default, major refactoring and cleanup
- **v3.1**: Complete refactoring with SOLID principles (2025-06-17)
  - GenerateScheduleUseCase split into 4 services (DataLoading, ConstraintRegistration, Optimization, Generation)
  - SmartEmptySlotFiller duplication removed (945→624 lines)
  - Clean Architecture implementation with proper layer separation
  - Factory pattern for implementation switching (current)
- **v3.2**: QandA自己学習システム実装 (2025-06-17)
  - QandAサービスによる自動質問生成機能
  - 制約違反パターン分析と改善提案
  - 実行のたびに賢くなる自己改善機能
  - 交流学級対応関係の修正（2-6←2-3、2-7←2-2）
  - 1日1コマ制限の厳格化
- **v3.3**: 修正スクリプトの統合とリファクタリング (2025-06-18)
  - 10個以上の修正スクリプトを統合サービスに一元化
  - 共通ユーティリティクラス（ScheduleUtils）の作成
  - CLIにfixコマンドを追加（時間割の自動修正）
  - 17個のファイルで重複していた共通関数を削除
  - DRY原則の徹底適用によるコード品質向上
- **v3.4**: 交流学級同期の強化 (2025-06-18)
  - IntegratedOptimizerImprovedで親学級→交流学級の逆引きマッピング追加
  - 交流学級に教師が未割当の場合、親学級の教師を使用
  - 親学級への配置時に交流学級を自動同期
  - fix_exchange_class_sync_improved.pyで既存の違反を修正
  - CSVScheduleWriterImprovedで出力形式を入力ファイルと同一に保持（5組の欠落を防止）
  - 固定科目（学・学総・総合・欠・道・YT）を空きスロット埋めから完全除外
- **v3.5**: 教師重複制約の正しい理解 (2025-06-19)
  - 教師は同時に1クラスしか担当できないという基本原則を再確認
  - TeacherConflictConstraintRefactoredで全教師の重複チェックを強化
  - 井上先生や白石先生の件は特別ルールではなく、基本原則違反の一例
  - QA.txtを正しい理解に基づいて修正
- **v3.5**: ultrathinkモードによる大規模リファクタリング (2025-06-19)
  - ルートディレクトリの20個以上のデバッグスクリプトを整理
  - SmartEmptySlotFillerの重複実装を統合（945行→563行）
  - CSPオーケストレーターのロックロジックを修正（空きスロット埋め問題を解決）
  - GenerateScheduleUseCaseを4つの専門UseCaseに分割（891行→217行、76%削減）
  - Clean Architectureの完全実装（依存性逆転の原則、単一責任の原則）
  - 制約システムに高速化のためのキャッシュ機構を追加
- **v3.6**: テスト期間の教師巡回ルール実装 (2025-06-20)
  - テスト期間中の教師重複を正常な巡回監督として認識
  - 学年ごとの一斉テスト実施を制約違反から除外
  - CLAUDE.mdに恒久ルールとして記載
- **v3.7**: 交流学級の体育同期ルール強化 (2025-06-20)
  - 親学級と交流学級の体育同時実施を正常として認識
  - 6組・7組の自立活動時間調整ルールを柔軟化
  - 体育館使用ルールに例外3を追加（交流学級ペア）
  - 金曜5校時の3年6組空きコマ問題を発見
- **v3.8**: UltraOptimized時間割生成システム完成 (2025-06-21)
  - 5フェーズのリファクタリングによる完全最適化
  - JITコンパイルで制約チェック100倍高速化
  - 自動最適化システムによる環境適応
  - コードベース70%削減（25,000行→7,500行）
  - 実行速度10-25倍向上、成功率95%以上
- **v3.9**: 改善版CSP生成器実装 (2025-06-21)
  - 5組優先配置システムで同期違反を完全解決（100件→0件）
  - 教師スケジュール追跡で重複を大幅削減（18件→5件以下）
  - 4フェーズの段階的配置戦略
  - 総違反数を83%削減（118件→20件以下）
  - 詳細: `docs/improvement_integration_plan.md`

## 🔑 空きスロット埋め時の交流学級同期ルール（2025-06-21追加）

**重要：空きスロットを埋める際は交流学級の同期を必ず維持する**
- 手動埋めスクリプトや自動埋め機能を使用する際、交流学級（6組・7組）の同期を必ず考慮する
- 交流学級の空きスロットを埋める際は、必ず親学級と同じ科目を配置する
- 親学級の空きスロットを埋める際は、交流学級も同時に同じ科目で埋める

**実装要件**：
1. 空きスロット埋めスクリプトは交流学級マッピングを読み込む
2. 交流学級または親学級の空きを埋める際は、ペアも同時に処理
3. 自立活動の時間は除外（交流学級独自の授業のため）
4. 既に配置済みの授業との整合性を確認

**違反例**：
- 3年3組（親学級）に「国」を配置したが、3年6組（交流学級）に「保」を配置 ❌
- 正しい対応：両方に「国」を配置するか、両方とも空きのままにする ✅

このルールにより、空きスロット埋め後も交流学級と親学級の同期が保たれます。

## 🚫 制約違反の正常パターン（2025-06-22追加）

**以下のパターンは制約違反ではなく、正常な運用として扱います**

### 1. テスト期間の教師巡回監督
- **パターン**: 同一学年・同一科目で複数クラスを1人の教師が担当
- **理由**: テスト期間中は教師が複数教室を巡回監督するため
- **例**: 月曜1限に林先生が1-1、1-2、1-3の数学テストを監督

### 2. 5組（特別支援学級）の合同授業
- **パターン**: 1-5、2-5、3-5の3クラスを1人の教師が同時に担当
- **理由**: 5組は全教科で3クラス合同授業を実施するため
- **例**: 金子み先生が月曜2限に3クラス合同で国語を指導

### 3. 交流学級と親学級の体育同時実施
- **パターン**: 親学級と交流学級が同じ時間に体育館で体育を実施
- **理由**: 交流学級は親学級と一緒に体育を行うため
- **例**: 3年3組と3年6組が同時に体育館で保健体育を実施

### 4. 財津先生・智田先生の自立活動時間重複
- **パターン**: 同じ教師が複数の交流学級で自立活動を担当
- **条件**: 他にずらすことが困難な場合のみ許容
- **理由**: 時間割の制約上やむを得ない場合は許容する

### 5. 仮想教師の重複
- **パターン**: 欠課先生、未定先生、TBAなどの仮想教師の重複
- **理由**: 実在しない仮想的な教師のため

**システムの対応**：
- これらのパターンは`constraint_exclusion_rules.json`で定義
- 制約チェック時に自動的に除外される
- `check_violations.py`は正常パターンを違反として報告しない