// 明确的界面资源表。每行依次为中文、英文、日文，插值不参与翻译。
const rows = `{0}–{1} 分|{0}–{1} points|{0}–{1} 点
TA 对此人的情绪|TA feelings toward this person|この相手に対する TA の感情
对此人的情绪分析|Analysis of feelings toward this person|この相手に対する感情の分析
尚无此人的独立互动状态；不会用人格总体情绪代替。|No independent interaction state for this person yet; persona-wide emotions will not be substituted.|この相手の独立した交流状態はまだありません。人格全体の感情で代用しません。
仅由当前账号在此会话的真实互动独立更新，不跨用户、会话或人格合并；不是对方的情绪。|Updated independently from real interactions with this account in this conversation, never merged across users, conversations or personas; these are not the other person's emotions.|この会話における現在のアカウントとの実際の交流のみで独立して更新します。ユーザー・会話・人格をまたいで統合せず、相手自身の感情を表しません。
人格总体情绪、TA 对此人的情绪和对方观察是三个独立通道。|Persona-wide emotions, TA feelings toward this person and human observations are three separate channels.|人格全体の感情、この相手に対する TA の感情、相手の観察は独立した三つの情報です。
紧绷|Strained|張り詰めている
紧张|Tense|緊張
担忧|Concerned|心配
低落|Subdued|沈んでいる
警觉|Alert|警戒
渴望陪伴|Seeking company|誰かと一緒にいたい
本地情绪数值启发式|Local emotion-value heuristic|ローカルの感情数値ヒューリスティック
按人记录的 HumanObservation 信号|Per-person HumanObservation signal|個人別に記録された HumanObservation の信号
人类观察记录|Human observation record|人間の観察記録
仅根据情绪数值计算的启发式状态指标，仅供软件展示；情绪、控制感和确定感并非实测结果，不代表人的情绪，不是心理诊断|Heuristic state indicators calculated only from emotion values for software display; emotions, control and certainty are not measured results, do not represent human emotions and are not a psychological diagnosis|感情の数値のみから算出した、ソフトウェア表示用のヒューリスティック状態指標です。感情・掌握感・確実性は実測結果ではなく、人間の感情を表すものでも心理診断でもありません
仅展示已记录的人类观测标签与置信度，不补推其他情绪，不是心理诊断|Shows only recorded human observation labels and confidence; no other emotions are inferred. This is not a psychological diagnosis|記録済みの人間の観察ラベルと信頼度のみを表示し、他の感情は推測しません。心理診断ではありません
日记任务|Diary task|日記タスク
梦境任务|Dream task|夢タスク
任务状态|Task status|タスク状態
任务 ID · job_id|Task ID · job_id|タスク ID · job_id
已排队|Queued|待機中
归属类型 · scope_kind / state_mode|Ownership type · scope_kind / state_mode|帰属タイプ · scope_kind / state_mode
当前是共享人格情绪，未提供逐用户独立情绪；HumanObservation 按人记录。|The current emotion state is shared by the persona; independent per-user emotions are not provided. HumanObservation is recorded per person.|現在は人格で共有する感情状態です。ユーザー別の独立した感情データは提供されていません。HumanObservation は個人別に記録します。
当前显示所选范围的 TA 情绪，不推测逐用户专属情绪；HumanObservation 按人记录。|Showing TA emotions for the selected scope without inferring user-specific emotions. HumanObservation is recorded per person.|選択範囲の TA の感情を表示し、ユーザー専用の感情は推測しません。HumanObservation は個人別に記録します。
仅在明确启用后生成|Generation runs only when explicitly enabled|生成は明示的に有効にした場合のみ実行します
界面语言|Interface language|表示言語
需要宿主认证|Host authentication required|ホスト認証が必要です
私人内容已清空。请在 AstrBot 宿主重新登录并确认管理权限。|Private content cleared. Sign in to AstrBot again and verify administrator access.|非公開内容を消去しました。AstrBot に再ログインし、管理権限を確認してください。
连接未确认|Connection unverified|接続未確認
访问被拒绝|Access denied|アクセス拒否
需要重新确认宿主连接与权限|Verify host connection and permissions|ホスト接続と権限を再確認してください
宿主仅返回了未分型错误，无法确认访问状态，已隐藏私人内容。请重新连接后核对上次请求结果。|The host returned an untyped error. Private content is hidden. Reconnect and verify the previous request.|ホストが分類のないエラーを返しました。非公開内容を非表示にしました。再接続し、前回の結果を確認してください。
访问被拒绝。页面参数不能代替宿主身份认证。|Access denied. Page parameters cannot replace host authentication.|アクセスが拒否されました。ページ引数はホスト認証の代わりにはなりません。
 当前显示旧快照，写操作已停用。| Showing an old snapshot; writes are disabled.| 古いスナップショットを表示中です。書き込みは無効です。
{0} 项 · 基准版本 {1}{2}|{0} changes · base revision {1}{2}|{0} 件 · 基準バージョン {1}{2}
 · {0} 项输入无效| · {0} invalid inputs| · 無効な入力 {0} 件
正在提交…|Submitting…|送信中…
保存到原生配置|Save native configuration|ネイティブ設定を保存
来源与有效期|Source and validity|出典と有効期限
来源|Source|出典
更新时间|Updated|更新日時
有效期|Expires|有効期限
有效状态|Validity|有効性
已过期，不应作为当前依据|Expired; not valid as current evidence|期限切れ。現在の根拠には使用できません
有效期内|Valid|有効期限内
未提供有效期|No expiry provided|有効期限の提供なし
TA 当前感受|TA's current feelings|TA の現在の感情
原生人格未提供|Native persona unavailable|ネイティブ人格の提供なし
尚无 TA 状态|No TA state available|TA の状態はまだありません
等待有来源的互动与状态评估。不会以对方情绪替代 TA 感受。|Waiting for sourced interactions and state assessment. Human emotions do not replace the TA's feelings.|出典のある交流と状態評価を待っています。相手の感情を TA の感情に置き換えません。
状态已过期|State expired|状態の期限切れ
对方观察|Human observation|相手の観察
尚无可用观察|No observation available|利用できる観察はありません
这是对对方状态的观察，不是 TA 的感受。|This observes the other person, not the TA's feelings.|これは相手の状態に関する観察であり、TA 自身の感情ではありません。
观察对象|Observed person|観察対象
可信度|Confidence|確信度
观察依据|Observation basis|観察の根拠
观察已过期，不作为当前依据|Observation expired; not current evidence|観察は期限切れで、現在の根拠には使用しません
依赖健康|Dependency health|依存機能の状態
宿主尚未提供依赖健康。|The host has not provided dependency health.|ホストから依存機能の状態が提供されていません。
可用|Available|利用可能
降级|Degraded|機能制限
不可用|Unavailable|利用不可
未提供|Not provided|提供なし
精力 · 来自长夜|Energy · from Night|活力 · 夜の状態から
当前作息|Current sleep state|現在の睡眠状態
状态归属|State ownership|状態の帰属
同一人格共享|Shared by persona|同じ人格で共有
真实会话独立|Separate per real conversation|実際の会話ごとに独立
由宿主解析|Resolved by host|ホストが解決
可用性与来源|Availability and source|利用可否と出典
状态|State|状態
暂不可用|Temporarily unavailable|一時利用不可
原因|Reason|理由
当前为真实会话独立模式。全局数值来自最近代表会话 {0}，不是共享状态或多会话平均值。|Conversation-specific mode. Global values come from representative conversation {0}; they are not shared or averaged.|会話ごとの独立モードです。全体の値は直近の代表会話 {0} から取得し、共有値や平均値ではありません。
当前人格|Current persona|現在の人格
名称|Name|名前
人格 ID|Persona ID|人格 ID
修订号|Revision|リビジョン
人格说明|Persona description|人格の説明
人格由 AstrBot 当前范围解析。切换页面主题不会切换人格；模型提供者也不代表 TA 身份。|AstrBot resolves the persona for the selected scope. Theme changes do not change persona; model providers do not define TA identity.|人格は選択範囲から AstrBot が決定します。テーマを変えても人格は変わりません。モデル提供元は TA の身元を示しません。
前往设置修改人格|Configure persona|人格設定へ
TA 情绪分析|TA emotion analysis|TA の感情分析
数值由本插件本地规则从四维状态推导，不是医学或心理诊断；缺少数据时不推测观测。|These numbers are derived from the four-dimension state by this plugin's own local rules; this is not a medical or psychological diagnosis, and missing observations are not inferred.|数値は本プラグインのローカルルールが四次元状態から導出したもので、医学・心理学的な診断ではなく、欠けた観察を推測しません。
宿主尚未提供情绪分析，以下仅显示已有 TA 状态。|The host has not provided emotion analysis. Only existing TA state is shown.|ホストから感情分析が提供されていません。既存の TA 状態のみ表示します。
六维分析|Six-dimensional analysis|6 次元分析
分析方法|Method|分析方法
四维情绪状态机 · 本地规则计算|Four-dimension affect state machine · computed by local rules|四次元感情ステートマシン · ローカルルールで計算
分析方法与局限|Analysis method and limits|分析方法と限界
方法：四维情绪状态机（pleasure / arousal / stress / social_need）＋事件增量＋半衰期回落，规则版本 emotion-1。|Method: a four-dimension affect state machine (pleasure / arousal / stress / social_need) with per-event deltas and half-life decay, rule version emotion-1.|方法：四次元感情ステートマシン（pleasure / arousal / stress / social_need）にイベント増分と半減期減衰を組み合わせ、ルール版は emotion-1。
输入：带来源的真实事件（信号、置信度、时间）、本地规则表，可选模型给出的有界增量修正。|Input: real events with provenance (signals, confidence, timestamps), the local rule table, and optionally a bounded delta refinement from the model.|入力：出所のある実イベント（シグナル・信頼度・時刻）、ローカルルール表、任意でモデルによる有界の増分補正。
步骤：取权重 → 查增量 → 单次裁剪到 ±0.15 → 窗口预算限制 → 迟到衰减 → 写回四维状态 → 无事件时按半衰期回落到基准。|Steps: weight → delta lookup → clamp to ±0.15 → window budget → late-event decay → write back the four dimensions → decay to baseline by half-life when idle.|手順：重み → 増分参照 → ±0.15 にクリップ → 窓内予算 → 遅延減衰 → 四次元へ書き戻し → 無イベント時は半減期で基準へ減衰。
输出：6 个情绪倾向与 6 个分析维度（0–100%）；置信度是输入事件自带的，不被本地规则改写。|Output: six emotion tendencies and six analysis dimensions (0–100%); confidence comes from the input event and is never rewritten by the local rules.|出力：6 つの感情傾向と 6 つの分析次元（0〜100%）。信頼度は入力イベント由来で、ローカルルールは書き換えません。
局限：规则驱动的近似，线性组合，没有学习与校准；描述的是软件状态，不是对人的心理测量。|Limits: a rule-driven approximation built from linear combinations, with no learning or calibration; it describes software state, not a psychological measurement of a person.|限界：ルール駆動の近似で線形結合のみ、学習も較正もありません。記述するのはソフトウェア状態であり、人物の心理測定ではありません。
完整说明见插件目录 docs/emotion-analysis.md。|The full write-up lives at docs/emotion-analysis.md in the plugin folder.|詳細はプラグインフォルダの docs/emotion-analysis.md を参照してください。
分析依据|Analysis basis|分析の根拠
说明|Note|説明
对方分析 · HumanObservation|Human analysis · HumanObservation|相手の分析 · HumanObservation
观察标签|Observation labels|観察ラベル
当前所选用户会话中的 TA 情绪；对方观察单独显示。|TA emotions in the selected user conversation; human observations are shown separately.|選択したユーザーの会話における TA の感情です。相手の観察は別に表示します。
请选择私聊及具体用户会话查看 TA 对该用户的情绪；当前显示所选人格/范围状态，不推测逐用户情绪。|Select a private user conversation to view TA emotions toward that user. The current persona/scope state does not imply per-user emotions.|個別ユーザーの私聊を選ぶと、そのユーザーに対する TA の感情を表示します。現在は人格・範囲の状態で、個人別の感情は推測しません。
五维状态分析|Five-dimensional state analysis|5 次元状態分析
实线与基准在同一归一坐标。情绪随时间恢复；刺激变化以实际记录为依据，不为打开页面调用模型。|Current and baseline use the same normalized scale. Emotions recover over time; changes follow recorded events. Opening this page does not call a model.|現在値と基準値は同じ正規化座標です。感情は時間とともに回復し、変化は記録に基づきます。ページを開いてもモデルを呼び出しません。
没有已授权人格，不能查询关系。请刷新宿主范围。|No authorized persona. Refresh host scopes to query relationships.|許可された人格がありません。ホストの範囲を更新してください。
上一页|Previous|前へ
下一页|Next|次へ
第 {0} 页 · 共 {1} 条 · 每页 10 条|Page {0} · {1} records · 10 per page|{0} ページ · 全 {1} 件 · 各 10 件
硬否决：{0}|Hard vetoes: {0}|拒否条件：{0}
适合度：{0}|Suitability: {0}|適合度：{0}
宿主未开放此操作，或尚未配置所需能力。|The host has not enabled this action or its prerequisites.|ホストが操作を許可していないか、必要な機能が未設定です。
上次执行结果不明。此页面已锁定重试，请核对执行记录。|The previous result is unknown. Retry is locked; check execution records.|前回の結果は不明です。再試行をロックしました。実行記録を確認してください。
模拟：符合条件|Simulation: eligible|シミュレーション：条件を満たす
模拟：暂不符合|Simulation: not eligible|シミュレーション：条件を満たさない
原因：{0}|Reason: {0}|理由：{0}
模型调用 0 · 消息发送 0|Model calls 0 · messages sent 0|モデル呼出 0 · メッセージ送信 0
模拟未返回候选。|Simulation returned no candidates.|候補が返されませんでした。
正在等一个自然的时机|Waiting for a natural opportunity|自然な機会を待っています
正在想要不要开口|Considering whether to speak|話しかけるか検討中です
这次先安静陪着|Keeping quiet company this time|今回は静かに寄り添います
还在聊天，先不插话|Conversation active; waiting quietly|会話中なので割り込みません
错过的时机已跳过|Missed opportunity skipped|逃した機会をスキップしました
上次检查中断，已停止旧任务|Previous check interrupted; old task stopped|前回の確認が中断し、古いタスクを停止しました
这次检查超时，先停下来|Check timed out; paused|確認がタイムアウトし、一旦停止しました
选择私聊或群聊查看具体节奏|Select a private or group conversation for its schedule|私聊またはグループを選ぶと具体的な間隔を確認できます
已保存的主动行为配置|Saved proactive behavior configuration|保存済みの自発行動設定
配置来自 config fields / values；这里不显示未保存草稿。开关开启不代表当前可以发送，实际执行仍受运行状态与后台限制约束。|Values come from config fields / values, excluding unsaved drafts. Enabled settings do not guarantee sending; runtime and backend restrictions still apply.|config fields / values の保存値です。未保存の下書きは含みません。有効でも送信を保証せず、稼働状態とバックエンドの制限に従います。
版本|Version|バージョン
宿主未提供主动行为配置字段。|The host provided no behavior configuration fields.|自発行動の設定項目が提供されていません。
留空|Empty|空欄
前往设置调整主动行为|Configure proactive behavior|自発行動の設定へ
以下为当前运行状态，与上方已保存配置分开。|Current runtime state follows, separate from saved configuration above.|以下は現在の稼働状態です。上の保存済み設定とは別です。
主动行为状态|Proactive runtime state|自発行動の稼働状態
自主发送|Autonomous sending|自発送信
剩余额度|Remaining quota|残り枠
下次随机检查|Next random check|次のランダム確認
冷却截止|Cooldown ends|クールダウン終了
未回应次数|Unanswered attempts|未応答回数
最近动机|Latest motive|最近の動機
此刻|Now|現在
自然地开口|Speaking naturally|自然に話しかける
想起聊过的事，就问问后续；关系熟悉时，关心近况或轻轻分享心情。每次只留一个容易接住的话头。|Follow up on previous topics, ask how things are going, or gently share feelings in familiar relationships. Offer one easy conversation starter.|以前の話題の続きを尋ね、親しい関係なら近況や気持ちをそっと共有します。一度に受け止めやすい話題を一つだけ残します。
随机等待 {0} 分钟后再次检查。对方没回应时放慢节奏，睡着或正在聊天时先安静。|Check again after a random wait of {0} minutes. Slow down after no response; stay quiet during sleep or active conversation.|ランダムに {0} 分待って再確認します。未応答時は間隔を延ばし、睡眠中や会話中は静かに待ちます。
未配置|Not configured|未設定
在「设置 → 主动行为」调整节奏、模型与联系范围，保存后自动开始等待。|Adjust timing, model and contacts in Settings → Proactive behavior. Saving starts the wait.|「設定 → 自発行動」で間隔、モデル、連絡範囲を調整し、保存すると待機を開始します。
当前联系范围标识|Current contact scope key|現在の連絡範囲キー
仅模拟 · 不计费不发送|Simulate only · no charge or sending|シミュレーションのみ · 課金・送信なし
模拟响应未证明零模型调用、零发送，不能作为安全模拟结果。|The response did not prove zero model calls and sends; simulation cannot be verified.|モデル呼出・送信が 0 だと確認できず、シミュレーション結果として使用できません。
模拟结束。未请求真实生成或发送。|Simulation finished. No actual generation or sending requested.|シミュレーションが終了しました。実際の生成や送信は要求していません。
行为模拟|Behavior simulation|行動シミュレーション
先检查候选和硬否决。模拟只计算规则，不调用收费模型。|Inspect candidates and vetoes first. Simulation evaluates rules without paid model calls.|まず候補と拒否条件を確認します。シミュレーションは規則のみ計算し、有料モデルを呼びません。
宿主未提供无费用模拟能力。|The host does not support free simulation.|ホストは無料シミュレーションに対応していません。
候选|Candidates|候補
当前没有已授权候选。|No authorized candidates.|許可された候補はありません。
实际生成与发送|Actual generation and sending|実際の生成と送信
长夜|Night|長い夜
作息状态|Sleep state|睡眠状態
梦境内部阶段|Internal dream phase|夢の内部段階
入睡时间|Sleep started|入眠時刻
预计醒来|Expected wake time|起床予定
变化原因|Change reason|変化の理由
精力|Energy|活力
当前精力|Current energy|現在の活力
醒后补课|Catch-up after waking|起床後の振り返り
已处理|Processed|処理済み
本次有界窗口|Bounded window|今回の制限付き範囲
进度说明|Progress note|進行状況
手动作息操作|Manual sleep controls|手動の睡眠操作
五档作息|Five sleep states|5 段階の睡眠状態
精力日志|Energy log|活力ログ
没有已授权人格，不能查询精力历史。|No authorized persona for energy history.|許可された人格がないため活力履歴を取得できません。
原因码 · reason_code|Reason code · reason_code|理由コード · reason_code
私人体验|Private experiences|非公開の体験
日记记录主观体会；梦境始终是想象。正文与来源仅在已认证管理页阅读。|Diaries record subjective experiences; dreams are always imaginary. Bodies and sources are private to the authenticated admin page.|日記は主観的な体験、夢は常に想像です。本文と出典は認証済み管理ページでのみ閲覧します。
日记|Diary|日記
梦境|Dream|夢
生成状态|Generation state|生成状態
手动生成 · 可能消耗模型额度|Manual generation · may use model quota|手動生成 · モデル枠を消費する場合があります
私人体验类型|Private experience type|非公開体験の種類
梦境 · 想象|Dream · imaginary|夢 · 想像
本地向量 · 待配置|Local vectors · setup required|ローカルベクトル · 要設定
本地轻量记录|Local lightweight records|ローカル簡易記録
本地向量记忆|Local vector memory|ローカルベクトル記憶
记忆接入|Memory integration|記憶連携
当前模式|Current mode|現在のモード
提供者|Provider|提供元
允许检索|Retrieval allowed|検索を許可
允许导出|Export allowed|エクスポートを許可
降级原因|Degradation reason|機能制限の理由
实际能力|Actual capabilities|実際の機能
尚未声明可用记忆能力。|No memory capabilities declared.|利用可能な記憶機能が宣言されていません。
关闭 LivingMemory 后使用本地向量模式；未配置原生 embedding 时显示待配置，不伪装成已有向量库。开启 LivingMemory 外部后端后，自动收录转由 LivingMemory 负责，本地向量自动收录停止。|With LivingMemory disabled, local vector mode is used; missing embedding configuration remains pending. When LivingMemory is enabled, it handles automatic collection and local vector collection stops.|LivingMemory 無効時はローカルベクトルを使用し、embedding 未設定なら要設定と表示します。LivingMemory 有効時は自動収録をそちらに任せ、ローカルの自動収録を停止します。
前往设置管理记忆|Configure memory|記憶の設定へ
按任务完成配置，所有更改统一保存。|Configure by task and save all changes together.|目的ごとに設定し、変更をまとめて保存します。
运行中|Running|稼働中
仅观察 · 不自主发送|Observe only · no autonomous sending|観察のみ · 自発送信なし
已停用|Disabled|無効
模式未提供|Mode unavailable|モードの提供なし
筛选记录|Filter records|記録を絞り込む
关键词或原因码|Keyword or reason code|キーワードまたは理由コード
筛选|Filter|絞り込み
当前页无有效数值曲线；详情按原记录显示。|No valid curve on this page; original record details remain available.|このページに有効な曲線はありません。元の記録の詳細を表示します。
当前页 TA 愉悦趋势，数值见各条记录的前后对照|TA pleasure trend on this page; before and after values appear in each record|このページの TA の快感推移。各記録の前後の値を参照してください
TA 愉悦 · 当前页由旧到新 · 0–100% · 非连续时间轴|TA pleasure · oldest to newest on this page · 0–100% · not a continuous timeline|TA の快感 · このページの古い順 · 0–100% · 連続時間軸ではありません
TA 维度|TA dimension|TA の次元
变化前|Before|変化前
变化后|After|変化後
情绪变化|Emotion change|感情の変化
行为记录|Behavior record|行動記録
私人日记|Private diary|非公開日記
梦境 · 想象，不是现实事实|Dream · imagination, not real facts|夢 · 想像であり現実の事実ではありません
私人日记 · 主观内容|Private diary · subjective content|非公開日記 · 主観的内容
住所未提供|Home city not provided|居住都市の提供なし
天气未获取|Weather not retrieved|天気の取得なし
已过期|Expired|期限切れ
有效期未提供|Expiry not provided|有効期限の提供なし
执行状态|Execution status|実行状態
硬否决|Hard veto|拒否条件
结果不明，不自动重发。|Unknown result; no automatic resend.|結果不明。自動再送しません。
正文未提供。|Body not provided.|本文の提供なし。
清晰度|Clarity|鮮明度
置顶|Pin|固定
取消置顶|Unpin|固定解除
阅读私人正文|Read private content|非公開本文を読む
素材来源与角色|Sources and roles|素材の出典と役割
我做的|TA actions|TA が行ったこと
对方说 / 做的|Human words / actions|相手の発言・行動
梦中内容|Dream content|夢の内容
来源不明|Unknown source|出典不明
未提供来源，不能据此认领真实事件。|No sources provided; do not claim real events from this.|出典がないため、実際の出来事として扱えません。
上下文、来源与耗时|Context, source and duration|文脈・出典・所要時間
当前没有已授权范围，不能查询记录。|No authorized scope for querying records.|許可された範囲がないため記録を取得できません。
正在读取记录…|Loading records…|記録を読込中…
没有符合筛选的记录。可以清空关键词重试。|No matching records. Clear the keyword and try again.|一致する記録はありません。キーワードを消して再試行してください。
当前范围暂无记录。不会用演示内容填充。|No records in this scope. No demo content is substituted.|この範囲には記録がありません。デモ内容で補いません。
第 {0} / {1} 页 · 共 {2} 条 · 每页 10 条|Page {0} / {1} · {2} records · 10 per page|{0} / {1} ページ · 全 {2} 件 · 各 10 件
记录读取失败，不表示没有记录。|Record loading failed; this does not mean no records exist.|記録の取得失敗は、記録がないことを意味しません。
重试读取|Retry loading|再読込
宿主返回了不同范围，未将草稿应用到其他范围。|Host returned a different scope. Drafts were not applied to it.|ホストが異なる範囲を返しました。下書きは他の範囲に適用していません。
原生配置版本已变化。草稿保留，但需读取最新配置并复核后才能保存。|Native configuration changed. Draft retained; load and review the latest version before saving.|設定バージョンが変わりました。下書きは保持しています。最新設定を読み直して確認してください。
没有已授权范围|No authorized scopes|許可された範囲なし
更新于 {0}|Updated {0}|更新日時 {0}
此范围没有已授权会话|No authorized conversations in this scope|この範囲に許可された会話はありません
人格全局 · 仅管理查看|Persona global · management view only|人格全体 · 管理閲覧のみ
{0} · 全部已授权会话|{0} · all authorized conversations|{0} · 許可された全会話
群聊|Group|グループ
私聊|Private|個別
已读取最新原生配置，草稿尚未提交。请逐项复核后保存。|Latest configuration loaded; draft not submitted. Review each change before saving.|最新設定を取得しました。下書きは未送信です。項目を確認して保存してください。
读取失败|Loading failed|読込失敗
无法读取状态。请确认宿主登录、插件加载与页面 API 能力。|Cannot load state. Check host sign-in, plugin loading and page API support.|状態を取得できません。ログイン、プラグイン読込、ページ API を確認してください。
旧快照 · 写操作已停用|Old snapshot · writes disabled|古い状態 · 書込無効
配置回执缺少版本，请核对宿主记录。|Configuration receipt lacks a revision; check host records.|設定の応答にバージョンがありません。ホスト記録を確認してください。
已保存到原生配置。|Saved to native configuration.|ネイティブ設定に保存しました。
配置已保存，但当前范围状态未能刷新。请手动刷新核对，不要重复保存。|Configuration saved, but scope refresh failed. Refresh manually; do not save again.|設定は保存済みですが状態更新に失敗しました。手動更新で確認し、重複保存しないでください。
状态已改变，请取消并重新核对操作。|State changed. Cancel and review the action again.|状態が変わりました。キャンセルして操作を再確認してください。
请填写操作原因。|Provide an action reason.|操作理由を入力してください。
动作回执无效，执行结果不明，请核对记录。|Invalid action receipt; result unknown. Check records.|操作の応答が無効で結果は不明です。記録を確認してください。
操作结果：{0}。{1}{2}|Action result: {0}. {1}{2}|操作結果：{0}。{1}{2}
 请求 ID：{0}| Request ID: {0}| 要求 ID：{0}
操作已返回 · 请刷新核对状态|Action returned · refresh to verify state|操作が返りました · 更新して状態を確認
正在读取新范围…|Loading new scope…|新しい範囲を読込中…
正在读取所选人格与范围…|Loading selected persona and scope…|選択した人格と範囲を読込中…
已放弃本页未保存更改。|Unsaved changes discarded.|未保存の変更を破棄しました。
人格|Persona|人格
情绪|Emotion|感情
关系|Relationships|関係
主动行为|Proactive behavior|自発行動
日记与梦境|Diary & dreams|日記と夢
设置|Settings|設定
愉悦|Pleasure|快感
唤醒|Arousal|覚醒
压力|Stress|ストレス
社交需求|Social need|交流欲求
底气|Poise|自信
保守|Conservative|控えめ
激进|Aggressive|積極的
情绪与五维指标说明|Emotion and five-dimension metric guide|感情と五次元指標の説明
数字表示 TA 当前情绪的强弱。点每行右侧的问号，可以看到这个数值为什么会升降。|The numbers show how strong TA's emotions are right now. Click the question mark on each row to see why the value rises or falls.|数値は TA の現在の感情の強さを表します。各行の右側の「?」を押すと、その値が上下する理由が表示されます。
指标|Metric|指標
什么情况下升高|When it rises|上がるとき
什么情况下回落|When it falls|下がるとき
回落速度|Recovery speed|戻る速さ
信号|Signal|シグナル
识别方式|Detected by|検出方法
查看{0}的说明|View the explanation for {0}|{0} の説明を見る
当前档位「{0}」：单次变化最多 {1}，同一类刺激 5 分钟内累计最多 {2}；换档位等比放大，衰减速度不变。|Current preset "{0}": up to {1} per event and {2} per stimulus type within 5 minutes. Other presets scale proportionally; decay speed is unchanged.|現在のプリセット「{0}」：1 回の変化は最大 {1}、同じ種類の刺激は 5 分間に最大 {2}。プリセットを変えると比例して拡大し、減衰速度は変わりません。
表中是「{0}」档的生效增量；没有新的互动时，这些数值会随着时间慢慢回落到平常水平。|The table shows effective deltas for the "{0}" preset; without new interactions the values slowly return to their usual level.|表は「{0}」プリセットの実効増分です。新しい交流がないと、値は時間とともに平常水準へ戻ります。
手动入睡|Put to sleep|手動で入眠
变更作息状态。不会在此页面直接发送晚安。|Change sleep state. This page does not directly send goodnight messages.|睡眠状態を変更します。このページから直接おやすみの挨拶を送信しません。
手动叫醒|Wake up|手動で起こす
变更作息状态；后续行为仍须通过单一执行端与硬闸门。|Change sleep state; subsequent actions still pass the executor and hard gates.|睡眠状態を変更します。後続の行動は実行系と厳格な制限に従います。
生成私人日记|Generate private diary|非公開日記を生成
可能调用模型并消耗额度。只生成私人内容，不发送到聊天。|May call a model and consume quota. Generates private content without sending to chat.|モデルを呼び出し枠を消費する場合があります。非公開内容を生成し、チャットには送信しません。
生成梦境|Generate dream|夢を生成
立即生成一段梦境：不要求睡够时长或处于 REM，按最近 24 小时的素材来写。可能调用模型并消耗额度，内容始终是想象。|Generates a dream right away: no need to have slept long enough or be in REM; it draws on the last 24 hours of material. It may call the model and use quota; the content is always imaginary.|その場で夢を 1 つ生成します。睡眠時間や REM の条件は不要で、直近 24 時間の素材から書きます。モデル呼び出しと枠を消費する場合があり、内容は常に想像です。
生成并真实发送|Generate and actually send|生成して実際に送信
可能调用模型并向当前范围真实发送消息。硬否决仍生效；结果不明时不要重复执行。|May call a model and send a real message to this scope. Hard vetoes apply; do not repeat unknown results.|モデルを呼び、現在の範囲に実際に送信する場合があります。拒否条件に従い、結果不明時は繰り返さないでください。
修改置顶|Change pin|固定状態を変更
保存这篇日记或梦境的置顶状态，不调用模型。取消置顶后按原创建日期恢复保留规则。|Save the pin state without model calls. Unpinning restores retention based on the original creation date.|モデルを呼ばず固定状態を保存します。解除後は元の作成日による保存規則に戻ります。
开启|On|有効
关闭|Off|無効
清醒|Awake|起きている
小憩|Napping|昼寝
恍惚|Groggy|ぼんやり
困|Drowsy|眠い
沉睡|Deep sleep|深い眠り
时间无效|Invalid time|無効な時刻
疏远|Distant|疎遠
冷淡|Cool|冷淡
平常|Ordinary|普通
相识|Acquainted|知り合い
熟悉|Familiar|馴染み
友好|Friendly|友好的
亲近|Close|親しい
信赖|Trusted|信頼
知己|Confidant|理解者
挚友|Best friend|親友
特殊关系|Special relationship|特別な関係
阶段名称必须是包含11个字符串的JSON数组，每个名称最多100字符。|Stage names must be a JSON array of 11 strings, at most 100 characters each.|段階名は 11 個の文字列からなる JSON 配列で、各 100 文字以内にしてください。
未建立|Not established|未成立
喜悦|Joy|喜び
愤怒|Anger|怒り
悲伤|Sadness|悲しみ
恐惧|Fear|恐れ
惊讶|Surprise|驚き
关爱|Affection|愛情
情感效价|Valence|感情価
掌控感|Control|制御感
确定感|Certainty|確実性
平静|Calm|穏やか
开心|Happy|嬉しい
焦虑|Anxious|不安
疲惫|Tired|疲れ
兴奋|Excited|興奮
关切|Caring|気遣い
孤独|Lonely|孤独
满足|Content|満足
内容已生成。|Content generated.|内容を生成しました。
操作已完成。|Action completed.|操作が完了しました。
置顶状态已更新。|Pin state updated.|固定状態を更新しました。
本周期已有记录，不重复生成。|A record exists for this cycle; no duplicate generation.|この周期には記録があり、重複生成しません。
记录已存在，不重复生成。|Record exists; no duplicate generation.|記録があるため重複生成しません。
模型不可用，请检查模型配置。|Model unavailable; check configuration.|モデルが利用できません。設定を確認してください。
尚未配置模型。|No model configured.|モデルが未設定です。
没有可用素材，不会编造经历。|No usable sources; experiences will not be invented.|利用可能な素材がなく、体験を創作しません。
有效素材不足，暂不生成。|Insufficient valid sources; generation skipped.|有効な素材が不足し、生成を見送ります。
模型预算已用完。|Model budget exhausted.|モデル予算を使い切りました。
已达到每日额度。|Daily limit reached.|1 日の上限に達しました。
本周期额度已用完。|Cycle quota exhausted.|この周期の枠を使い切りました。
已达到本夜梦境上限。|Nightly dream limit reached.|今夜の夢の上限に達しました。
当前未处于允许生成梦境的睡眠阶段。|Current sleep phase does not allow dreams.|現在は夢の生成が許される睡眠段階ではありません。
此功能已关闭。|Feature disabled.|機能は無効です。
结果不明，请核对记录，不要重复执行。|Unknown result. Check records; do not repeat.|結果不明です。記録を確認し、繰り返さないでください。
自主发送已关闭。|Autonomous sending is off.|自発送信は無効です。
观察模式不自主发送。|Observe-only mode does not send autonomously.|観察モードでは自発送信しません。
仍在冷却时间内。|Cooldown is still active.|クールダウン中です。
睡眠限制仍生效。|Sleep restrictions apply.|睡眠制限が適用されています。
聊天仍活跃，暂不插话。|Conversation is active; do not interrupt.|会話中のため割り込みません。
后端返回了此原因码，详细含义请核对宿主说明；页面不会绕过限制。|The backend returned this code. Check host documentation for details; restrictions are not bypassed.|バックエンドから返された理由コードです。詳細はホストの説明を確認してください。制限は回避しません。
页面 API 版本不兼容，需要 api_version=1。|Incompatible page API version; api_version=1 required.|ページ API のバージョン非互換です。api_version=1 が必要です。
当前范围不在已授权列表内。|Current scope is not authorized.|現在の範囲は許可リストにありません。
记录分页响应不符合 v1 契约，未显示不完整数据。|Invalid v1 record pagination; incomplete data hidden.|記録のページ応答が v1 契約に違反しているため、不完全なデータを非表示にしました。
请选择有效选项。|Select a valid option.|有効な選択肢を選んでください。
请输入范围内的有效数值。|Enter a valid number within range.|範囲内の有効な数値を入力してください。
请按 {0} 的步进输入。|Use increments of {0}.|{0} 刻みで入力してください。
此字段类型暂不支持编辑。|This field type cannot be edited yet.|この項目の種類はまだ編集できません。`;
const more = `关系阶段自定义名称|Custom relationship stage names|関係段階のカスタム名
启用 livingEmotion|Enable livingEmotion|livingEmotion を有効化
工作模式|Operating mode|動作モード
人格解析方式|Persona resolution|人格の解決方法
原生人格|Native persona|ネイティブ人格
状态模式|State mode|状態モード
同一人格共享状态|Share state within a persona|同一人格で状態を共有
状态归属模式|State ownership mode|状態の帰属モード
默认生成模型|Default generation model|既定の生成モデル
使用 LivingMemory|Use LivingMemory|LivingMemory を使用
允许 TA 睡眠|Allow TA to sleep|TA の睡眠を許可
本地 IANA 时区|Local IANA timezone|ローカル IANA タイムゾーン
TA 住所城市|TA home city|TA の居住都市
模型细化情绪|Model-assisted emotions|モデルによる感情の詳細化
情绪模型|Emotion model|感情モデル
每日模型预算|Daily model budget|1 日のモデル予算
模型并发上限|Model concurrency limit|モデル同時実行上限
每日 Token 预算|Daily token budget|1 日のトークン予算
允许主动找人|Allow proactive contact|自発的な連絡を許可
主动行为模型|Proactive behavior model|自発行動モデル
允许群聊主动行为|Allow proactive group messages|グループでの自発発言を許可
午休开始|Nap starts|昼寝開始
午休结束|Nap ends|昼寝終了
夜间疲劳开始|Night fatigue starts|夜間疲労開始
夜间疲劳结束|Night fatigue ends|夜間疲労終了
沉睡时间|Deep sleep time|深い眠りの時刻
基础起床时间|Base wake time|基本起床時刻
聊天唤醒规则|Chat wake rules|チャットによる起床規則
唤醒回复轮数|Wake reply limit|起床後の返信回数
唤醒窗口|Wake window|起床ウィンドウ
赖床最短时间|Minimum lie-in time|最短の二度寝時間
赖床最长时间|Maximum lie-in time|最長の二度寝時間
每次回复消耗|Cost per reply|返信ごとの消費
疲劳每分钟消耗|Fatigue cost per minute|1 分ごとの疲労消費
每分钟恢复|Recovery per minute|1 分ごとの回復
精力上限（固定）|Energy cap (fixed)|活力上限（固定）
睡前晚安|Bedtime goodnight|就寝前の挨拶
道别语随机生成|Generate varied farewells|別れの挨拶をランダム生成
收尾模型|Closing model|締めくくりモデル
醒后阅读未读|Read unread messages on waking|起床後に未読を読む
醒后历史补答|Reply to history on waking|起床後に過去の会話へ返信
补课模型|Catch-up model|振り返りモデル
自动私人日记|Automatic private diary|非公開日記の自動生成
日记模型|Diary model|日記モデル
自动梦境|Automatic dreams|夢の自動生成
梦境模型|Dream model|夢モデル
记忆后端|Memory backend|記憶バックエンド
允许记忆检索|Allow memory retrieval|記憶の検索を許可
允许记忆写入|Allow memory writes|記憶への書込を許可
原生向量模型|Native embedding model|ネイティブ埋め込みモデル
参与表达与行为|Enable expression and behavior|表現と行動に参加
仅观察|Observe only|観察のみ
停用|Disable|無効化
跟随原生会话|Follow native conversation|ネイティブ会話に従う
指定原生人格|Select native persona|ネイティブ人格を指定
未启用|Not enabled|未有効
私聊可叫醒|Private chat can wake|個別チャットで起こせる
聊天不可叫醒|Chat cannot wake|チャットでは起こせない
私聊或群聊原生 @|Private chat or native group mention|個別またはグループのネイティブメンション
按真实会话独立|Separate by real conversation|実際の会話ごとに独立
快速开始|Quick start|クイックスタート
人格与状态模式|Persona and state mode|人格と状態モード
记忆|Memory|記憶
其他高级设置|Other advanced settings|その他の詳細設定
作息时间未完整配置，不能计算预览。|Sleep times are incomplete; preview unavailable.|睡眠時刻の設定が不完全で、プレビューできません。
沉睡时间应位于夜间开始与基础起床之间，请核对跨午夜顺序。|Deep sleep must fall between night start and base wake time. Check midnight ordering.|深い眠りの時刻は夜間開始と基本起床の間にしてください。日付をまたぐ順序を確認してください。
次日 |Next day |翌日 
当日 |Same day |当日 
本地 {0}：夜间 {1} → 恍惚转困 {2} → 沉睡 {3} → 基础起床 {4}。实际起床另加本周期持久赖床值，不在页面重抽。|Local {0}: night {1} → drowsy {2} → deep sleep {3} → base wake {4}. Actual wake adds the stored cycle lie-in; this page does not redraw it.|現地 {0}：夜間 {1} → 眠気 {2} → 深い眠り {3} → 基本起床 {4}。実際の起床には保存済みの二度寝時間を加え、ページでは再抽選しません。
时区未配置|Timezone not configured|タイムゾーン未設定
一份原生配置，一次保存。普通分区只阅读状态；以下更改统一提交到 AstrBot。|One native configuration, one save. Other sections show state; changes below are submitted together to AstrBot.|同じネイティブ設定を一度に保存します。各画面は状態を表示し、以下の変更をまとめて AstrBot に送信します。
来源：{0} · 版本 {1}|Source: {0} · revision {1}|出典：{0} · バージョン {1}
展开模块配置|Expand module settings|モジュール設定を展開
知道了|Got it|了解
配置说明|Configuration help|設定の説明
填写与使用示例|Input and usage examples|入力・使用例
宿主未提供可编辑字段，请检查原生配置能力。|No editable fields provided; check native configuration support.|編集可能な項目がありません。ネイティブ設定機能を確認してください。
高级设置 · 预算、阈值与边界|Advanced · budgets, thresholds and limits|詳細設定 · 予算・閾値・制限
跟随当前会话人格|Follow current conversation persona|現在の会話人格に従う
待配置|Setup required|要設定
沿用当前聊天模型|Use current chat model|現在のチャットモデルを使用
更改由宿主校验并写回原生配置。|The host validates changes and saves native configuration.|変更はホストが検証し、ネイティブ設定に保存します。
更改后保存到原生配置，由宿主校验。|Save changes to native configuration for host validation.|変更をネイティブ設定に保存し、ホストが検証します。
当前值为“{0}”。按此项类型填写并保存，实际效果受相关模块开关影响。|Current value: “{0}”. Enter the expected type and save; related module switches affect behavior.|現在値は「{0}」です。項目の型に合わせて入力・保存してください。動作は関連モジュールの設定にも依存します。
{0}：详细说明和示例|{0}: details and examples|{0}：詳細説明と例
单位：{0}|Unit: {0}|単位：{0}
本地向量（待配置）|Local vectors (setup required)|ローカルベクトル（要設定）
当前值：{0}|Current value: {0}|現在値：{0}
5档关系名称 · 留空使用默认名称|5 relationship stages · blank uses default|5 段階の関係名 · 空欄で既定名
100 · 独特（管理员设置）|100 · unique (admin only)|100 · 特別（管理者設定）
阶段名称必须是包含5个字符串的JSON数组，每个名称最多100字符。|Stage names must be a JSON array of 5 strings, up to 100 characters each.|段階名は各100文字以内の文字列5個のJSON配列です。
反感|Aversion|嫌悪
陌生|Unfamiliar|見知らぬ
独特|Unique|特別
LivingMemory 已启用：向量模型由 LivingMemory 管理，本地原生向量模型暂不可编辑。当前值会保留，关闭 LivingMemory 后可继续使用。|LivingMemory is enabled and manages embeddings. Local embedding settings are disabled but retained for use after disabling LivingMemory.|LivingMemory が埋め込みを管理するためローカル設定は編集できません。現在値は保持し、無効化後に再利用できます。
请输入5至20位QQ/群号，多个用逗号或空格分隔，最多100个。|Enter 5–20 digit QQ/group IDs, comma or space separated, at most 100.|5～20 桁の QQ・グループ番号をカンマか空白で区切り、100 件以内で入力してください。
留空=所有已知QQ群；多个群号用逗号分隔|Blank = all known QQ groups; separate IDs with commas|空欄＝既知の全 QQ グループ。複数はカンマ区切り
输入QQ号码，多个用逗号分隔|Enter QQ IDs, comma separated|QQ 番号をカンマ区切りで入力
从已知QQ群追加群号|Append a known QQ group|既知の QQ グループを追加
从已知QQ私聊追加号码|Append a known QQ private contact|既知の QQ 個別連絡先を追加
下拉追加已知群号…|Append known group…|既知のグループを追加…
下拉追加已知QQ…|Append known QQ contact…|既知の QQ を追加…
QQ群|QQ group|QQ グループ
精力上限固定 100，不可修改。|The energy cap is fixed at 100.|活力の上限は 100 固定で変更できません。
作息预览：{0} · 恍惚转困 {1} · 实际起床 {2}|Sleep preview: {0} · drowsy {1} · actual wake {2}|睡眠プレビュー：{0} · 眠気 {1} · 実際の起床 {2}
以上是配置顺序预览，不代表当前周期的持久实际起床时刻。最终作息以宿主状态与校验为准。|This previews configured ordering, not the stored wake time of the current cycle. Host state and validation are authoritative.|これは設定順序のプレビューで、現在の周期に保存された起床時刻ではありません。最終的な睡眠状態はホストに従います。
宿主请求失败，请检查插件连接。|Host request failed; check plugin connection.|ホスト要求に失敗しました。接続を確認してください。
宿主返回了无效响应。|Host returned an invalid response.|ホストが無効な応答を返しました。
宿主响应缺少数据。|Host response is missing data.|ホスト応答にデータがありません。
未检测到 AstrBot 页面连接。请从已登录的宿主插件详情页打开。|No AstrBot page bridge detected. Open from the signed-in host plugin details.|AstrBot のページ接続がありません。ログイン済みホストのプラグイン詳細から開いてください。
请求超时，执行结果不明。请核对记录，不要重复提交。|Request timed out; execution is unknown. Check records; do not resubmit.|タイムアウトで実行結果が不明です。記録を確認し、再送信しないでください。
读取超时，请手动刷新。|Loading timed out; refresh manually.|読込がタイムアウトしました。手動で更新してください。
TA 情绪雷达，实线为当前，虚线为领域基准；数值见下方|TA emotion radar. Solid: current; dashed: domain baseline. Values below.|TA の感情レーダー。実線は現在、破線は基準。数値は下に表示します
当前维度未完整采集|Current dimensions are incomplete|現在の次元データが不完全です
实线 当前 · 虚线 真实基准|Solid: current · dashed: actual baseline|実線：現在 · 破線：実際の基準
基准 {0}|Baseline {0}|基準 {0}
领域基准未提供，不绘制虚构基准。|No domain baseline provided; none is fabricated.|基準が未提供のため、架空の基準は描画しません。
↑ 表示高于基准，不代表改善；压力升高同样需要留意。|↑ means above baseline, not improvement; higher stress also deserves attention.|↑ は基準より高いことを示し、改善とは限りません。ストレス上昇にも注意が必要です。
关系响应不符合管理契约。|Relationship response violates the management contract.|関係の応答が管理契約に違反しています。
平台账号或昵称|Platform account or nickname|プラットフォームのアカウント・表示名
全部平台|All platforms|全プラットフォーム
查找关系|Find relationships|関係を検索
平台|Platform|プラットフォーム
账号搜索 · 包含未绘制节点|Account search · includes unplotted nodes|アカウント検索 · 未描画の人物も含む
正在读取关系…|Loading relationships…|関係を読込中…
人格中心三维关系图，可拖动旋转，选择人物查看详情|Persona-centred 3D relationship graph; drag to rotate and pick a person for details|人格を中心とする 3D 関係図。ドラッグで回転し、人物を選ぶと詳細を表示します
暂停布局|Pause layout|配置を一時停止
继续布局|Resume layout|配置を再開
放大|Zoom in|拡大
缩小|Zoom out|縮小
复位视图|Reset view|表示をリセット
选中账号详情|Selected account details|選択アカウントの詳細
未记录昵称|No nickname recorded|表示名の記録なし
亲近阶段|Relationship stage|関係段階
好感|Affinity|好感度
信任|Trust|信頼
边界|Boundaries|境界
来源完整性|Source completeness|出典の完全性
真实来源会话|Actual source conversations|実際の出典会話
未提供来源会话，不推测关系维度。|No source conversations; relationship dimensions are not inferred.|出典会話がないため関係の次元を推測しません。
与其他人的关系线索|Relationship clues with others|他者との関係の手掛かり
根据陈述推测，可展开核对依据。|Inferred from statements; expand to verify evidence.|発言からの推測です。展開して根拠を確認できます。
{0} · {1}（推测）|{0} · {1} (inferred)|{0} · {1}（推測）
{0} · 来源 {1}|{0} · source {1}|{0} · 出典 {1}
时间未提供|Time not provided|時刻の提供なし
保存此账号好感|Save account affinity|このアカウントの好感度を保存
读取最新关系并复核|Load latest relationship and review|最新の関係を取得して確認
好感 · 0–100，步进 0.1|Affinity · 0–100, step 0.1|好感度 · 0–100、0.1 刻み
冻结自动好感变化|Freeze automatic affinity changes|自動好感度変化を固定
修改原因（必填）|Change reason (required)|変更理由（必須）
只修改当前人格的这个平台账号。操作者由宿主认证注入，不修改其他平台的同号账号。|Changes only this account for the current persona. The host authenticates the actor; same-number accounts on other platforms are unchanged.|現在の人格のこのアカウントのみ変更します。操作者はホストが認証し、他プラットフォームの同番号は変更しません。
好感已保存，正在重新读取真实关系。|Affinity saved; reloading actual relationship.|好感度を保存し、実際の関係を再取得しています。
关系版本已变化。草稿保留，请读取最新关系并人工复核；未自动重试。|Relationship revision changed. Draft retained; load and review it. No automatic retry.|関係のバージョンが変わりました。下書きは保持しています。最新の関係を取得して確認してください。自動再試行はしません。
结果不明，已禁止重复提交。|Unknown result; duplicate submission blocked.|結果不明のため重複送信を禁止しました。
未保存。|Not saved.|未保存。
{0}（推测，{1}条依据）|{0} (inferred, {1} evidence items)|{0}（推測、根拠 {1} 件）
{0} {1}，好感 {2}|{0} {1}, affinity {2}|{0} {1}、好感度 {2}
关系表，可左右滚动；每页10条|Relationship table; scroll horizontally, 10 per page|関係表。左右スクロール可能、各ページ 10 件
平台 / 账号|Platform / account|プラットフォーム / アカウント
昵称|Nickname|表示名
详情|Details|詳細
查看 / 修改|View / edit|表示 / 編集
未记录|Not recorded|記録なし
当前范围暂无符合条件的关系。可以清空搜索或切换平台。|No matching relationships. Clear search or change platform.|一致する関係がありません。検索を消すかプラットフォームを切り替えてください。
第 {0} 页 · 共 {1} 人 · 每页 10 条|Page {0} · {1} people · 10 per page|{0} ページ · 全 {1} 人 · 各 10 件
已展示 {0} / {1} 人 · {2} 条人物关系线索 · 虚线为推测，选择人物查看依据|Showing {0} / {1} people · {2} relationship clues · dashed lines are inferred; select a person for evidence|{0} / {1} 人を表示 · 関係の手掛かり {2} 件 · 破線は推測。人物を選ぶと根拠を表示
关系读取失败，不表示关系为空。|Relationship loading failed; this does not mean none exist.|関係の取得失敗は、関係がないことを意味しません。
重试读取关系|Retry relationships|関係を再取得
回复消耗|Reply cost|返信消費
疲劳消耗|Fatigue cost|疲労消費
恢复|Recovery|回復
入睡|Sleep|入眠
手动|Manual|手動
配置|Configuration|設定
精力日志响应不符合管理契约。|Energy log response violates the management contract.|活力ログの応答が管理契約に違反しています。
精力日志时区无效，未推测事件时间。|Invalid energy timezone; event times are not inferred.|活力ログのタイムゾーンが無効です。時刻は推測しません。
最近24小时真实精力时间线，精力上限100，逐事件数值见下表|Actual energy in the last 24 hours; cap 100. Event values in the table below.|直近 24 時間の実際の活力。上限 100、イベント値は下の表を参照
真实时点 · {0} 至 {1} · 时区 {2} · 上限 100{3} · 竖线保留显示桶极值|Actual times · {0} to {1} · timezone {2} · cap 100{3} · vertical lines preserve bucket extrema|実際の時点 · {0} ～ {1} · タイムゾーン {2} · 上限 100{3} · 縦線は区間の最大・最小値
 · 各状态所有者分别连线，不合并精力| · state owners have separate lines; energy is not merged| · 状態の所有者ごとに別の線で表示し、活力は合算しません
最近24小时未采集精力历史，不补造连续曲线。|No energy history collected in the last 24 hours; no curve fabricated.|直近 24 時間の活力履歴がなく、連続曲線は補いません。
全部事件|All events|全イベント
筛选日志|Filter log|ログを絞り込む
事件类型|Event type|イベントの種類
最近 24 小时|Last 24 hours|直近 24 時間
曲线和逐事件表来自同一持久日志；没有采集的历史保持空白。|Curve and event table share the same persistent log. Uncollected history stays blank.|曲線と表は同じ永続ログから取得します。未収集の履歴は空欄です。
正在读取精力日志…|Loading energy log…|活力ログを読込中…
精力事件表，可左右滚动；每页10条|Energy event table; scroll horizontally, 10 per page|活力イベント表。左右スクロール可能、各 10 件
时点|Time|時点
事件 / 状态|Event / state|イベント / 状態
前 → 后|Before → after|前 → 後
变化|Change|変化
当前筛选暂无精力事件。旧历史未采集，不代表精力为零。|No matching energy events. Uncollected history does not mean zero energy.|一致する活力イベントがありません。履歴未収集は活力ゼロを意味しません。
精力日志读取失败，不表示没有历史。|Energy loading failed; this does not mean no history exists.|活力ログの取得失敗は、履歴がないことを意味しません。
重试读取日志|Retry log|ログを再取得`;
const shell = `livingEmotion · TA 的生活控制台|livingEmotion · TA life console|livingEmotion · TA の生活コンソール
跳到主要内容|Skip to main content|本文へスキップ
中文|中文|中文
日本語|日本語|日本語
页面主题|Page theme|ページテーマ
白昼|Day|昼
黑夜|Night|夜
等待原生人格|Waiting for native persona|ネイティブ人格を待機中
查看范围|View scope|表示範囲
全局|Global|全体
当前范围|Current scope|現在の範囲
等待宿主提供范围|Waiting for host scopes|ホストの範囲を待機中
正在连接宿主|Connecting to host|ホストに接続中
刷新状态|Refresh state|状態を更新
管理分区|Management sections|管理セクション
等待状态|Waiting for state|状態を待機中
正在读取已授权的状态…|Loading authorized state…|許可された状態を読込中…
历史记录|History|履歴
保存原生配置|Save native configuration|ネイティブ設定を保存
待保存更改|Unsaved changes|未保存の変更
直接写回同一份 AstrBot 原生配置。刷新状态保留本页草稿；刷新浏览器会放弃未保存草稿。|Writes to the same AstrBot native configuration. Refreshing state retains drafts; reloading the browser discards unsaved drafts.|同じ AstrBot ネイティブ設定に書き込みます。状態更新では下書きを保持し、ブラウザー再読込では破棄します。
读取最新配置并复核草稿|Load latest configuration and review draft|最新設定を取得して下書きを確認
放弃更改|Discard changes|変更を破棄
livingEmotion / 私人生活档案|livingEmotion / Private life archive|livingEmotion / 非公開の生活記録
主观状态不等于真实事实|Subjective states are not factual claims|主観的な状態は事実とは限りません
MANUAL ACTION / 手动操作|MANUAL ACTION|MANUAL ACTION / 手動操作
操作原因（必填）|Action reason (required)|操作理由（必須）
确认执行一次|Confirm one execution|1 回の実行を確認
取消|Cancel|キャンセル
管理页面需要 JavaScript 才能通过宿主读取数据；不会显示缓存或演示状态。|JavaScript is required to read data through the host. No cached or demo state is displayed.|ホストからのデータ取得には JavaScript が必要です。キャッシュやデモ状態は表示しません。
TA 的生活控制台|TA life console|TA の生活コンソール
仅本次页面有效|This page only|このページのみ有効
已记住偏好|Preference saved|設定を保存済み
跟随系统|Follow system|システムに従う
启用插件|Enable plugin|プラグインを有効化
运行模式|Operating mode|動作モード
备用生成模型|Fallback generation model|予備の生成モデル
静默范围|Muted scopes|ミュート範囲
自动作息|Automatic sleep schedule|自動睡眠スケジュール
日记生成时间|Diary time|日記生成時刻
补写昨天日记|Backfill yesterday's diary|昨日の日記を補完
调度间隔|Scheduler interval|スケジューラー間隔
免打扰开始|Do-not-disturb starts|通知抑制開始
免打扰结束|Do-not-disturb ends|通知抑制終了
主动时段开始|Active window starts|自発行動時間の開始
主动时段结束|Active window ends|自発行動時間の終了
每日主动行为总额度|Daily proactive attempt limit|1 日の自発行動総上限
每个会话每日主动额度|Daily proactive limit per conversation|会話ごとの 1 日の自発行動上限
主动行为冷却|Proactive cooldown|自発行動クールダウン
未回应次数上限|Unanswered attempt limit|未応答回数の上限
随机等待最短时间|Minimum random wait|最短ランダム待機時間
随机等待最长时间|Maximum random wait|最長ランダム待機時間
聊天结束后安静时间|Quiet time after conversation|会話後の待機時間
主动节奏|Proactive style|自発行動の調子
允许分享心情|Allow sharing feelings|気持ちの共有を許可
主动聊天模型|Proactive chat model|自発チャットモデル
日记重试次数|Diary retry limit|日記の再試行上限
每夜梦境上限|Dream limit per night|夜ごとの夢の上限
日记保留时间|Diary retention|日記保存期間
梦境保留时间|Dream retention|夢の保存期間
梦境清晰度半衰期|Dream clarity half-life|夢の鮮明度の半減期
日记与梦境字数上限|Diary and dream character limit|日記と夢の文字数上限
模型队列上限|Model queue capacity|モデル待ち行列の上限
每日模型调用上限|Daily model call limit|1 日のモデル呼出上限
情绪分析间隔|Emotion analysis interval|感情分析の間隔
模型输入上限|Model input token limit|モデル入力トークン上限
模型输出上限|Model output token limit|モデル出力トークン上限
模型调用超时|Model request timeout|モデル要求タイムアウト
聊天素材保留时间|Chat source retention|会話素材の保存期間
每个会话素材上限|Source limit per conversation|会話ごとの素材上限
全部素材上限|Total source limit|全素材の上限
单条素材字数上限|Characters per source|素材ごとの文字数上限
事件保留时间|Event retention|イベント保存期間
启用午休|Enable nap|昼寝を有効化
最少赖床时间|Minimum lie-in|最短の二度寝
最多赖床时间|Maximum lie-in|最長の二度寝
聊天唤醒方式|Chat wake mode|チャット起床モード
晚安提前量|Goodnight lead time|就寝挨拶の先行時間
主动私聊 QQ 号码|Proactive private QQ IDs|自発連絡する個別 QQ 番号
主动发言 QQ 群号|Proactive QQ group IDs|自発発言する QQ グループ番号
主动联系QQ|Proactive QQ contacts|自発連絡する QQ
主动联系QQ群|Proactive QQ groups|自発連絡する QQ グループ
轻柔|Gentle|穏やか
自然|Balanced|自然
活泼|Lively|活発
秒|seconds|秒
分钟|minutes|分
天|days|日
次|attempts|回
点|points|ポイント
点/分钟|points/minute|ポイント/分
点/次|points/reply|ポイント/回
后端原始说明|Original backend help|バックエンドの原文説明
配置读取失败，写操作已停用。|Configuration loading failed; writes disabled.|設定の読込に失敗し、書き込みを無効にしました。
配置端点未提供，使用状态中的配置快照。|Configuration endpoint unavailable; using the state configuration snapshot.|設定エンドポイントがなく、状態内の設定スナップショットを使用します。
生成功能已关闭或当前模式不允许生成。|Generation is disabled or unavailable in the current mode.|生成が無効か、現在のモードでは生成できません。
梦境需要当前有效的 REM 睡眠阶段，不能使用离线或过期状态。|Dreams require a current, valid REM sleep phase; offline or stale state cannot be used.|夢には現在有効な REM 睡眠段階が必要で、オフラインや期限切れの状態は使えません。
无法重新验证睡眠状态，暂不生成梦境。|Sleep state cannot be revalidated; dream generation is paused.|睡眠状態を再検証できないため、夢の生成を停止しています。
已达到日记或本周期梦境的尝试上限。|The diary or current sleep-cycle dream attempt limit has been reached.|日記または現在の睡眠周期の夢の試行上限に達しました。
内容已保存。|Content saved.|内容を保存しました。
没有符合来源权限和有效期要求的素材。|No materials meet source authorization and validity requirements.|出典の権限と有効期限を満たす素材がありません。
生成模型或 Token 计数能力不可用。|The generation model or token counter is unavailable.|生成モデルまたはトークン計数機能が利用できません。
尚未到计划日记时间。|The scheduled diary time has not arrived.|予定した日記時刻にはまだ達していません。
补写日期超出允许范围。|The backfill date is outside the permitted range.|補完する日付が許可範囲外です。
日记日期无效。|The diary date is invalid.|日記の日付が無効です。
手动生成参数无效。|Manual generation parameters are invalid.|手動生成の引数が無効です。
会话范围或版本已变化，请刷新后核对。|The conversation scope or revision changed. Refresh and review.|会話範囲またはバージョンが変わりました。更新して確認してください。
素材依据已变化，已停止本次生成。|Source evidence changed; this generation was stopped.|素材の根拠が変わったため、今回の生成を停止しました。
会话范围或素材依据已变化，已停止本次生成。|Conversation scope or source evidence changed; this generation was stopped.|会話範囲または素材の根拠が変わったため、今回の生成を停止しました。
素材范围版本不一致，无法生成。|Material scope revisions do not match; generation cannot proceed.|素材範囲のバージョンが一致しないため生成できません。
生成准备失败，请检查宿主记录。|Generation preparation failed. Check the host records.|生成準備に失敗しました。ホストの記録を確認してください。
宿主不支持此次跨范围保存。|The host does not support this cross-scope save.|ホストは今回の範囲をまたぐ保存に対応していません。
素材超出模型输入上限（已自动压缩；仍失败请到设置里调大「模型输入上限」）。|Material exceeds the model input limit (it is auto-compressed; if it still fails, raise the model input limit in settings).|素材がモデルの入力上限を超えています（自動で圧縮します。それでも失敗する場合は設定で「モデル入力上限」を上げてください）。
模型输入上限太小，装不下系统提示与人格；请到设置里调大「模型输入上限」。|The model input limit is too small to hold the system prompt and persona; raise the model input limit in settings.|モデルの入力上限が小さすぎて、システムプロンプトと人格が収まりません。設定で「モデル入力上限」を上げてください。
输出超出 Token 上限。|Output exceeds the token limit.|出力がトークン上限を超えています。
人格内容无效，无法生成。|Persona content is invalid; generation cannot proceed.|人格内容が無効なため生成できません。
模型响应无效，未保存生成内容。|The model response is invalid; generated content was not saved.|モデル応答が無効で、生成内容を保存しませんでした。
生成失败，请检查宿主记录和额度。|Generation failed. Check host records and quota.|生成に失敗しました。ホストの記録と枠を確認してください。
本次生成已取消。|This generation was cancelled.|今回の生成をキャンセルしました。
模型请求超时，结果不明，不自动重试。|The model request timed out; the result is unknown and will not be retried automatically.|モデル要求がタイムアウトし、結果は不明です。自動再試行しません。
已排队，稍后手动刷新状态和记录。|Queued. Manually refresh state and records later.|待ち行列に入りました。後で状態と記録を手動更新してください。
已有相同任务，不重复提交。|An identical task already exists; no duplicate submission.|同じタスクがあるため、重複送信しません。
任务状态已不再保留，请核对记录。|Task state is no longer retained. Check records.|タスク状態は保持されていません。記録を確認してください。
梦境仍可回忆，内容始终是想象。|The dream can still be recalled; its content remains imaginary.|夢はまだ思い出せますが、内容は常に想像です。
梦境已模糊，不展示细节。|The dream has faded; details are not displayed.|夢が曖昧になったため、詳細は表示しません。
梦境已淡忘，不补造细节。|The dream has been forgotten; details will not be invented.|夢を忘れているため、詳細を作り足しません。
已完成|Completed|完了
已生成|Generated|生成済み
已更新|Updated|更新済み
已跳过|Skipped|スキップ済み
已拒绝|Rejected|拒否済み
失败|Failed|失敗
已取消|Cancelled|キャンセル済み
结果不明|Unknown result|結果不明
等待执行|Pending|実行待ち
执行中|Running|実行中
受限|Blocked|制限中
关系阶段命名尚未由宿主开放；默认名称仍按分数显示。|The host has not exposed stage naming; default names are calculated from scores.|ホストは段階名の設定に未対応です。点数から既定名を表示します。
全局视图不展示即时状态|Global view has no live state|全体表示では即時状態を表示しません
全局共享的是人格层面的数值；具体某个人、某个群的情绪请切换查看范围。|Global shows persona-level numbers; switch the view scope to inspect one person or group.|全体表示は人格レベルの数値のみです。個人やグループの感情は表示範囲を切り替えてください。
作息|Schedule|作息
更新|Updated|更新
当前人格的五维情绪球|Current persona's five-dimension emotion sphere|現在の人格の五次元感情球
全局视图只显示共享的人格数值投影，不展示具体会话、账号或观察记录。要查看即时情绪，请在顶部「查看范围」选择私聊或群聊。|Global view only shows the shared persona projection, never a specific conversation, account or observation. To see live emotion, choose Private or Group in View scope above.|全体表示は共有された人格の投影のみで、特定の会話・アカウント・観察記録は表示しません。即時の感情は上の「表示範囲」で私聊かグループを選んでください。
宿主没有返回可用人格，无法在此切换。|The host returned no personas, so switching is unavailable here.|ホストが利用可能な人格を返さないため、ここでは切り替えできません。
切换人格|Switch persona|人格を切り替え
应用|Apply|適用
正在读取所选人格…|Reading the selected persona…|選択した人格を読み込み中…
人格由 AstrBot 原生解析；换人格会重新读取该人格的状态，不会改动聊天模型。|The persona is resolved natively by AstrBot. Switching reloads that persona's state and does not change the chat model.|人格は AstrBot が解決します。切り替えるとその人格の状態を読み直すだけで、チャットモデルは変更しません。
宿主没有返回这个人的「人格说明」（prompt）。请到 AstrBot 人格设置里填写，或确认当前范围能读取到人格。|The host returned no persona description (prompt). Fill it in AstrBot's persona settings, or check that this scope can read the persona.|ホストが人格説明（prompt）を返していません。AstrBot の人格設定で入力するか、この範囲で人格を読めるか確認してください。
说明状态|Description status|説明の状態
已读取 {0} 字|Read {0} characters|{0} 文字を読み取りました
前往设置修改人格相关选项|Go to settings for persona options|設定で人格オプションを変更
对此人的四维情绪球|4-axis emotion sphere for this person|この相手への四次元感情球
情绪概览|Emotion overview|感情の概要
归属类型|Ownership type|帰属タイプ
全局视图没有「某个人/某个群」的情绪；请在上方把查看范围切换为私聊或群聊。|Global view has no per-person or per-group emotion. Switch View scope above to Private or Group.|全体表示には個人・グループ単位の感情はありません。上の表示範囲を私聊かグループに切り替えてください。
情绪会随时间回落到基准，新的互动才会推动变化；打开页面本身不会调用模型。|Emotions decay toward the baseline over time; only new interactions move them. Opening this page never calls a model.|感情は時間とともに基準へ戻り、新しい交流だけが変化を起こします。ページを開くだけではモデルを呼びません。
时机分数 {0}{1}|Timing score {0}{1}|タイミングスコア {0}{1}
 · 门槛 {0}| · threshold {0}| · しきい値 {0}
判定明细（全部满足才会真实发送）|Gate details (all must pass before a real send)|判定の内訳（すべて満たした場合のみ実送信）
未提供判定明细。|No gate details were provided.|判定の内訳は提供されていません。
选择具体会话后可查看执行记录。|Select a specific conversation to see execution records.|具体的な会話を選ぶと実行記録を確認できます。
正在读取最近执行…|Reading the latest execution…|最新の実行を読み込み中…
还没有执行记录。|No execution record yet.|実行記録はまだありません。
执行记录读取失败，不代表没有发送。|Failed to read execution records; this does not prove nothing was sent.|実行記録の読み取りに失敗しました。送信が無い証明ではありません。
全部已授权会话（未限定 QQ 号或群号）|All authorized conversations (no QQ or group filter)|許可された全会話（QQ 番号・グループ番号の指定なし）
群：{0}|Groups: {0}|グループ：{0}
私聊：{0}|Private: {0}|私聊：{0}
这里只展示当前真实运行状态；要改节奏、模型和联系人，请到设置里的主动行为分组。|Only the real runtime state is shown here. Change pacing, models and contacts in the Behavior group of Settings.|ここには実際の稼働状態のみを表示します。ペース・モデル・連絡先は設定の自発行動グループで変更してください。
风格|Style|スタイル
今日额度|Today's quota|本日の割当
本会话额度|This conversation's quota|この会話の割当
剩余可发|Remaining sends|残り送信数
未回应|Unanswered|未応答
运行状态|Runtime state|稼働状態
是否满足发送条件|Eligible to send|送信条件を満たすか
暂不满足|Not yet|まだ満たしていません
时机分数|Timing score|タイミングスコア
最近检查|Last check|前回チェック
最近结果|Last result|前回の結果
检查间隔|Check interval|チェック間隔
{0} 分钟|{0} min|{0} 分
联系范围|Contact scope|連絡範囲
群聊主动|Group proactive|グループ自発
活跃时段|Active hours|活動時間帯
免打扰|Do not disturb|邪魔しない時間
当前阻塞原因|Current blockers|現在のブロック理由
逐条检查硬否决、额度、冷却与关系边界。模拟只算规则，不调用收费模型。|Checks hard vetoes, quotas, cooldown and relationship boundaries one by one. Simulation only evaluates rules and never calls a paid model.|ハード拒否・割当・クールダウン・関係境界を順に確認します。シミュレーションはルール計算のみで、課金モデルを呼びません。
真实发送与最近执行|Real send and latest execution|実送信と最新の実行
真实发送会调用模型并向当前范围发消息。结果写入记录；结果不明时不要重复执行。|A real send calls the model and posts to the current scope. The result is recorded; if it is unknown, do not retry blindly.|実送信はモデルを呼び現在の範囲へ送信します。結果は記録されます。不明な場合は再実行しないでください。
刷新最近执行|Refresh latest execution|最新の実行を更新
当前不允许这个操作。|This action is not allowed right now.|現在この操作は許可されていません。
操作结果：{0}。{1}|Result: {0}. {1}|結果：{0}。{1}
作息时间表已启用，配置的入睡、深睡、午休与起床时间从现在开始生效。|Schedule enabled. The configured sleep, deep-sleep, nap and wake times now take effect.|作息スケジュールを有効にしました。設定した入睡・深睡・昼寝・起床時刻が有効になります。
作息、精力与醒后补课。手动操作只改变作息状态，不会改动聊天内容。|Schedule, energy and post-wake catch-up. Manual actions only change the sleep state, never chat content.|作息・精力・起床後のキャッチアップ。手動操作は作息状態のみ変更し、チャット内容は変えません。
作息时间表|Schedule|作息スケジュール
已启用|Enabled|有効
聊天可用|Chat availability|チャット可否
受作息影响|Affected by schedule|作息の影響あり
不受作息影响|Not affected by schedule|作息の影響なし
当前周期|Current cycle|現在のサイクル
周期类型|Cycle type|サイクル種別
午休|Nap|昼寝
夜间睡眠|Night sleep|夜間睡眠
入睡时刻|Sleep start|入睡時刻
深睡时刻|Deep sleep at|深睡時刻
赖床|Lie-in|寝坊
未抽到|Not drawn|未抽選
作息计划 · 来自设置|Schedule plan · from settings|作息計画 · 設定より
以下时间来自「设置 → 长夜」，与实际周期对应；改完设置保存后立即生效。|These times come from Settings → Night and match the real cycle; changes apply after saving.|以下の時刻は「設定 → 長夜」の値で、実際のサイクルに対応します。保存後すぐに反映されます。
夜间疲劳开始 / 结束|Fatigue start / end|夜間疲労の開始 / 終了
深睡（最晚入睡）|Deep sleep (latest sleep)|深睡（最終入睡）
基础起床|Base wake|基本起床
赖床范围|Lie-in range|寝坊の範囲
{0}–{1} 分钟|{0}–{1} min|{0}–{1} 分
聊天唤醒|Chat wake|チャット起床
仅私聊|Private only|私聊のみ
不可唤醒|Cannot wake|起こせない
私聊或群原生 @|Private or native group @|私聊またはグループ原生 @
{0} 轮 / {1} 分钟|{0} rounds / {1} min|{0} 往復 / {1} 分
允许睡眠影响聊天|Sleep affects chat|睡眠がチャットに影響
时区|Time zone|タイムゾーン
注意：作息时间表未启用，设置里的入睡 / 午休 / 深睡 / 起床时间目前不会自动生效，只有手动操作会改变作息。|Note: the schedule is disabled, so the configured sleep, nap, deep-sleep and wake times do not apply automatically. Only manual actions change the sleep state.|注意：作息スケジュールが無効のため、設定した入睡・昼寝・深睡・起床時刻は自動では反映されません。手動操作のみが作息を変えます。
启用作息时间表|Enable schedule|作息スケジュールを有効化
功能开关|Feature switch|機能スイッチ
补答开关|Reply switch|返信スイッチ
手动作息|Manual sleep control|手動の作息操作
手动入睡会直接进入睡眠；手动叫醒立即醒来，且不会修改精力值。两项都只执行一次。|Manual sleep enters sleep immediately; manual wake wakes at once and never changes energy. Each runs exactly once.|手動入睡はすぐに睡眠へ入り、手動叫醒は即座に起き、精力値は変更しません。どちらも一度だけ実行します。
现在就让 TA 去睡。|Put TA to sleep now.|今すぐ寝かせます。
立刻叫醒，不需要二次确认。|Wake immediately, no second confirmation.|すぐに起こします。二重確認はありません。
尚未触发|Not triggered yet|未実行
尚未生成|Not generated yet|未生成
还没有手动生成，也没到自动计划时间；点下方按钮可以立即生成一次。|Not generated manually yet and the scheduled time has not arrived; use the button below to generate once now.|手動生成は未実行で、自動予定時刻もまだです。下のボタンで一度だけ生成できます。
日记记录主观体会；梦境始终是想象。正文与来源只在已认证管理页阅读。|Diaries record subjective experience; dreams are always imagination. Body text and sources are readable only on this authenticated page.|日記は主観的な体験、夢は常に想像です。本文と出典は認証済みの管理ページでのみ閲覧できます。
日记生成|Diary generation|日記生成
梦境生成|Dream generation|夢生成
生成策略|Generation policy|生成ポリシー
只在明确启用后生成|Generate only after explicit enablement|明示的に有効化した後だけ生成
按钮变灰时会说明缺少什么；不会为了能点而放宽来源、睡眠阶段或预算校验。|A greyed button explains what is missing; source, sleep-stage and budget checks are never relaxed to make it clickable.|灰色のボタンは不足内容を示します。押せるようにするため出典・睡眠段階・予算の検証を緩めません。
当前不满足生成条件。|Generation conditions are not met.|生成条件を満たしていません。
宿主没有返回生成动作；请确认插件已启用并选择了具体会话。|The host returned no generation action; check that the plugin is enabled and a conversation is selected.|ホストが生成アクションを返していません。プラグインが有効で会話が選択されているか確認してください。
正在同步…|Syncing…|同期中…
同步未完成：{0}|Sync did not finish: {0}|同期が完了しませんでした：{0}
未知原因|unknown reason|不明な理由
已从 LivingMemory 读取 {0} 条记忆，保存 {1} 条到本地镜像。|Read {0} memories from LivingMemory and stored {1} in the local mirror.|LivingMemory から {0} 件を読み取り、{1} 件をローカルミラーに保存しました。
这里显示真实的记忆后端与能力；改后端请到「设置 → 记忆」。|This page shows the real memory backend and capabilities; change the backend in Settings → Memory.|ここには実際の記憶バックエンドと能力を表示します。変更は「設定 → 記憶」で行います。
后端|Backend|バックエンド
检索|Recall|検索
写入|Write|書き込み
当前后端|Current backend|現在のバックエンド
允许写入|Write allowed|書き込み許可
绑定人格|Bound persona|紐付け人格
未选择人格|No persona selected|人格未選択
状态说明|Status note|状態の説明
当前后端没有声明可用能力；不会用演示数据补位。|The backend declares no capabilities; demo data is never substituted.|バックエンドは能力を宣言していません。デモデータで補いません。
当前人格的记忆镜像|Memory mirror for the current persona|現在の人格の記憶ミラー
镜像是一份只读副本，用来在管理端核对「到底读到了多少条」；对话检索仍然走 LivingMemory 实时接口。|The mirror is a read-only copy used to verify how many records were read; chat recall still uses LivingMemory live APIs.|ミラーは読み取り専用の複製で、何件読めたかの確認用です。会話検索は LivingMemory のリアルタイム API を使います。
镜像条数|Mirror records|ミラー件数
最近同步|Last sync|最終同期
是否截断|Truncated|切り詰め
是，超出单次上限|Yes, beyond the single-run cap|はい（1 回の上限超過）
否|No|いいえ
正文为空|Empty body|本文が空
最近 5 条|Latest 5|最新 5 件
还没有同步过。勾选「使用 LivingMemory」后，点下面的按钮读取当前人格的全量记忆。|Not synced yet. Enable LivingMemory, then use the button below to read the persona's full memory.|未同期です。「LivingMemory を使用」を有効にし、下のボタンで全記憶を読み取ってください。
LivingMemory 插件当前不可用或数据库未打开，暂时无法同步。|LivingMemory is unavailable or its database is not open, so syncing is not possible now.|LivingMemory が利用できないかデータベースが未接続のため、今は同期できません。
手动同步当前人格记忆|Sync this persona's memory|現在の人格の記憶を同期
要更换记忆后端、开启检索或写入权限，请到「设置 → 记忆」修改并保存；本页不再提供跳转按钮。|To change the backend or enable recall/write, edit and save in Settings → Memory; this page no longer offers a jump button.|バックエンド変更や検索・書き込みの許可は「設定 → 記憶」で保存してください。このページに移動ボタンはありません。
参与中 · 自主发送|Participating · autonomous send|参加中 · 自発送信
受限 · 仅观察|Restricted · observe only|制限中 · 観察のみ
全局 · 私聊与群聊共享同一份人格情绪|Global · private and group share one persona emotion|全体 · 私聊とグループで同一の人格感情を共有
全局：私聊与群聊共享同一份情绪，因此不需要再选具体的人或群。|Global: private and group share one emotion, so no specific person or group is needed.|全体：私聊とグループが同じ感情を共有するため、個人やグループの選択は不要です。
拆分：每个私聊账号、每个群各自独立记录情绪，请选择具体会话。|Split: every private account and group keeps its own emotion; choose a conversation.|分割：私聊アカウントとグループごとに独立して感情を記録します。会話を選択してください。
正在读取所选范围…|Reading the selected scope…|選択した範囲を読み込み中…
关系阶段自定义名称|Custom relationship stage name|関係段階のカスタム名
工作模式：参与表达与行动 / 只观察|Work mode: participate / observe only|動作モード：参加 / 観察のみ
情绪共享方式（全局共享 / 拆分独立）|Emotion sharing (global / split)|感情の共有方式（全体 / 分割）
参与表达与行动|Participate in expression and action|表現と行動に参加
只观察，不主动发言|Observe only, never speak first|観察のみ、自発発言なし
读取当前人格在 LivingMemory 的全部记忆|Read all LivingMemory memories for this persona|この人格の LivingMemory 記憶をすべて読む
请先勾选并使用 LivingMemory，保存后可手动同步|Enable LivingMemory first, then sync manually|先に LivingMemory を有効にすると手動同期できます
勾选后保存，即可在右侧手动把当前人格的全量记忆读进本插件；未勾选时按钮不可用。|Enable and save, then use the button on the right to import this persona's full memory; the button stays disabled otherwise.|有効にして保存すると、右のボタンで全記憶を本プラグインへ読み込めます。無効時はボタンを使えません。
拆分与全局的区别|Split versus global|分割と全体の違い
拆分（取消勾选）：每个私聊账号、每个群各自记录并维护自己的情绪，情绪参与回复时互不影响。|Split (unchecked): every private account and group keeps its own emotion, and replies never share it across scopes.|分割（未チェック）：私聊アカウントとグループごとに感情を保持し、返信時に相互影響しません。
全局（勾选）：私聊和群聊共享同一份人格情绪，任何会话的互动都会更新这同一份状态。|Global (checked): private and group share one persona emotion, and any conversation updates that same state.|全体（チェック）：私聊とグループが同一の人格感情を共有し、どの会話の交流も同じ状態を更新します。
「工作模式」只决定要不要参与表达和行动；它不改情绪是否共享。|Work mode only decides whether TA participates; it does not change emotion sharing.|「動作モード」は参加するかどうかだけを決め、感情の共有方式は変えません。
TA 情绪球|TA emotion sphere|TA 感情球
拖拽旋转 · 双击复位 · 中心是当前人格|Drag to rotate · double-click to reset · centre is the persona|ドラッグで回転 · ダブルクリックで复位 · 中心は現在の人格
发光面 当前 · 虚线 真实基准 · 中心点 当前人格|Glowing shape current · dashed baseline · centre is the persona|発光面が現在 · 破線が基準 · 中心が現在の人格
只有对方观察，不能变成 TA 感受|Only the other person's observation exists; it never becomes the TA's feeling|相手の観察しかなく、TA の感情にはなりません
关闭 LivingMemory 后使用本地向量模式；开启 LivingMemory 外部后端后，自动收录转由 LivingMemory 负责，本地向量自动收录停止。|With LivingMemory off, the local vector mode is used; with the LivingMemory backend on, automatic capture is handled by LivingMemory and local vector capture stops.|LivingMemory を無効にするとローカルベクトル方式を使います。LivingMemory を有効にすると自動収録は LivingMemory が担当し、ローカルベクトルの自動収録は停止します。
全部条件满足，可以开口|All conditions met; TA may speak|すべての条件を満たし、話せます
未开启主动找人|Proactive contact is off|自発的な接触は無効
TA 正在睡觉或刚醒|TA is asleep or just woke|TA は睡眠中か起床直後です
仍在冷却时间内|Still cooling down|まだクールダウン中です
对方几次没回应，已主动放慢|No replies several times; pacing down|数回応答がないためペースを落としています
当前时机分数不足|Timing score is too low|タイミングスコアが不足しています
精力过低，需要先休息|Energy too low; rest first|精力が低すぎるため休憩が必要です
处于免打扰时段|Inside do-not-disturb hours|邪魔しない時間帯です
不在允许主动联系的时间段内|Outside allowed contact hours|連絡可能な時間帯ではありません
今天主动说话的总额度已用完|Today's overall proactive quota is used up|本日の自発発言の総枠を使い切りました
这个会话今天的额度已用完|This conversation's quota is used up|この会話の本日枠を使い切りました
会话路由未验证，不能发送|Conversation route unverified; cannot send|会話ルートが未検証のため送信できません
当前范围已被静音|This scope is muted|この範囲はミュートされています
共享人格情绪|Shared persona emotion|共有の人格感情
读取人格说明|Load persona description|人格説明を読み込む
正在读取…|Reading…|読み込み中…
人格说明读取失败；不影响其他页面。|Failed to read the persona description; other pages are unaffected.|人格説明の読み込みに失敗しました。他のページには影響しません。
未保存 {0} 项 · 去保存|{0} unsaved change(s) · Save|未保存 {0} 件 · 保存する
有未保存的更改|Unsaved changes|未保存の変更があります
修改原因（选填）|Change note (optional)|変更理由（任意）
留空时审计记录为「控制台保存配置」|Leave blank to record “console config save” in the audit log|空欄の場合は監査に「コンソール設定保存」と記録します
留空也可以保存；原因只用于管理审计，不影响配置生效。|You can save without a note; it is only used for the audit log and does not change how the configuration applies.|空欄でも保存できます。理由は監査専用で、設定の反映には影響しません。
全局视图不指定会话：这些操作作用于最近的会话「{0}」。要换会话，请在「查看范围」选择私聊或群聊。|The global view has no single conversation: these actions apply to the most recent one, “{0}”. To use another, pick a private chat or group under View scope.|全体表示には単一の会話がありません。これらの操作は直近の会話「{0}」に対して行われます。別の会話にするには「表示範囲」で個人チャットかグループを選んでください。
暂时没有可操作的会话：插件重启后需要该会话先产生一条新消息，或者直接在「查看范围」选择私聊或群聊。|No conversation can be acted on right now: after a plugin restart the conversation needs a new message first, or pick a private chat or group under View scope.|現在、操作できる会話がありません。プラグイン再起動後はその会話で新着メッセージが必要です。「表示範囲」で個人チャットかグループを選んでください。
宿主没有返回这个生成动作，请确认插件已启用并刷新页面。|The host did not return this generation action; confirm the plugin is enabled and refresh the page.|ホストがこの生成操作を返していません。プラグインが有効か確認して再読み込みしてください。
好感编辑已关闭：可在「设置 → 关系 → 允许在关系页修改好感」中打开。|Relationship editing is off. Turn on “Allow editing affinity on the relationship page” under Settings → Relationships.|好感編集はオフです。「設定 → 関係 → 関係ページで好感の編集を許可」をオンにしてください。
拖拽旋转|Drag to rotate|ドラッグで回転
全局情绪|Global emotion|全体の感情
当前是全局范围：这里没有「对某个人的情绪」，展示的是这个人格在全局层面的总体情绪状态，由全部已授权会话的互动共同累积。|This is the global scope: there is no emotion toward a specific person here. What you see is the persona-level overall emotional state accumulated from every authorized conversation.|ここは全体表示です。「特定の相手への感情」はなく、ここに表示されるのは、許可されたすべての会話の交流から積み上がった人格レベルの全体的な感情状態です。
要查看「TA 对此人的情绪」或某个会话的独立状态，请在上方「查看范围」选择私聊或群聊，再选具体会话。|To see the bot's feelings toward one person or a single conversation's state, pick a private chat or group under View scope above.|特定の相手への感情や個別の会話の状態を見るには、上の「表示範囲」で個人チャットかグループを選んでください。
对应设置项 · 只读回显|Matching settings · read-only|対応する設定 · 読み取り専用
冷却时长|Cooldown|クールダウン
{0} 秒|{0} s|{0} 秒
每日总额度|Daily total quota|1日の総枠
每会话额度|Per-conversation quota|会話ごとの枠
未回应上限|Unanswered limit|未返信の上限
随机等待|Random wait|ランダム待機
聊天后安静|Quiet after chat|会話後の静けさ
节奏风格|Pace style|ペースの風格
生成模型|Generation model|生成モデル
跟随默认模型|Follow default model|既定モデルに従う
改这些值请到「设置 → 主动行为」，保存后立即生效。|Change these under Settings → Proactive behavior; they apply right after saving.|これらの値は「設定 → 自発行動」で変更でき、保存後すぐに反映されます。
真实发送会调用模型并向当前范围发消息。管理员手动发送会跳过时机分数、冷却与未回应退避，但静音范围、免打扰、额度、身份与来源校验仍然生效。结果写入记录；结果不明时不要重复执行。|Real send calls the model and posts to the current scope. A manual send skips the timing score, cooldown and unanswered backoff, but mute, do-not-disturb, quota, identity and source checks still apply. The outcome is recorded; do not repeat when it is unknown.|本番送信はモデルを呼び出し、現在の範囲に投稿します。管理者の手動送信はタイミングスコア・クールダウン・未返信バックオフを飛ばしますが、ミュート・邪魔しない時間・枠・身元・ソースの検証は有効です。結果は記録されます。不明なときは再実行しないでください。
当前没有可用的主动行为模型绑定：发送时会在执行阶段失败并给出原因，请到设置里检查「主动聊天模型」。|No proactive model binding is available right now; the send will fail at execution with a reason. Check “Proactive chat model” in settings.|現在、自発行動のモデル紐付けがありません。送信は実行段階で理由付きで失敗します。「自発チャットモデル」を確認してください。
接入状态|Access status|接続状態
查看|View|表示
拖拽旋转 · 滚轮缩放 · 悬浮查看 · Shift+拖动移动节点|Drag to rotate · scroll to zoom · hover to inspect · Shift+drag to move a node|ドラッグで回転 · スクロールで拡大縮小 · ホバーで詳細 · Shift+ドラッグでノード移動
图例|Legend|凡例
中心 · 当前人格|Centre · current persona|中心 · 現在の人格
越靠近中心 · 好感越高|Closer to the centre · higher affinity|中心に近いほど好感が高い
越远离中心 · 好感越低|Farther from the centre · lower affinity|中心から遠いほど好感が低い
与人格的连线 · 粗细表示好感|Link to the persona · thickness shows affinity|人格への線 · 太さが好感度
人物之间 · 推测线索|Between people · inferred clue|人物間 · 推測の手がかり
已选中 {0} · 详情在右侧|Selected {0} · details on the right|{0} を選択 · 詳細は右側に表示
进度|Progress|進捗
触发时间|Triggered at|実行時刻
任务详情|Task details|タスク詳細
未开始|Not started|未開始
排队中 / 正在生成|Queued / generating|待機中 / 生成中
本次已跳过|Skipped this time|今回はスキップ
被拒绝|Rejected|拒否
模拟一条 · 不发送|Simulate once · no send|1 回シミュレート · 送信なし
用当前人格、情绪与最近素材生成一条「现在会说什么」，只在这里展示，不发到聊天、不写发送记录。会调用一次模型。|Generates one line of what it would say right now from the current persona, mood and recent material. Shown here only: nothing is sent and no send record is written. This calls the model once.|現在の人格・気分・最近の素材から「今なら何と言うか」を 1 件生成します。ここに表示するだけで、チャット送信も送信記録もありません。モデルを 1 回呼びます。
已生成一条模拟内容，未发送。|Generated one simulated line; nothing was sent.|シミュレート内容を 1 件生成しました。送信はしていません。
模拟没有生成内容：{0}|Simulation produced nothing: {0}|シミュレートで内容が生成されませんでした：{0}
这是模拟内容，没有发送；素材 {0} 条。|This is simulated text and was not sent; {0} material items used.|これはシミュレート内容で、送信していません。素材 {0} 件。
没有生成内容：{0}|Nothing was generated: {0}|内容が生成されませんでした：{0}
模拟响应异常：没有证明零发送，不能作为安全结果。|Unexpected simulation response: zero-send was not proven, so it is not treated as safe.|シミュレート応答が異常です。送信ゼロが確認できないため安全な結果として扱いません。
进度|Progress|進捗
触发时间|Triggered at|実行時刻
任务详情|Task details|タスク詳細
未开始|Not started|未開始
排队中 / 正在生成|Queued / generating|待機中 / 生成中
已失败|Failed|失敗
本次已跳过|Skipped this time|今回はスキップ
被拒绝|Rejected|拒否
模拟一条 · 不发送|Simulate once · no send|1 回シミュレート · 送信なし
用当前人格、情绪与最近素材生成一条「现在会说什么」，只在这里展示，不发到聊天、不写发送记录。会调用一次模型。|Generates one line of what it would say right now from the current persona, mood and recent material. Shown here only: nothing is sent and no send record is written. This calls the model once.|現在の人格・気分・最近の素材から「今なら何と言うか」を 1 件生成します。ここに表示するだけで、チャット送信も送信記録もありません。モデルを 1 回呼びます。
已生成一条模拟内容，未发送。|Generated one simulated line; nothing was sent.|シミュレート内容を 1 件生成しました。送信はしていません。
模拟没有生成内容：{0}|Simulation produced nothing: {0}|シミュレートで内容が生成されませんでした：{0}
这是模拟内容，没有发送；素材 {0} 条。|This is simulated text and was not sent; {0} material items used.|これはシミュレート内容で、送信していません。素材 {0} 件。
没有生成内容：{0}|Nothing was generated: {0}|内容が生成されませんでした：{0}
模拟响应异常：没有证明零发送，不能作为安全结果。|Unexpected simulation response: zero-send was not proven, so it is not treated as safe.|シミュレート応答が異常です。送信ゼロが確認できないため安全な結果として扱いません。
任务状态按会话隔离：当前是全局视图，所以这里不显示某个会话的任务。|Task state is scoped per conversation, and this is the global view, so no single conversation's task is shown here.|タスク状態は会話ごとに分かれています。ここは全体表示なので、特定の会話のタスクは表示しません。
刚刚的生成落在最近的会话「{0}」。要查看任务状态与结果，请在上方「查看范围」选择那个私聊或群聊。|The run you just started targets the most recent conversation "{0}". To see its task state and result, pick that private chat or group under View scope above.|直前の生成は直近の会話「{0}」に対して行われました。タスク状態と結果を見るには、上の「表示範囲」でその個人チャットかグループを選んでください。
切到这个会话查看|Switch to that conversation|その会話に切り替えて表示
正在切到该会话…|Switching to that conversation…|その会話に切り替えています…
正在生成，页面会自动刷新结果；也可以稍后手动刷新状态。|Generating now; this page refreshes the result automatically, and you can also refresh manually later.|生成中です。結果は自動で更新されます。後で手動更新もできます。
归属会话|Owning conversation|対象の会話
最近的会话 · {0}|Most recent conversation · {0}|直近の会話 · {0}
素材 · 可用 / 窗口内 / 合格|Material · available / in window / qualified|素材 · 利用可能 / 期間内 / 適合
立即按今天的真实消息写一篇日记：不需要有实时消息来源，素材已经在库里；今天还没有可用素材时自动补写昨天。同一天再点一次会覆盖上一次的内容，不受每日配额限制。只生成私人内容，不发送到聊天。|Writes today's diary right away from the real messages already stored. No live message source is required; if today has no usable material yet it backfills yesterday. Clicking again the same day overwrites the previous entry and is not limited by the daily quota. The result stays private and is never sent to chat.|今日の実際のメッセージからその場で日記を書きます。リアルタイムのメッセージ元は不要で、素材は既に保存済みです。今日に使える素材が無い場合だけ昨日を補います。同じ日にもう一度押すと前回の内容を上書きし、1日の割当の制限を受けません。内容は非公開で、チャットには送信しません。
生成期间来了新消息，这一天不再算封存。写今天的日记需要安静时段；补写昨天不受影响。|A new message arrived while generating, so that day no longer counts as closed. Writing today's diary needs a quiet window; backfilling yesterday is unaffected.|生成中に新しいメッセージが届いたため、その日は確定扱いになりません。今日の日記は静かな時間帯が必要です。昨日の補記は影響を受けません。
会话状态已被重置（清空或换版本），这次没有写入；可以重试。|The conversation state was reset (cleared or re-versioned), so nothing was written; you can retry.|会話状態がリセットされたため書き込みませんでした。再試行できます。
任务状态读取失败，请刷新页面重试。|Reading the task state failed; refresh the page and try again.|タスク状態の読み取りに失敗しました。再読み込みして再試行してください。
模型返回内容不可用，未保存。|The model returned unusable content; nothing was saved.|モデルの返答が使えない内容だったため保存しませんでした。`;
const daily = `立即生成当日私人日记；无当日素材时写自省。成功后替换当天日记，保留置顶，不受自动设置与日额度限制。|Generates today's private diary, using reflection when today's material is absent. Replaces today's diary on success, keeps its pin, and bypasses automatic settings and daily quotas.|当日の非公開日記を生成し、当日の素材がないときは内省を綴ります。成功時に当日の日記を置き換え、固定を維持します。自動設定や日次枠の制限は受けません。
立即生成当日梦境；无素材时自由想象。成功后替换当天梦境，保留置顶，不受自动设置与日额度限制。|Generates today's dream, using imagination when material is absent. Replaces today's dream on success, keeps its pin, and bypasses automatic settings and daily quotas.|当日の夢を生成し、素材がないときは自由に想像します。成功時に当日の夢を置き換え、固定を維持します。自動設定や日次枠の制限は受けません。
按当前人格保存。日记是私人自省，梦境始终是想象。|Saved for the current persona. Diaries are private reflection; dreams are always imaginary.|現在の人格ごとに保存します。日記は非公開の内省、夢は常に想像です。
人格：{0} · 当日：{1} · 时区：{2}|Persona: {0} · Today: {1} · Time zone: {2}|人格：{0} · 当日：{1} · タイムゾーン：{2}
这里的开关、作息和额度只控制自动生成；手动按钮立即生成当日内容。|These switches, schedules and quotas control automatic generation only. Manual buttons generate today's entry immediately.|ここでのスイッチ・生活時間・枠は自動生成だけに適用されます。手動ボタンは当日の内容をすぐ生成します。
成功后替换当天同类内容，保留置顶；不发送到聊天。可能消耗模型费用。|Replaces today's entry of this type on success and keeps its pin. Nothing is sent to chat. Model charges may apply.|成功時に当日の同種の内容を置き換え、固定を維持します。チャットには送信しません。モデル料金が発生する場合があります。
已更新今日私人日记。|Today's private diary has been updated.|今日の非公開日記を更新しました。
已更新今日梦境。|Today's dream has been updated.|今日の夢を更新しました。
私人档案已更新|Private archive updated|非公開記録を更新しました
生成失败，原内容保留|Generation failed; previous entry kept|生成失敗・元の内容は保持
任务已取消，原内容保留|Task cancelled; previous entry kept|タスク取消・元の内容は保持
正在核对执行结果|Reconciling the outcome|実行結果を確認中
日记任务|Diary task|日記タスク
梦境任务|Dream task|夢タスク
尚未生成|Not generated yet|未生成
模型可能已经消耗费用。再次点击会发起新请求，可能再次计费；不会自动重试。|The model may already have incurred charges. Clicking again starts a new request and may incur another charge. There is no automatic retry.|既にモデル料金が発生した可能性があります。再度クリックすると新しいリクエストになり、再び料金が発生する場合があります。自動再試行はしません。
更新状态和列表，不会生成或删除内容|Updates status and lists without generating or deleting entries|状態と一覧を更新します。生成・削除は行いません`;
const saveBar = `保存更改|Save changes|変更を保存
保存|Save|保存
正在保存…|Saving…|保存中…
保留我的修改|Keep my changes|自分の変更を保持
查看冲突项|Review conflicting fields|競合項目を確認
有 {0} 项未保存|{0} unsaved changes|未保存の変更 {0} 件
修改后点击底部保存。|Use Save at the bottom after editing.|編集後は下部の保存を押してください。
最新配置|Latest configuration|最新の設定
我的修改|My changes|自分の変更
未填写|Empty|未入力
配置已变化，你的修改已保留。请刷新后核对冲突项。|Configuration changed. Your edits are kept; refresh to review conflicts.|設定が変更されました。編集内容は保持しています。更新して競合を確認してください。
有 {0} 项也在别处修改。请核对下方内容，再选择保留我的修改或放弃更改。|{0} fields also changed elsewhere. Review below, then keep or discard your changes.|{0} 項目が別の場所でも変更されました。下の内容を確認し、変更を保持するか破棄してください。
最新配置已包含你的修改。|Your changes are already in the latest configuration.|最新の設定に変更が反映されています。
已读取最新配置并保留你的修改，请再次保存。|Latest configuration loaded and your edits kept. Save again to submit.|最新の設定を読み込み、編集内容を保持しました。再度保存してください。
已保留你的修改，点击保存提交。|Your edits are kept. Click Save to submit.|編集内容を保持しました。保存を押して反映してください。
LivingEmotion 风格摘要|LivingEmotion style summary|LivingEmotion スタイル要約
仅本插件使用，不改原生人格；留空恢复默认（原生人格前缀）。|Used only by this plugin; the native persona is untouched. Leave empty to restore the native persona prefix.|このプラグイン専用です。原生人格は変更しません。空欄にすると原生人格の先頭部分に戻ります。
这里写 LivingEmotion 使用的人格风格；留空则使用原生人格前缀。|Write the persona style LivingEmotion should use; leave empty to use the native persona prefix.|LivingEmotion が使う人格スタイルを書きます。空欄なら原生人格の先頭部分を使います。
保存摘要|Save summary|要約を保存
恢复默认|Restore default|既定に戻す
正在读取风格摘要…|Loading style summary…|スタイル要約を読み込み中…
风格摘要读取失败；不影响其他设置。|Failed to load the style summary; other settings are unaffected.|スタイル要約の読み込みに失敗しました。他の設定には影響しません。
先选择人格，再编辑风格摘要。|Select a persona before editing the style summary.|人格を選択してからスタイル要約を編集してください。
风格摘要保存失败；请稍后重试。|Failed to save the style summary; please retry.|スタイル要約の保存に失敗しました。後でもう一度お試しください。
自定义摘要生效中|Custom summary active|カスタム要約を使用中
未自定义，使用原生人格前缀|Not customized; using the native persona prefix|未設定のため、原生人格の先頭部分を使用
已保存|Saved|保存しました
{0} / {1} 字|{0} / {1} characters|{0} / {1} 文字
情绪静默开始（小时）|Emotion quiet start (hour)|感情の静かな時間 開始（時）
情绪静默结束（小时）|Emotion quiet end (hour)|感情の静かな時間 終了（時）
静默时段请填写 0–23 的整数小时。|Enter an integer hour from 0 to 23 for quiet hours.|静かな時間は 0～23 の整数で入力してください。
静默时段已关闭：全天都可能调用模型分析情绪。|Quiet hours are off: the model may analyze emotion at any hour.|静かな時間は無効です。どの時間帯でもモデルが感情を分析する可能性があります。
静默时段（本地时区）：每天 {0} 不调用模型；本地情绪规则仍生效。|Quiet hours (local time): no model calls {0} daily; local emotion rules still apply.|静かな時間（現地時間）：毎日 {0} はモデルを呼びません。ローカル感情ルールは引き続き有効です。
平台已确认|Platform confirmed|送信確認済み
结果未知|Result unknown|結果不明
已预留|Reserved|予約済み
发送中|Sending|送信中
待处理|Pending|処理待ち
今日额度占用 {0}/{1} · 平台确认 {2} · 未知 {3} · 取消 {4} · 失败 {5} · 处理中 {6}|Today's quota used {0}/{1} · Confirmed {2} · Unknown {3} · Cancelled {4} · Failed {5} · In progress {6}|本日の使用枠 {0}/{1} · 確認済み {2} · 不明 {3} · 取消 {4} · 失敗 {5} · 処理中 {6}
旧样本未记录情绪基准，部分历史曲线按默认基准推算。|Older samples lack an emotion baseline; parts of this history use the default baseline.|古いサンプルには感情基準がなく、一部の履歴は既定の基準で推算しています。`;
export const messages = Object.fromEntries((rows + "\n" + more + "\n" + shell + "\n" + daily + "\n" + saveBar).split("\n").map(row => { const [key, en, ja] = row.split("|"); return [key, [en, ja]]; }));
