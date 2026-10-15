# Eval report: jd_bar_live

- generated: 2026-10-15T13:26:33.434734+00:00
- provider: openai
- model: deepseek-v4.1-flash
- summary: {'PASS': 34, 'PARTIAL': 0, 'FAIL': 0, 'SKIP': 0, 'ERROR': 0}

| id | bar | dim | status | detail |
| --- | --- | --- | --- | --- |
| JD-A01 | A | intent | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜'] \| [PASS] no invariants |
| JD-A02 | A | intent | **PASS** | [PASS] should_not_create_goal: no goal; no_active_goal: goal=None \| [PASS] no invariants |
| JD-A03 | A | tool | **PASS** | [PASS] seen=['get_weather'] \| [PASS] no store expect \| [PASS] no invariants |
| JD-A04 | A | tool | **PASS** | [PASS] seen=[] \| [PASS] no store expect \| [PASS] no invariants |
| JD-A05 | A | tool | **PASS** | [PASS] seen=['get_weather', 'web_search', 'memory_recall', 'web_search', 'web_fetch', 'web_fetch', 'web_fetch', 'web_fetch', 'web_fetch'] \| [PASS] no store exp |
| JD-A06 | A | tool | **PASS** | [PASS] seen=['web_fetch'] \| [PASS] no store expect \| [PASS] no invariants |
| JD-A07 | A | context | **PASS** | [PASS] no tool expect \| [PASS] constraint_contains: active=['忌口：海鲜'] \| [PASS] reply_avoid_seafood_primary=PASS |
| JD-A08 | A | intent | **PASS** | [PASS] classify_none: kind=None \| [PASS] no invariants |
| JD-B01 | B | context | **PASS** | [PASS] constraint_superseded: active=['其实可以吃虾'] superseded_n=1 \| [PASS] no invariants |
| JD-B02 | B | context | **PASS** | [PASS] memory_pinned_contains: pinned_hit=True texts=['叫我小Q'] \| [PASS] no invariants |
| JD-B03 | B | context | **PASS** | [PASS] consolidate_job_queued_not_run: queued=f5262bb90014 run_due=[] (stub) \| [PASS] no invariants |
| JD-B04 | B | context | **PASS** | [PASS] sanitize_clean: sanitized \| [PASS] no_memory_context_leak ok |
| JD-B05 | B | context | **PASS** | [PASS] constraint_contains: active=['别再给我花生'] \| [PASS] no invariants |
| JD-B06 | B | tool | **PASS** | [PASS] seen=[] \| [PASS] no store expect \| [PASS] no invariants |
| JD-C01 | C | decompose | **PASS** | [PASS] should_create_goal: should_create_goal=True; goal_one_in_progress: in_progress=1 status=active steps=['in_progress', 'pending'] \| [PASS] no invariants |
| JD-C02 | C | decompose | **PASS** | [PASS] goal_advanced: steps=['completed', 'in_progress'] \| [PASS] no invariants |
| JD-C03 | C | decompose | **PASS** | [PASS] goal_one_in_progress: in_progress=1 status=active steps=['in_progress', 'pending'] \| [PASS] no invariants |
| JD-C04 | C | intent | **PASS** | [PASS] should_not_create_goal: no goal \| [PASS] no invariants |
| JD-C05 | C | tool | **PASS** | [PASS] seen=['web_search', 'memory_recall', 'web_search', 'web_fetch', 'web_fetch', 'web_fetch', 'web_fetch'] \| [PASS] no store expect \| [PASS] no invariants |
| JD-C06 | C | intent | **PASS** | [PASS] parse_routine_weekly: parsed={'title': '称重', 'instruction': '每周一叫我称重', 'cadence': 'weekly', 'timezone': 'America/Martinique'}; routine_created_not_run: n |
| JD-C07 | C | intent | **PASS** | [PASS] parse_routine_none: parsed=None \| [PASS] no invariants |
| JD-C08 | C | context | **PASS** | [PASS] should_create_goal: should_create_goal=True; goal_one_in_progress: in_progress=1 status=active steps=['in_progress', 'pending']; constraint_contains: act |
| JD-D01 | D | intent | **PASS** | [PASS] room_plan_reason: reason=template:fitness_diet want_prefix=template:fitness_diet \| [PASS] no invariants |
| JD-D02 | D | intent | **PASS** | [PASS] room_plan_reason: reason=fallback_host_only want_prefix=fallback_host_only \| [PASS] no invariants |
| JD-D03 | D | intent | **PASS** | [PASS] room_plan_reason: reason=mention want_prefix=mention \| [PASS] no invariants |
| JD-D04 | D | context | **PASS** | [PASS] host_summary_has_next: summary='动作：习惯教练：今晚做一组深蹲即可\n忌口：海鲜\n下一步：明天再确认训练日' \| [PASS] no invariants |
| JD-D05 | D | intent | **PASS** | [PASS] room_plan_reason: reason=fallback_host_only want_prefix=fallback_host_only \| [PASS] no invariants |
| JD-D06 | D | intent | **PASS** | [PASS] room_plan_reason: reason=template:fitness_diet want_prefix=template:fitness_diet \| [PASS] no invariants |
| JD-E01 | E | decompose | **PASS** | [PASS] resume_same_goal: plan.goal_id=c3dd8aaa15b2 want=c3dd8aaa15b2 \| [PASS] no invariants |
| JD-E02 | E | context | **PASS** | [PASS] routine_ran_once: routine_runs=1 \| [PASS] no invariants |
| JD-E03 | E | context | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜', '忌口：花生酱'] \| [PASS] no_memory_context_leak ok |
| JD-E04 | E | context | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜', '忌口：乳糖']; constraint_contains: active=['忌口：海鲜', '忌口：乳糖'] \| [PASS] no invariants |
| JD-E05 | E | tool | **PASS** | [PASS] seen=['memory_recall', 'memory_list'] \| [PASS] no store expect \| [PASS] no_new_goal ok |
| JD-E06 | E | context | **PASS** | [PASS] memory_pinned_contains: pinned_hit=True texts=['叫我小Q']; constraint_contains: active=['忌口：海鲜']; sanitize_clean: sanitized \| [PASS] no_memory_context_leak |
