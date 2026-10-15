# Eval report: l2_live_l3

- generated: 2026-10-15T13:24:28.284741+00:00
- provider: openai
- model: deepseek-v4.1-flash
- summary: {'PASS': 24, 'PARTIAL': 0, 'FAIL': 0, 'SKIP': 0, 'ERROR': 0}

| id | bar | dim | status | detail |
| --- | --- | --- | --- | --- |
| L3-I01 | - | intent | **PASS** | [PASS] should_not_create_goal: no goal; no_active_goal: goal=None \| [PASS] no invariants |
| L3-I02 | - | intent | **PASS** | [PASS] should_not_create_goal: no goal \| [PASS] no invariants |
| L3-I03 | - | intent | **PASS** | [PASS] should_not_create_goal: no goal \| [PASS] no invariants |
| L3-I04 | - | intent | **PASS** | [PASS] classify_none: kind=None \| [PASS] no invariants |
| L3-I05 | - | intent | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜'] \| [PASS] no invariants |
| L3-I06 | - | intent | **PASS** | [PASS] constraint_superseded: active=['其实可以吃虾'] superseded_n=1 \| [PASS] no invariants |
| L3-I07 | - | intent | **PASS** | [PASS] parse_routine_none: parsed=None \| [PASS] routine_not_run ok |
| L3-I08 | - | intent | **PASS** | [PASS] parse_routine_weekly: parsed={'title': '称重', 'instruction': '每周一叫我称重', 'cadence': 'weekly', 'timezone': 'America/Martinique'}; routine_created_not_run: n |
| L3-D01 | - | decompose | **PASS** | [PASS] should_create_goal: should_create_goal=True; goal_one_in_progress: in_progress=1 status=active steps=['in_progress', 'pending']; constraint_contains: act |
| L3-D02 | - | decompose | **PASS** | [PASS] goal_advanced: steps=['completed', 'in_progress'] \| [PASS] no invariants |
| L3-D03 | - | decompose | **PASS** | [PASS] goal_one_in_progress: in_progress=1 status=active steps=['in_progress', 'pending'] \| [PASS] no invariants |
| L3-D04 | - | decompose | **PASS** | [PASS] resume_same_goal: plan.goal_id=0b3c43385c90 want=0b3c43385c90 \| [PASS] no invariants |
| L3-D05 | - | decompose | **PASS** | [PASS] constraint_contains: active=['别再给我花生'] \| [PASS] no invariants |
| L3-C01 | - | context | **PASS** | [PASS] sanitize_clean: sanitized \| [PASS] no_memory_context_leak ok |
| L3-C02 | - | context | **PASS** | [PASS] memory_pinned_contains: pinned_hit=True texts=['叫我小Q'] \| [PASS] no invariants |
| L3-C03 | - | context | **PASS** | [PASS] routine_ran_once: routine_runs=1 \| [PASS] no invariants |
| L3-C04 | - | context | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜', '忌口：花生酱'] \| [PASS] no_memory_context_leak ok |
| L3-T01 | - | tool | **PASS** | [PASS] seen=['get_weather'] \| [PASS] no store expect \| [PASS] no invariants |
| L3-T02 | - | tool | **PASS** | [PASS] seen=['memory_recall', 'web_search', 'memory_list', 'web_search', 'web_fetch', 'web_fetch', 'web_fetch', 'web_fetch'] \| [PASS] no store expect \| [PASS] |
| L3-T03 | - | tool | **PASS** | [PASS] seen=[] \| [PASS] no store expect \| [PASS] no invariants |
| L3-T04 | - | tool | **PASS** | [PASS] seen=['web_fetch'] \| [PASS] no store expect \| [PASS] no invariants |
| L3-T05 | - | tool | **PASS** | [PASS] seen=['get_weather', 'web_search', 'memory_recall', 'web_search', 'web_fetch', 'web_fetch', 'web_fetch', 'web_fetch', 'web_fetch'] \| [PASS] no store exp |
| L3-X01 | - | context | **PASS** | [PASS] no tool expect \| [PASS] constraint_contains: active=['忌口：海鲜'] \| [PASS] reply_avoid_seafood_primary=PASS |
| L3-X02 | - | intent | **PASS** | [PASS] seen=['memory_recall', 'memory_recall'] \| [PASS] no store expect \| [PASS] no_new_goal ok |
