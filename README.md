# 時間割自動生成システム v5

日本の中学校向けの時間割自動生成システムです。高度な制約充足問題（CSP）アプローチを使用して、複雑な制約条件を満たす最適な時間割を生成します。

## バージョン 3.0の新機能

- **高度なCSPアルゴリズムがデフォルト**: バックトラッキングと局所探索による最適化
- **1ステップで完全な時間割を生成**: `python3 main.py generate`コマンドだけで空きコマのない時間割を作成
- **整理されたディレクトリ構造**: スクリプトファイルを用途別に分類
- **パフォーマンスの向上**: 不要なファイルを削除し、コードベースを最適化
- **統合ロギングシステム**: 一元化されたログ設定で出力を制御

## ディレクトリ構造

```
timetable_v5/
├── main.py                  # メインエントリーポイント
├── check_violations.py      # 制約違反チェック（→scripts/analysis/）
├── fill_empty_slots.py      # 空きコマ埋め（→scripts/utilities/）
├── setup.py                # パッケージセットアップ
├── requirements.txt         # 本番環境の依存関係
├── requirements-dev.txt     # 開発環境の依存関係
├── README.md               # このファイル
├── CLAUDE.md               # Claude Code用ドキュメント
├── .gitignore              # Git除外設定
│
├── src/                    # ソースコード（クリーンアーキテクチャ）
│   ├── application/       # アプリケーション層
│   │   ├── services/     # アプリケーションサービス
│   │   └── use_cases/    # ユースケース
│   ├── domain/           # ドメイン層
│   │   ├── constraints/  # 制約実装
│   │   ├── entities/     # エンティティ
│   │   ├── services/     # ドメインサービス
│   │   └── value_objects/# 値オブジェクト
│   ├── infrastructure/   # インフラ層
│   │   ├── config/       # 設定
│   │   ├── parsers/      # パーサー
│   │   └── repositories/ # リポジトリ
│   └── presentation/     # プレゼンテーション層
│       └── cli/          # CLIインターフェース
│
├── scripts/                # ユーティリティスクリプト
│   ├── analysis/          # 分析スクリプト
│   ├── checks/            # チェックスクリプト
│   ├── fixes/             # 修正スクリプト
│   └── utilities/         # その他のユーティリティ
│
├── data/                   # データファイル
│   ├── config/            # 設定ファイル
│   ├── input/             # 入力ファイル
│   └── output/            # 出力ファイル
│
├── tests/                  # テストコード
└── docs/                   # ドキュメント
```

## インストール

```bash
cd timetable_v5
pip install -r requirements.txt
```

## 使用方法

### 基本的な時間割生成（1ステップで完了）

```bash
# 高度なCSPアルゴリズムで完全な時間割を生成（デフォルト）
python3 main.py generate

# より多くの反復で最適化
python3 main.py generate --max-iterations 200

# レガシーアルゴリズムを使用
python3 main.py generate --use-legacy

# カスタムパラメータで生成
python3 main.py generate \
  --max-iterations 300 \
  --use-random \
  --randomness-level 0.5

```

**注意**: `python3 main.py generate`を実行すると、常に空きコマも埋められた完全な時間割が生成されます。

### 補助ツール


#### 制約違反をチェック

```bash
python3 check_violations.py
```

### その他のスクリプト

分析スクリプト:
```bash
python3 scripts/analysis/comprehensive_analysis.py
python3 scripts/analysis/check_jiritsu_violations.py
```

修正スクリプト:
```bash
python3 scripts/fixes/fix_gym_violations.py
python3 scripts/fixes/fix_jiritsu_constraints.py
```

## 主な制約

### CRITICAL（必須制約）
- 教員重複制約: 同一教員が同時刻に複数クラスを担当不可
- 月曜6校時固定制約: 全クラス「欠」
- 教師不在制約: 不在教員の授業割り当て禁止
- 体育館使用制約: 同時刻に体育は1クラスのみ

### HIGH（重要制約）
- 5組同一教科制約: 1-5, 2-5, 3-5は同時刻に同教科
- 交流学級同期制約: 交流学級と親学級の連携
- 会議ロック制約: 会議時間帯の教員確保

### 自立活動制約
交流学級（支援学級）が自立活動を行う時、親学級は数学または英語の授業を実施する必要があります。

## 生成オプション

### 基本オプション
- `--max-iterations`: 最大反復回数（デフォルト: 100）
- `--soft-constraints`: ソフト制約も適用
- `--use-random`: ランダム性を導入
- `--randomness-level`: ランダム性レベル 0.0-1.0（デフォルト: 0.3）
- `--start-empty`: 空の時間割から開始（input.csvを無視）
- `--use-legacy`: レガシーアルゴリズムを使用

### 拡張オプション
- `--optimize-meeting-times`: 会議時間の最適化を有効化
- `--optimize-gym-usage`: 体育館使用の最適化を有効化
- `--optimize-workload`: 教師の負担バランスを最適化
- `--use-support-hours`: 5組の時数表記（5支、16支等）を使用
- `--enable-all-optimizations`: すべての最適化機能を有効化

### ログ制御オプション
- `--verbose` / `-v`: 詳細なログを出力
- `--quiet` / `-q`: 警告以上のログのみ出力

## データファイル

### 入力ファイル
- `data/config/base_timetable.csv`: 標準時数定義
- `data/input/input.csv`: 初期時間割（オプション）
- `data/input/Follow-up.csv`: 週次要望・教員不在情報

### 出力ファイル
- `data/output/output.csv`: 生成された時間割

## トラブルシューティング

問題が発生した場合:
1. `check_violations.py`で制約違反を確認
2. 必要に応じて`scripts/fixes/`内の修正スクリプトを実行
3. ログファイルで詳細を確認

## ライセンス

内部使用のみ