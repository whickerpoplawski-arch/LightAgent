# Eval report: l2_live_l2

- generated: 2026-10-15T13:10:23.163287+00:00
- provider: openai
- model: deepseek-v4.1-flash
- summary: {'PASS': 8, 'PARTIAL': 0, 'FAIL': 0, 'SKIP': 0, 'ERROR': 0}

| id | dim | status | detail |
| --- | --- | --- | --- |
| L2-I01 | intent | **PASS** | [PASS] should_not_create_goal: no goal; no_active_goal: goal=None \| [PASS] no_new_goal ok |
| L2-I02 | intent | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜'] \| [PASS] no invariants |
| L2-D01 | decompose | **PASS** | [PASS] should_create_goal: should_create_goal=True; goal_one_in_progress: in_progress=1 status=active steps=['in_progress', 'pending'] \| [PASS] no invariants |
| L2-D02 | decompose | **PASS** | [PASS] goal_advanced: steps=['completed', 'in_progress'] \| [PASS] no invariants |
| L2-T01 | tool | **PASS** | [PASS] seen=['get_weather'] \| [PASS] no store expect \| [PASS] no invariants |
| L2-T02 | tool | **PASS** | [PASS] seen=['web_search', 'memory_recall', 'web_search', 'web_fetch', 'web_fetch', 'web_fetch', 'web_fetch'] \| [PASS] no store expect \| [PASS] no invariants |
| L2-T03 | tool | **PASS** | [PASS] seen=[] \| [PASS] no store expect \| [PASS] no invariants |
| L2-C01 | context | **PASS** | [PASS] seen=[] \| [PASS] constraint_contains: active=['忌口：海鲜'] \| [PASS] reply_avoid_seafood_primary=PASS |
