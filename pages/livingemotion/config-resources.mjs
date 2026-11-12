import { locale, controlled, t } from "./i18n.mjs";
// 按配置键维护帮助，避免依赖后端自由文本的逐词翻译。
const rows = `enabled|Enable lifecycle processing. Module switches and operating mode still apply.|生活イベント処理を有効にします。モードと各モジュールの制限にも従います。
mode|Observe-only records state without autonomous sending. Active mode still requires authorization.|観察モードは状態を記録し自発送信しません。通常モードでも許可が必要です。
persona_mode|Follow each conversation persona or explicitly select an existing native persona.|会話の人格に従うか、既存のネイティブ人格を指定します。
persona_id|Select a native persona for explicit mode. This does not change the resolution mode.|指定モード用の人格を選びます。この項目だけでは解決モードは変わりません。
persona_shared_state|Share numeric emotion and energy within one persona. Conversation bodies and relationship sources stay separate.|同一人格の感情・活力の数値を共有します。会話本文と関係の出典は分離します。
timezone|Use an IANA timezone such as Asia/Shanghai or Asia/Tokyo for schedules and daily limits.|睡眠と日次上限に IANA タイムゾーンを使います。例：Asia/Shanghai、Asia/Tokyo。
provider_id|Default background chat model. Empty follows the conversation model; dedicated task models may override it.|バックグラウンド生成の既定モデルです。空欄で会話モデルに従い、専用モデルがあれば優先します。
fallback_provider_id|Fallback only before a request is sent. Unknown or timed-out requests are not automatically resent.|送信前のみ予備モデルに切り替えます。結果不明やタイムアウト時は自動再送しません。
emotion_model_enabled|Optional model refinement. Local emotion rules remain active when off; interval and model budget apply.|モデルによる補助分析です。無効時もローカル規則は有効で、間隔と予算に従います。
emotion_interval_seconds|Minimum seconds between model emotion analyses. Quiet hours skip model calls and keep local rules only. Available events, model and budget are still required.|感情分析の最小間隔（秒）です。静默時間帯はモデルを呼ばず、ローカル規則のみです。イベント、モデル、予算も必要です。
emotion_quiet_start_hour|Start hour of the quiet window, local 0–23. Equal start and end disables it. Only model analysis is skipped.|静かな時間帯の開始時刻（0～23 時）です。開始と終了が同じなら無効です。モデル分析のみを止めます。
emotion_quiet_end_hour|End hour of the quiet window, local 0–23. Analysis resumes at this hour; start greater than end wraps overnight.|静かな時間帯の終了時刻（0～23 時）です。この時刻から分析を再開し、開始が終了より大きい場合は日付をまたぎます。
autonomy_enabled|Allow proactive contact after saving. Authorized contacts, timing, sleep and budget gates still apply.|保存後の自発連絡を許可します。連絡先の許可、時間、睡眠、予算の制限に従います。
autonomy_qq_ids|Comma or space separated QQ IDs, matching known private conversations only. Blank authorizes no new private contacts.|QQ 番号をカンマや空白で区切ります。既知の個別会話のみ照合し、空欄では新たな私聊を許可しません。
autonomy_qq_group_ids|QQ group IDs, not member IDs. Blank covers known groups only when group autonomy is enabled; all gates still apply.|メンバー番号ではなく QQ グループ番号です。空欄は群の自発行動が有効な場合に既知の全群が対象です。
group_autonomy_enabled|Separate master switch for groups. Private emotions and memories must not be shared into groups.|グループ用の独立したスイッチです。個別会話の感情や記憶をグループに共有しません。
muted_scopes|Space separated existing scope keys. Muting takes priority over allowed contact lists.|既存の範囲キーを空白区切りで入力します。ミュートは許可リストより優先します。
active_start|Start of the daily active window, local HH:MM. Sleep and do-not-disturb restrictions take priority.|自発行動時間の開始です。現地 HH:MM 形式で、睡眠・通知抑制を優先します。
active_end|Exclusive end of the active window. Overnight ranges are supported; endpoints must differ.|自発行動時間の終了境界を含みません。日付越えに対応し、開始と終了は異なる値にします。
dnd_start|Start of proactive do-not-disturb, local HH:MM. Does not block normal incoming messages.|自発送信の通知抑制開始です。現地 HH:MM で、通常の受信は妨げません。
dnd_end|End of do-not-disturb. Supports overnight ranges; endpoints must differ.|通知抑制の終了です。日付越えに対応し、開始と同時刻にはできません。
behavior_style|Gentle, balanced or lively willingness to speak. Quota and timing restrictions always apply.|穏やか・自然・活発から選びます。枠と時間の制限は常に適用します。
behavior_emotional_share|Allow gentle feeling sharing only in familiar private relationships; no pressure to comfort or reply.|親しい個別関係でのみ気持ちをそっと共有します。慰めや返信を強制しません。
behavior_provider_id|Dedicated proactive model; empty uses the default/current model. Model and behavior quotas both apply.|自発チャット専用モデルです。空欄で既定・会話モデルを使い、モデル予算と行動枠の両方に従います。
behavior_random_min_minutes|Minimum random wait, 1–10080 minutes, no greater than maximum. Waiting does not guarantee sending.|最短ランダム待機は 1～10080 分で、最長以下にします。待機後の送信は保証しません。
behavior_random_max_minutes|Maximum random wait, 1–10080 minutes. Sleep, active chat, relationships and budget are checked afterward.|最長ランダム待機は 1～10080 分です。終了後も睡眠、会話、関係、予算を確認します。
behavior_idle_minutes|Quiet interval, 1–1440 minutes. Group activity uses the whole group's latest message.|会話後の静かな時間は 1～1440 分です。グループは群全体の最新メッセージを基準にします。
behavior_daily_limit|Daily attempt quota across all conversations. Failed and unknown attempts also count.|全会話の 1 日の試行上限です。失敗や結果不明の試行も消費します。
behavior_scope_daily_limit|Daily attempt quota per actual conversation, in addition to the overall limit.|実際の会話ごとの 1 日の試行上限です。全体上限と同時に適用します。
behavior_cooldown_seconds|Cooldown in seconds after a proactive attempt. Random wait also applies.|自発試行後の待機時間（秒）です。ランダム待機も同時に適用します。
behavior_unanswered_limit|Stop after this many unanswered attempts. Unknown sends count conservatively.|連続未応答がこの回数に達すると停止します。送信結果不明も保守的に加算します。
night_schedule_enabled|Maintain sleep cycles automatically. Requires a valid timezone; permission to sleep is a separate setting.|睡眠周期を自動管理します。有効なタイムゾーンが必要で、睡眠の許可は別設定です。
allow_sleep|Allow sleep to affect chat availability. When off, energy can still be recorded.|睡眠による返信可否への影響を許可します。無効でも活力は記録できます。
nap_enabled|Enable the nap interval. Chat blocking still depends on permission to sleep.|昼寝時間帯を有効にします。返信停止には睡眠の許可も必要です。
nap_start|Local nap start in HH:MM, such as 13:00. Must differ from nap end.|昼寝開始を現地 HH:MM で入力します。例 13:00。終了とは異なる時刻にします。
nap_end|Local nap end in HH:MM, such as 14:30. Energy and sleep rules still apply.|昼寝終了を現地 HH:MM で入力します。例 14:30。活力と睡眠規則も適用します。
fatigue_start|Start of the night cycle. Drowsiness begins halfway between this time and deep sleep.|夜間周期の開始です。開始と深い眠りの中間で眠気段階に移ります。
fatigue_end|End of night fatigue consumption; this does not itself end deep sleep.|夜間の疲労消費終了です。この時刻だけで深い眠りが終了するわけではありません。
deep_sleep_at|Deep sleep time between night start and base wake. Local HH:MM supports overnight ordering.|夜間開始と基本起床の間に深い眠りの時刻を設定します。現地 HH:MM で日付越えに対応します。
wake_at|Base wake time before stored lie-in. Lie-in is sampled once per cycle, never redrawn on refresh.|保存された二度寝時間を加える前の基本起床です。抽選は周期ごとに 1 回で、更新時に再抽選しません。
lie_in_min_minutes|Minimum lie-in, 0 or more, no greater than maximum. Stored for the cycle.|最短の二度寝時間は 0 以上で、最長以下です。周期中は保存値を使います。
lie_in_max_minutes|Maximum lie-in, 0–1440 minutes. Adds to the base wake time.|最長の二度寝は 0～1440 分で、基本起床時刻に加算します。
wake_mode|Allow private chat, no chat wake, or private chat plus native group mentions. Plain @ text is not a native mention.|個別のみ・起こさない・個別と群のネイティブメンションから選びます。通常の @ 文字列はメンションではありません。
wake_reply_limit|Reply attempts per wake window, 1–100. Failed generation attempts count too.|起床ウィンドウ内の返信試行は 1～100 回です。生成失敗も数えます。
wake_window_minutes|Wake reply window, 1–1440 minutes, fixed from first host submission.|起床後の返信期間は 1～1440 分で、最初のホスト送信時から固定計算します。
energy_reply_cost|Energy per visible reply, 0–100 in steps of 0.1. Each actual reply is recorded once.|可視返信ごとの活力消費は 0～100、0.1 刻みです。各返信を 1 回だけ記録します。
energy_fatigue_per_minute|Energy spent per applicable fatigue minute, 0–100 in steps of 0.1.|該当する疲労状態の 1 分ごとの消費です。0～100、0.1 刻みです。
energy_recovery_per_minute|Energy recovered per applicable minute, 0–100 in steps of 0.1; total cap 100.|該当状態の 1 分ごとの回復です。0～100、0.1 刻みで、合計上限は 100 です。
energy_max|Read-only energy cap, fixed at 100.|活力上限は読み取り専用で 100 固定です。
catchup_enabled|Read stored unread messages on waking. Does not grant access to all platform history.|起床後に保存済み未読を読みます。プラットフォームの全履歴への権限ではありません。
catchup_reply_enabled|Allow bounded replies after reading unread messages. Model, budget and identity gates apply.|未読閲覧後の制限付き返信を許可します。モデル、予算、身元の検証に従います。
catchup_provider_id|Dedicated catch-up model; empty follows default/conversation model.|振り返り専用モデルです。空欄で既定・会話モデルに従います。
closing_enabled|Evaluate goodnight only for real conversations joined recently; not a broadcast to all contacts.|最近参加した実際の会話のみ就寝挨拶を評価します。全連絡先への一斉送信ではありません。
closing_random|Generate varied farewells using model budget. Off uses a local template.|モデル予算を使って挨拶を生成します。無効時はローカル定型文を使います。
closing_lead_minutes|Evaluate goodnight 0–60 minutes before night fatigue starts.|夜間疲労開始の 0～60 分前に就寝挨拶を評価します。
closing_provider_id|Dedicated farewell model, only used when random generation and budget permit.|挨拶専用モデルです。ランダム生成と予算が許可する場合のみ使用します。
diary_enabled|Automatically generate private, subjective diaries from authorized sources using model budget.|許可された出典からモデル予算を使い、非公開の主観的日記を自動生成します。
diary_at|Local planned diary time in HH:MM. Missing sources or budget can cause a skip.|予定時刻を現地 HH:MM で入力します。素材や予算不足では見送る場合があります。
diary_backfill_yesterday|Backfill only yesterday, subject to source validity, retry limits and budget.|昨日分だけを補完します。素材の有効性、再試行上限、予算に従います。
diary_provider_id|Dedicated diary model; empty uses default model.|日記専用モデルです。空欄で既定モデルを使用します。
diary_retries|Retry limit 0–2. Each attempt uses budget; unknown results are not blindly resent.|再試行上限は 0～2 回です。各試行で予算を使い、結果不明時は安易に再送しません。
diary_retention_days|Retention for unpinned diaries, 1–365 days. Pinned records follow their own retention rules.|未固定日記を 1～365 日保存します。固定記録は別の保存規則に従います。
dream_enabled|Allow dreams during permitted sleep cycles with sources, model and budget. Dreams remain imaginary.|許可された睡眠周期で素材、モデル、予算がある場合に夢を生成します。夢は常に想像です。
dream_provider_id|Dedicated dream model; empty uses default model. Imaginary content must remain marked as such.|夢専用モデルです。空欄で既定モデルを使い、想像であることを明示します。
dream_per_night|Attempt limit 1–2 per sleep cycle. Failures do not restore unlimited quota.|睡眠周期ごとに 1～2 回の試行上限です。失敗で無制限に枠が戻ることはありません。
dream_retention_days|Retention for unpinned dreams, 1–30 days, independent of clarity decay.|未固定の夢を 1～30 日保存します。鮮明度の減衰とは独立しています。
dream_half_life_seconds|Seconds for dream clarity to halve, for example 86400 for one day. Does not change retention or factual status.|鮮明度が半減する秒数です。86400 は 1 日。保存期間や想像属性は変えません。
experience_body_chars|Maximum 1–8000 characters per diary/dream. Token budgets are separate.|日記・夢ごとの文字数は 1～8000 です。トークン予算は別制限です。
home_city|Public home city for weather context, not a private address. Does not set timezone automatically.|天気背景用の公開都市名です。私的な詳細住所は入力せず、タイムゾーンは別途設定します。
livingmemory_enabled|Use the installed LivingMemory interface when authorized. Off uses the local vector path.|許可された LivingMemory が導入済みの場合に使用します。無効時はローカルベクトルを使います。
memory_read|Permit retrieval with source, purpose and identity filtering. No fallback to private sources when unavailable.|出典・目的・身元で絞った検索を許可します。利用不可時に私有素材へ回避しません。
memory_write|Permit reply experience writes, isolated by real source and retention rules.|実際の出典で分離し、保存規則に従って返信体験を書き込みます。
embedding_provider_id|Native embedding model for local vector memory. Disabled when LivingMemory manages embeddings.|ローカルベクトル用のネイティブ埋め込みモデルです。LivingMemory 管理時は無効です。
window_days|Source body retention, 1–7 days; per-scope and global item limits also apply.|会話本文素材の保存は 1～7 日です。会話別・全体件数上限も適用します。
window_per_scope|Maximum sources per real conversation, 1–200. Bodies are not merged across private/group contexts.|実際の会話ごとの素材上限は 1～200 件です。個別と群の本文は合算しません。
window_global|Maximum source bodies across all conversations, 1–10000, pruned by retention rules.|全会話の素材本文は 1～10000 件で、保存規則に従って削減します。
body_max_chars|Maximum 1–8000 characters per chat source. Model input tokens are limited separately.|会話素材ごとの文字数は 1～8000 です。モデル入力トークンは別制限です。
event_days|Positive number of retention days for events without bodies, separate from diary and source retention.|本文なしイベントの保存日数を正整数で指定します。日記・素材とは別の規則です。
scheduler_seconds|Background evaluation interval, 1–3600 seconds. Not every tick invokes a model or sends.|バックグラウンド評価間隔は 1～3600 秒です。毎回モデル呼出や送信を行うわけではありません。
model_concurrency|Concurrent background model tasks, 1–8, separate from normal AstrBot chat concurrency.|バックグラウンドモデル同時実行は 1～8 件です。通常の AstrBot 会話とは別設定です。
queue_size|Bounded background waiting queue, 1–1000 tasks, not a daily quota.|バックグラウンド待ち行列は 1～1000 件です。日次枠ではありません。
model_daily_limit|Daily background model reservation budget shared across emotions, diaries, dreams and behavior. Failed reserved attempts count.|感情・日記・夢・行動で共有する日次モデル予約予算です。予約済み失敗も消費します。
model_input_tokens|Input token cap per task, 1–32768. This is neither characters nor a daily total.|タスクごとの入力は 1～32768 トークンです。文字数や日次合計ではありません。
model_output_tokens|Output token cap per task, 1–8192. Proactive messages may use a smaller internal limit.|タスクごとの出力は 1～8192 トークンです。自発メッセージは内部でさらに短くする場合があります。
model_timeout_seconds|Request timeout, 1–120 seconds. Timeout does not prove non-execution; unknown sends are not repeated.|要求タイムアウトは 1～120 秒です。未実行を保証しないため、結果不明の送信は繰り返しません。
relationship_special_description|Custom behavior for the administrator-set unique relationship at 100. Per-account notes take priority.|管理者が設定する100点の特別な関係の説明です。相手別メモを優先します。
relationship_stage_names|Five names: 0–10, 11–24, 25–44, 45–99 and unique 100. Ordinary interactions cap at 99; old eleven-name settings remain compatible.|0～10、11～24、25～44、45～99、特別な100の5名称です。通常は99が上限で、旧11名称も互換対応します。`;
const help = Object.fromEntries(rows.split("\n").map(row => { const [key, en, ja] = row.split("|"); return [key, [en, ja]]; }));
const examples = Object.fromEntries(`enabled|Enable and select observe-only mode to inspect state first.|まず有効にし、観察モードで状態を確認します。
mode|Use observe-only while checking settings, then switch to active mode.|設定確認中は観察モード、確認後は通常モードを選びます。
persona_mode|Select explicit mode and then choose an existing persona below.|指定モードを選び、下の項目で既存の人格を指定します。
persona_id|Choose a configured persona after selecting explicit mode.|指定モードにしてから設定済みの人格を選びます。
persona_shared_state|Enable to share energy across private and group chats of this persona.|この人格の個別・群会話で活力を共有する場合は有効にします。
timezone|Asia/Shanghai or Asia/Tokyo.|Asia/Shanghai または Asia/Tokyo。
provider_id|Choose a default model, then override it for diaries if needed.|既定モデルを選び、必要なら日記だけ専用モデルを指定します。
fallback_provider_id|Select another configured chat model for pre-request fallback.|要求送信前の代替として別の設定済みモデルを選びます。
emotion_model_enabled|For lower cost, leave off; for refinement, enable with a 300-second interval.|低コストなら無効に、補助分析を使うなら有効にして間隔を 300 秒にします。
emotion_interval_seconds|600 means at least ten minutes between analyses.|600 は分析間隔が最低 10 分です。
emotion_quiet_start_hour|3 with an end of 8 skips model calls from 03:00 to 08:00 local time.|開始 3、終了 8 で現地時間 03:00～08:00 にモデルを呼びません。
emotion_quiet_end_hour|Start 22 with an end of 6 skips overnight; set both equal to disable quiet hours.|開始 22、終了 6 は夜間を静かな時間帯にし、両方同じ値なら無効です。
autonomy_enabled|Authorize private contacts and set a 90–240 minute random wait, then save.|個別連絡先を許可し、ランダム待機を 90～240 分にして保存します。
autonomy_qq_ids|12345678, 23456789 allows these two known private contacts.|12345678, 23456789 は既知の個別連絡先 2 人を許可します。
autonomy_qq_group_ids|34567890, 45678901 limits activity to those known groups. Blank requires the group switch.|34567890, 45678901 で対象群を限定します。空欄でも群スイッチは必要です。
group_autonomy_enabled|Leave off when proactive contact should be private only.|自発連絡を個別だけにする場合は無効のままにします。
muted_scopes|Copy an existing scope_key to pause that conversation.|既存の scope_key をコピーして、その会話の自発行動を停止します。
active_start|09:00 with an end of 22:00 allows daytime and evening evaluations.|開始 09:00、終了 22:00 で日中と夜間に評価します。
active_end|Start 20:00 and end 00:30 continues until the next day.|開始 20:00、終了 00:30 で翌日の午前 0 時半までです。
dnd_start|01:00 with an end of 08:00 avoids overnight proactive messages.|開始 01:00、終了 08:00 で深夜の自発送信を抑えます。
dnd_end|Start 23:00 and end 08:00 ends do-not-disturb the next morning.|開始 23:00、終了 08:00 で翌朝に通知抑制を終了します。
behavior_style|Choose gentle for fewer interruptions or lively for more willingness to speak.|割り込みを減らすなら穏やか、会話意欲を高めるなら活発を選びます。
behavior_emotional_share|Enable to allow gentle feeling sharing in suitable private conversations.|適切な個別会話で気持ちの共有を許可するなら有効にします。
behavior_provider_id|Use a lightweight configured model for proactive chat.|自発チャットには設定済みの軽量モデルを選べます。
behavior_random_min_minutes|90–240 means a random wait of 1.5 to 4 hours before evaluation.|90～240 は評価前に 1.5～4 時間待機します。
behavior_random_max_minutes|Set both bounds to 120 for a fixed two-hour wait.|最短・最長をともに 120 にすると 2 時間固定です。
behavior_idle_minutes|20 waits until there have been no messages for twenty minutes.|20 は直近 20 分に会話があれば待機を続けます。
behavior_daily_limit|6 permits at most six attempts across all conversations per day.|6 は全会話合計で 1 日最大 6 回の試行です。
behavior_scope_daily_limit|Total 6 and per-conversation 2 permits at most two attempts for one friend.|全体 6、会話別 2 なら 1 人の相手には最大 2 回です。
behavior_cooldown_seconds|7200 means a cooldown of at least two hours.|7200 は最低 2 時間の待機です。
behavior_unanswered_limit|2 pauses after two consecutive unanswered attempts.|2 は連続 2 回未応答でいったん停止します。
night_schedule_enabled|Use night start 23:30, deep sleep 02:30 and base wake 08:00.|夜間開始 23:30、深い眠り 02:30、基本起床 08:00 を指定します。
allow_sleep|Disable if normal chat should remain available overnight.|夜間も通常の返信を続けたい場合は無効にします。
nap_enabled|Enable and set 13:00–14:30 for an afternoon nap.|有効にし、13:00～14:30 の昼寝時間を設定します。
nap_start|13:00 starts the nap at one in the afternoon.|13:00 は午後 1 時に昼寝を開始します。
nap_end|14:30 ends the nap at half past two.|14:30 は午後 2 時半に昼寝を終了します。
fatigue_start|23:30 start and 02:30 deep sleep gives a 01:00 drowsy transition.|開始 23:30、深い眠り 02:30 なら眠気への移行は翌日 01:00 です。
fatigue_end|07:00 ends fatigue consumption while a configured 08:00 wake still applies.|07:00 に疲労消費を止めても、設定した 08:00 の起床は有効です。
deep_sleep_at|23:30 → 02:30 → 08:00 is ordered correctly across midnight.|23:30 → 02:30 → 08:00 は日付越えの正しい順序です。
wake_at|08:00 plus 0–90 minutes of lie-in wakes between 08:00 and 09:30.|08:00 に二度寝 0～90 分を加えると起床は 08:00～09:30 です。
lie_in_min_minutes|0–30 permits waking on time or up to half an hour later.|0～30 なら定刻から 30 分後までに起床します。
lie_in_max_minutes|15–45 with a base wake of 08:00 gives 08:15–08:45.|15～45、基本起床 08:00 なら 08:15～08:45 です。
wake_mode|Choose private-only if group mentions should not interrupt sleep.|群のメンションで睡眠を妨げたくないなら個別のみを選びます。
wake_reply_limit|3 replies and a 10-minute window allow at most three attempts within ten minutes.|3 回・10 分なら、10 分以内に最大 3 回試行します。
wake_window_minutes|10 keeps the wake reply window open for at most ten minutes.|10 は起床後の返信期間を最大 10 分にします。
energy_reply_cost|4.0 spends four energy points per actual visible reply.|4.0 は可視返信ごとに活力を 4 点消費します。
energy_fatigue_per_minute|0.8 consumes about eight points over ten applicable minutes.|0.8 は該当する 10 分間で約 8 点消費します。
energy_recovery_per_minute|1.5 restores about fifteen points in ten applicable minutes, capped at 100.|1.5 は該当する 10 分間で約 15 点回復し、上限は 100 です。
energy_max|74 points means 74 out of the fixed maximum of 100.|74 点は固定上限 100 点のうち 74 点です。
catchup_enabled|Enable reading and leave replies off to review unread messages silently.|読むだけなら閲覧を有効にし、補答は無効にします。
catchup_reply_enabled|Enable both reading and replies to allow bounded catch-up responses.|閲覧と補答を有効にすると、上限付きで未読への補足返信を行えます。
catchup_provider_id|For many unread messages, choose a configured model with a longer context.|未読が多い場合は長いコンテキストに対応したモデルを選びます。
closing_enabled|Night start 23:30 and a five-minute lead evaluates goodnight around 23:25.|夜間開始 23:30、5 分前なら 23:25 頃に挨拶を評価します。
closing_random|Disable to reduce model calls and use the local template.|呼出を減らしてローカル定型文を使うなら無効にします。
closing_lead_minutes|5 with a 23:30 night start schedules evaluation around 23:25.|夜間開始 23:30、5 分前なら予定は 23:25 頃です。
closing_provider_id|Choose a lightweight model for short goodnight messages.|短い就寝挨拶には軽量モデルを選べます。
diary_enabled|Enable and schedule the day's diary at 23:00 local time.|有効にし、当日の日記を現地 23:00 に予定します。
diary_at|23:00 is suitable for reflecting at the end of the day.|23:00 は一日の終わりの振り返りに使えます。
diary_backfill_yesterday|Enable to attempt yesterday's missing diary after an interruption.|中断で昨日の日記がなければ、有効にして補完を試せます。
diary_provider_id|Choose one model for diaries and a separate creative model for dreams.|日記用モデルと夢用モデルを個別に指定できます。
diary_retries|0 disables retries; 2 allows bounded retries after explicitly retryable failures.|0 は再試行なし、2 は明確に再試行可能な失敗後の上限です。
diary_retention_days|30 retains approximately one month of unpinned diaries.|30 は未固定日記を約 1 か月保存します。
dream_enabled|Enable for imaginary sleep experiences; disable if only practical records are wanted.|想像の睡眠体験を使うなら有効にし、実用記録だけなら無効にします。
dream_provider_id|Choose a configured model suited to short narratives.|短い物語に適した設定済みモデルを選びます。
dream_per_night|1 allows at most one dream attempt per sleep cycle.|1 は睡眠周期ごとに夢を最大 1 回試行します。
dream_retention_days|7 retains approximately one week of unpinned dreams.|7 は未固定の夢を約 1 週間保存します。
dream_half_life_seconds|86400 halves clarity after approximately one day.|86400 は約 1 日で鮮明度が半減します。
experience_body_chars|2000 caps each generated record at approximately 2000 characters.|2000 は各記録の本文を約 2000 文字以内にします。
home_city|Enter Shanghai and configure Asia/Shanghai separately as the timezone.|Shanghai を入力し、時区は別途 Asia/Shanghai に設定します。
livingmemory_enabled|Enable after installing and configuring LivingMemory; otherwise configure local embeddings.|LivingMemory の導入・設定後に有効にし、それ以外はローカル埋め込みを設定します。
memory_read|Enable to retrieve conversation experiences when selecting topics.|話題選択時に会話体験を検索したい場合は有効にします。
memory_write|Enable to store reply experiences; disable to stop adding records.|返信体験を保存するなら有効にし、追加停止なら無効にします。
embedding_provider_id|Select a configured AstrBot embedding provider for local vector memory.|ローカルベクトルを使う場合は AstrBot の設定済み埋め込み提供元を選びます。
window_days|7 uses at most the most recent week of source bodies.|7 は直近最大 1 週間の素材本文を使います。
window_per_scope|200 retains at most 200 recent sources per conversation.|200 は会話ごとに最新最大 200 件の素材を保存します。
window_global|10000 caps stored source bodies across the plugin at ten thousand.|10000 は全プラグインの本文素材上限を 1 万件にします。
body_max_chars|8000 prevents one very long message from filling the source window.|8000 は極端に長い 1 件で素材枠を占有しないための上限です。
event_days|30 retains body-free event records for approximately one month.|30 は本文なしイベントを約 1 か月保存します。
scheduler_seconds|60 evaluates about once a minute without guaranteeing model calls.|60 は約 1 分ごとに評価し、モデル呼出は保証しません。
model_concurrency|1 suits lightweight use; 2 permits two background tasks at once.|1 は軽量運用向き、2 はバックグラウンド処理を 2 件並列にします。
queue_size|100 allows at most one hundred waiting tasks.|100 は最大 100 件の待機タスクを許可します。
model_daily_limit|48 allows at most forty-eight background reservations per day.|48 はバックグラウンド予約を 1 日最大 48 回にします。
model_input_tokens|4096 suits short tasks; longer diaries may need a higher cap.|4096 は短い処理向きで、長い日記には増量を検討できます。
model_output_tokens|1024 can suit diaries; proactive messages may remain shorter.|1024 は日記に使えますが、自発メッセージはさらに短い場合があります。
model_timeout_seconds|30 suits faster models; 60 can suit slower models.|速いモデルには 30 秒、遅いモデルには 60 秒を使えます。
relationship_stage_names|["","","Friendly","","Owner"] customizes the friendly and unique stages.|["","","友好","","主人"] は友好と特別の名称を変更します。`.split("\n").map(row => { const [key, en, ja] = row.split("|"); return [key, [en, ja]]; }));
const legacyHelp = {
  memory_mode: ["Legacy memory mode. Use the current memory backend controls when available.", "旧版の記憶モードです。利用可能なら現在の記憶バックエンド設定を使います。"],
  memory_export: ["Legacy permission to export memory. Host authorization still applies.", "旧版の記憶エクスポート許可です。ホストの権限検証にも従います。"],
  night_enabled: ["Legacy switch for night state tracking. Prefer the current automatic schedule control.", "旧版の作息記録スイッチです。現在の自動作息設定を優先します。"],
  night_block_chat: ["Legacy sleep blocking setting. Current sleep permission and schedule rules govern availability.", "旧版の睡眠による会話阻断です。現在の睡眠許可と作息規則に従います。"],
  sleep_at: ["Legacy sleep start time. Use current night start and deep sleep settings when available.", "旧版の入眠時刻です。利用可能なら現在の夜間開始と深い眠りの設定を使います。"],
  night_policy_version: ["Sleep policy migration version. Preserve the host value unless the host provides migration controls.", "睡眠規則の移行バージョンです。ホストが移行操作を提供しない限り値を保持します。"],
  autonomy_scopes: ["Legacy allowed conversation scope list. Only existing authorized conversations are eligible.", "旧版の許可会話リストです。既存の許可済み会話だけが対象です。"],
};
Object.assign(help, legacyHelp);
export function fieldHelp(field, kind = "help") {
  const original = field[kind] || field.help;
  if (locale() === "zh-CN") return original || t("更改由宿主校验并写回原生配置。");
  const index = locale() === "en" ? 0 : 1;
  if (kind === "example" && examples[field.key]) return examples[field.key][index];
  if (/^relationship_stage_(?:[0-9]|10)_name$/.test(field.key)) return help.relationship_stage_names[index];
  return help[field.key]?.[index] || controlled(original) || t("更改由宿主校验并写回原生配置。");
}
export const localizedFieldLabel = field => controlled(field.label || field.key);
export const helpKeys = Object.keys(help);
