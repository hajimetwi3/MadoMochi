[English](README.md) | 日本語

# MadoMochi（マドモチ）

**いつも窓辺にいる、もちっとした小さな相棒。**
Claude Code とチャットしている間、ウィンドウの入力欄右上あたりで
かわいく反応してくれる、**Claude Code のための**ドット絵デスクトップコンパニオンです。
標準スキンはティールのネコ。スキンで着せ替えできます。
（非公式のコミュニティ製作物です。Anthropic社とは無関係です）

> **なぜ別ウィンドウ？**
> Claude Code 本体の UI にはキャラクター差し込み枠がないため、
> **フックで状態を書き → 最前面の透過ウィンドウが Claude ウィンドウに追従してアニメ**、
> という形にしています。

<video src="./assets/demo.mp4" width="100%" autoplay loop muted playsinline></video>  

## 状態一覧

| バッジ | いつ（フック） | アニメ |
|--------|----------------|--------|
| （非表示） `IDLE` | 待機 | 呼吸・まばたき・泡ぷくぷく |
| `LISTEN` | プロンプト受信（UserPromptSubmit） | 背伸びして目を見開き、キョロキョロ（**3秒でTHINKへ**） |
| `THINK` | 受信3秒後〜ツール開始まで／コンテキスト整理（PreCompact） | 目が泳ぐ・…… |
| `WORKING` | ツール実行（Pre/PostToolUse） | **端末に向かってカタカタ** |
| `DONE` | ターン完了（Stop）／バックグラウンドタスク完了（TaskCompleted） | ジャンプ→着地→**踏み鳴らし＋紙吹雪**（10秒で IDLE） |
| `ERROR` | ツール失敗（PostToolUseFailure）／ターン異常終了（StopFailure） | ＞＜目・よろけ（6秒で IDLE） |
| `確認待ち` | 要対応の通知（Notification: 許可プロンプト・入力待ち・エージェントの問いかけ等） | 小刻みホップでハサミぶんぶん。**数分放置すると持ち場を離れて画面中をうろうろ**（見逃し防止）、解決すると小走りで帰宅 |
| `SLEEP` | セッション終了（SessionEnd） | おすわり zzz |

アニメーションの流儀：感情は小道具でなく**動きだけ**（傾き・ホップ・しゃがみ・目の動き）で表現し、
環境エフェクトは**紙吹雪**のみ。

固着対策の安全網：フックイベントが**5分**（Bash / Agent 等の長時間ツール後は**30分**）
届かない場合、WORKING は自動で IDLE に戻ります。

## 動作環境（前提）

- **Windows 11** — ウィンドウ追従・透過にWin32 APIを使うためWindows専用です
  （Windows 10 でも動作しますが、通常サポートが2025年10月に終了しているため、
  ESU等で更新が継続されている環境でのみ推奨）
- **Python 3.10以上** —
  - 公式インストーラの標準構成でOK（**tkinter・pythonw同梱**。追加のpipパッケージは不要＝標準ライブラリのみ）
  - インストール時に「**Add python.exe to PATH**」を有効にしてください（`install.ps1` が `python` コマンドを探します）
- **Claude Code**（デスクトップアプリ推奨。ターミナルでのCLI利用でも可） —
  フック連動とウィンドウ追従の相手です。Claudeのウィンドウが無い間、バディは隠れて待機します

## インストール（このPC・他のPC共通）

> ⚠️ **フォルダの置き場所を先に決めてください。**
> インストールはファイルをコピーせず、このフォルダへの**絶対パス**を
> フック設定に書き込みます。インストール後にフォルダを移動・改名すると
> 連動が止まります（移動したくなったら、移動先でもう一度 `install.ps1` を
> 実行すれば配線し直せます）。
>
> インストール後に使われる場所は3つ：
> - **このフォルダ** — 本体（scripts/ とスキン。ここから直接実行されます）
> - **フック配線** — `~/.claude/settings.json`（または各プロジェクトの `.claude/settings.json`）
> - **状態・設定** — `~/.claude/buddy/`（status.json / config.json / キャッシュ / ログ）

```powershell
cd <buddyのフォルダ>
powershell -ExecutionPolicy Bypass -File install.ps1
```

対話式で「グローバル / このプロジェクトのみ / 別フォルダ」を選ぶだけ。最後にバディの起動まで面倒を見ます。
スクリプトから使う場合は `install.ps1 -Global` や `install.ps1 -Project <dir>`（`-Start`で起動も）。
プロンプトの言語はWindowsの表示言語に自動追従します（`-Lang en` / `-Lang ja` で強制）。

- フック設定の**原本**は [install.settings\settings.template.json](install.settings/settings.template.json)
  （`{{PYTHON}}` / `{{HOOK_ENTRY}}` をそのPCの実パスに置換して配線されます）
- 生成先の `.claude/settings.json` はマシン固有なのでgit管理外
- フックの配線変更は、通常**実行中のセッションにもすぐ自動反映**されます
  （Claude Code が設定ファイルを監視しているため）。反映されない場合
  （旧バージョン等）は新しいセッションを開いてください

### アンインストール

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

対話式でインストール時と同じ「グローバル / このプロジェクト / 別フォルダ」を選ぶだけ。
バディを停止し、settings.json から**バディの配線だけ**を除去します（他の設定・他のフックは無傷。バックアップ自動作成）。
スクリプトからは `uninstall.ps1 -Global` / `-Project <dir>`、
`-PurgeData` を足すと `~/.claude/buddy`（設定・キャッシュ・ログ）も削除。
配線の除去も通常はすぐ反映されます（残っているように見える場合は
セッションを張り直してください）。

## クイックスタート

```powershell
# バディを出す（多重起動は自動で防止）
powershell -ExecutionPolicy Bypass -File scripts\start_buddy.ps1

# しまう
powershell -ExecutionPolicy Bypass -File scripts\stop_buddy.ps1
```

- Claude Code のウィンドウを動かすと**追従**、閉じる/最小化すると**隠れます**
  （右クリック→「**右隅居座りモード** ON」で、隠れる代わりにデスクトップ右下へ
  常駐する挙動に変更できます。config: `park_when_hidden`）
- サイズ変更: `python scripts\buddy.py --scale 3`（既定 2.4。小数OK＝有理数スケーリング）
- 内部は64×64の細グリッド：体は2ドット単位のチャンキー描画、表情（＞＜目・ヒゲ等）だけ1ドット単位＋アンチエイリアスで繊細に

## アイドル中のお楽しみ

| 動作 | いつ | 内容 |
|------|------|------|
| **お散歩** | idleが3分続くと | 左へトコトコ→立ち止まってキョロキョロ→歩いて帰宅。作業が入ると**小走りで持ち場へ戻る** |
| **筋トレ** | idle中 90〜240秒に1回（サッカーと抽選） | バーベルカール数レップ。持ち上げ中は＞＜で力み、後半は汗 |
| **サッカー** | 同上（筋トレと抽選） | 左足元でリフティング×2→トラップしてドヤ顔。目線はボールを追う |
| **つつき** | クリック（ドラッグしない） | むぎゅっ（＞＜）となってからびっくりジャンプ。散歩中につつくと慌てて帰る |

### 時間帯イベント

- **深夜（23時〜5時）**: idleが3分続くと居眠りを始める（イベントが来ればすぐ起きる）
- **朝（6時〜9時）**: その日最初のidleで1回だけ朝の体操（筋トレ）
- **金曜**: DONEの紙吹雪パーティーが2倍の長さ

- コマ送りは**可変ホールド**（基本85ms＋溜め最大500ms、ジャンプは滞空頂点でスロー）
- 調整は**右クリック→「設定…」**のスライダーから（サイズ / 散歩までの秒数 / プレミア間隔 / うろうろ開始秒数）。
  config.json直編集派は `walk_after_sec` / `premium_min_sec` / `premium_max_sec` / `roam_after_sec` / `scale` / `skin`
- 右クリックメニューに「お散歩デモ」「筋トレデモ」「サッカーデモ」「うろうろデモ」があります
  （うろうろデモは確認待ち放置の画面徘徊を8秒ツアーで再現し、自動で持ち場に帰ります）
- 設定内の**全体デモショー**（60 / 120 / 180秒・停止）は、全アクション＋BGM＋効果音を
  台本どおり自動上演します。README用GIFはこれを回して画面録画するだけ。
  上演中は選曲の固定を解除して**全ムードで曲が切り替わり**、音は一時ON
  （小さすぎる音量は35%へ一時ブースト）。終わると元の設定に完全復元されます。
  うろうろは既定で除外（録画フレームを飛び出すため）——チェック
  「**うろうろも台本に入れる**」でイベント上映用のフル台本になります

## レトロBGMとLEDバー

右クリック→「🎵 レトロBGM」からONにすると、内蔵チップチューン12曲をループ再生します。
スプライトの下には**LEDバー**が付いていて、気分や曲に合わせて光ります。

- **音源ファイル不要** — 全曲を標準ライブラリだけでその場で合成
  （WAVキャッシュは `~/.claude/buddy/bgm_cache`。外部通信もなし）
- **ギャップレスループ** — winmm waveOut のハードウェアループ再生
  （使えない環境では winsound に自動フォールバック）
- **気分で曲変更（既定ON）** — WORKING→Coffee Rush、DONE→Victory March のように
  状態に合わせて選曲。手動で選んだ曲は idle 程度では奪われませんが、
  イベント時は場を譲ります（完全に固定したい場合はOFFに）
- **音量** — メニューから 10〜70% の5段階を直接選択
- **自動ミュート** — バディが隠れている間（Claude最小化・終了中）はBGMも一時停止し、
  再表示で同じ曲から再開
- **効果音（既定OFF）** — DONEでファンファーレ、エラーでずっこけ、つつきで「ぷに」、
  確認待ちでチャイム。メニューの「効果音 ON にする」で有効化
  （BGMと独立にONでき、音量はBGM音量に連動）
- **LEDパターン** — 既定は **auto**（気分連動）。手動で12種から選べて、
  曲を選ぶとその曲と相性のよいパターンに切り替わります（LED自体のOFFも可）
- 収録曲：Victory March / Modem Memories / Chill Elevator / Coffee Rush /
  Starlight / Pixel Plaza / Bug Chase / Deep Think / Terminal Tap /
  Morning Build / Pixel Waltz / Carousel Spin
- config.json のキー：`bgm_enabled` / `bgm_volume` / `bgm_track` /
  `bgm_follow_mood` / `led_enabled` / `led_mode` / `se_enabled`

## フック連携（操作連動）

配線は `install.ps1`（または `python scripts\install_hooks.py`）で行います。
クローン直後は未配線です。生成される `.claude/settings.json` はマシン固有の
絶対パスを含む**生成物**なのでgit管理外（壊れたら再インストールで再生成）。

- 配線変更は通常**すぐ自動反映**されます（反映されない場合はセッションを張り直し）
- セッション開始（SessionStart）で**バディを自動起動**します（既に居れば何もしません）
- **メッセージ送信でも自動復活**します（クラッシュ等で消えていた場合の自己修復）。
  ただし右クリック→終了／Esc／stop_buddy.ps1 で**自分で閉じた直後30分は復活しません**
  （終了の意思を尊重。すぐ戻したい時は新しいセッションを開くか start_buddy.ps1）

**全プロジェクトで反応させたい場合**（ユーザーグローバル導入）:

```powershell
python scripts\install_hooks.py            # ~/.claude/settings.json に追記（バックアップ自動作成）
python scripts\install_hooks.py --project <dir>   # 特定プロジェクトに入れる場合
```

## 操作

| 操作 | 内容 |
|------|------|
| クリック | つつき（びっくりジャンプ） |
| ドラッグ | 移動（位置は記憶され、追従にも反映） |
| 右クリック | 気分切替デモ / お散歩・筋トレ・サッカー・うろうろデモ / **スキン切替** / **レトロBGM・効果音・LED** / 位置リセット / 追従・**居座り**ON・OFF / バッジ表示 / **設定…** / **言語（English・日本語）** / 終了 |
| ダブルクリック | 気分を順番にデモ |
| Esc | 終了 |

**言語**：UIは日英対応。既定はWindowsの表示言語に自動追従し、右クリック下部の
**English / 日本語** で切替（選ぶと `config.json` の `lang` に固定保存。`null` に戻すと自動）。
UI文字列は [scripts/i18n.py](scripts/i18n.py) に集約してあり、言語追加は辞書1個です。

## スキン

`scripts/skins/` に `.py` を置くだけで右クリックメニューに登場します
（各スキンのidle顔が小さなアイコンとして並びます。選択は記憶されます）。

- スキンの規約：`NAME / PALETTE / GRID / build_frame / frame_hold / POKE_SEQ / GYM_SEQ` をエクスポートする
  （任意：`SOCCER_SEQ`、英語UI用の表示名 `NAME_EN`）
- 収録スキン：オリジナル13体
  （**ネコ・ネコさくら・ペンギン・うさぎ・おばけ・スライム・ビッグスライム・カエル・しば・フクロウ・タコ・キノコ・おにぎり**）
- スキンの作り方：
  - **パレット差し替え** — [skins/neko_sakura.py](scripts/skins/neko_sakura.py)（十数行）
  - **共有基盤に乗る** — [skins/_base.py](scripts/skins/_base.py) が振り付け・エフェクト・目・タイミングを提供するので、
    新キャラは「パレット＋体の描き方」だけ（例: [skins/penguin.py](scripts/skins/penguin.py)）
  - **フル自作** — [skins/neko.py](scripts/skins/neko.py) を参考にゼロから
  - **フィルタ型（後処理）** — [skins/slime_big.py](scripts/skins/slime_big.py)：
    スライムを読み込んで体だけ横1.5倍に引き伸ばし。
    目・口は**サイズそのまま間隔だけ**広げ、ボール等の小道具も等倍のまま
- ハウススタイル：目はベタ黒・光点なし
- 壊れたスキンファイルは無視されるだけで、バディは落ちません
- 切替の負荷はゼロ（フレームキャッシュを作り直すだけ）

> ⚠️ **スキンはPythonコード**であり、起動時にあなたの権限で実行されます。
> 信頼できる（または中身を読んだ）スキンだけを入れてください。

## 手動で状態を変える（テスト用）

```powershell
python scripts\set_status.py --mood happy
python scripts\set_status.py --mood work --tool Bash
```

## ファイル

```
MadoMochi/                  # リポジトリ直下
  README.md / README.ja.md  # このドキュメント（英語版 / 日本語版）
  LICENSE                   # MITライセンス本文
  .gitignore                # 生成物（キャッシュ・PNG等）の無視設定
  .claude/settings.json     # インストール時に生成されるフック配線（git管理外）
  install.ps1               # 対話式インストーラ
  uninstall.ps1             # 対話式アンインストーラ（配線除去・-PurgeDataでデータも）
  install.settings/
    settings.template.json  # フック配線の原本（プレースホルダ入り）
  scripts/
    buddy.py                # 浮遊ウィンドウ本体（tkinter・透過・最前面）
    retro_bgm.py            # 内蔵チップチューン12曲＋LEDパターン（純標準ライブラリ合成）
    i18n.py                 # UI文字列（英語・日本語）と表示言語の自動判定
    skins/                  # スキン13体＋共有基盤 _base.py（.pyを置くだけで追加）
    window_pos.py           # Claudeウィンドウ検出・右下アンカー（純ctypes）
    hook_entry.py           # フック入口（stdin JSON → status.json、常に exit 0）
    set_status.py           # 手動で気分変更
    install_hooks.py        # テンプレートからsettings.jsonへ配線
    start_buddy.ps1 / stop_buddy.ps1
  tests/
    test_units.py           # 回帰テスト一式（バディ停止中に python tests\test_units.py）
    soccer_strip.py         # スプライトをPNGで確認（python tests\soccer_strip.py out.png [mood] [skin]）
    capture.ps1             # DPI対応スクリーンキャプチャ（-CropX/-CropY/-CropW/-CropH/-Zoom）
```

状態ファイル等は `~/.claude/buddy/` に置かれます:
`status.json`（現在の気分）/ `config.json`（位置・設定）/ `hook.log`（フック実行ログ）/
`buddy_err.log`（描画ループのエラー記録、1MBでローテーション）/
`bgm_cache/`（合成した曲のWAVキャッシュ）

## トラブルシューティング

- **フックに反応しない** →
  `Get-Content $HOME\.claude\buddy\hook.log -Tail 20` で行が増えていればフックは発火しています。
  増えているのにバディが変わらない場合はバディを再起動。
  行が増えていない場合はインストールし直すか、セッションを張り直してみてください。
- **バディが出ない** → Claude ウィンドウが最小化されていると隠れます。
  右クリック→「追従 OFF」で常時表示にできるほか、
  「右隅居座りモード ON」ならデスクトップ右下で待機します。
- **閉じちゃった？** → メッセージ送信で自動復活します（クラッシュ自己修復）。
  自分で終了（Esc／メニュー／stop_buddy.ps1）した直後は30分だけ復活を控えます
  ——すぐ戻すには新しいセッションを開くか `start_buddy.ps1`。
- **ドット絵をいじった** → `stop_buddy.ps1` → `start_buddy.ps1` で反映。

## 注意

- **非公式プロジェクト**です。Anthropic社との提携・承認・後援はありません。
  「Claude」「Claude Code」はAnthropic, PBCの商標であり、本書では
  対応対象を説明する目的でのみ使用しています
- ステータスはローカルファイルのみ（外部送信なし）
- フックは fail-open 設計（失敗しても Claude Code の作業は止まりません）
- **マスコットIPについて**：同梱スキンはすべてオリジナルです。エンジン自体は
  マスコット非依存なので、他者のキャラクターのスキンを作って遊ぶ場合は
  **ローカル限定**にとどめ、再配布しないでください
- 業務ツールではなく、**かわいい相棒**です 🐱
- ライセンス: [MIT](LICENSE)

## 免責

本アプリは現状有姿で提供され、動作の正確性・可用性について一切の保証はありません。
ご利用は自己責任にてお願いします。ファイルのバックアップは利用者の責任で行ってください。

## 作者

[Hajime Tsui](https://hajimetwi3.github.io/hajimetwi3/)  
X (Twitter): https://x.com/hajimetwi3  

