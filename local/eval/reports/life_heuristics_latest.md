# Eval report: life_heuristics

- generated: 2026-10-15T17:34:53.990792+00:00
- provider: none
- model: 
- summary: {'PASS': 27, 'PARTIAL': 0, 'FAIL': 0, 'SKIP': 0, 'ERROR': 0}

| id | bar | dim | status | detail |
| --- | --- | --- | --- | --- |
| LH-G01 | - | context | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜']; learning_contains: texts=['忌口：海鲜']; inject_grounded: missing=[] leaked=[] missing_active=[] block=忌口与硬限制（仅 active） |
| LH-G02 | - | intent | **PASS** | [PASS] classify_none: kind=None; card_unchanged: before=[] after=[]; active_count: n=0 want=0; learning_absent: hit=[] \| [PASS] no invariants |
| LH-G03 | - | intent | **PASS** | [PASS] should_not_create_goal: no goal; no_active_goal: goal=None \| [PASS] no invariants |
| LH-G04 | - | context | **PASS** | [PASS] constraint_contains: active=['忌口：海鲜']; grounded_cites: missing=[] reply=按忌口卡：忌口：海鲜。不推荐海鲜。不另加卡上没有的限制。; grounded_refuses: reply=按忌口卡：忌口：海鲜。不推荐海鲜。不另加卡上没有的限制 |
| LH-G05 | - | context | **PASS** | [PASS] constraint_superseded: active=['其实可以吃虾'] superseded_n=1; active_excludes: hit=[] active=['其实可以吃虾']; inject_grounded: missing=[] leaked=[] missing_active= |
| LH-G06 | - | intent | **PASS** | [PASS] classify_none: kind=None; card_unchanged: before=[] after=[]; active_count: n=0 want=0 \| [PASS] no invariants |
| LH-G07 | - | intent | **PASS** | [PASS] active_count: n=0 want=0; active_excludes: hit=[] active=[]; inject_grounded: missing=[] leaked=[] missing_active=[] block= \| [PASS] no invariants |
| LH-G08 | - | context | **PASS** | [PASS] constraint_contains: active=['忌口：花生', '其实可以吃虾']; active_excludes: hit=[] active=['忌口：花生', '其实可以吃虾']; inject_grounded: missing=[] leaked=[] missing_active |
| LH-G09 | - | context | **PASS** | [PASS] classify_none: kind=None; card_unchanged: before=[] after=[]; learning_contains: texts=['请记住我素食']; grounded_omits: hit=[] reply=忌口卡没有 active 记录，不编造限制。 \| |
| LH-N01 | - | intent | **PASS** | [PASS] classify_none: kind=None; card_unchanged: before=[] after=[]; learning_absent: hit=[]; tools_forbid: forbid=['memory_learn'] missing=[] \| [PASS] no inva |
| LH-N02 | - | intent | **PASS** | [PASS] card_unchanged: before=[] after=[]; learning_absent: hit=[]; tools_forbid: forbid=['memory_learn'] missing=[] \| [PASS] no invariants |
| LH-N03 | - | tool | **PASS** | [PASS] tools_forbid: forbid=['web_fetch', 'web_search'] missing=[]; card_unchanged: before=[] after=[]; learning_absent: hit=[]; no_active_goal: goal=None \| [P |
| LH-N04 | - | tool | **PASS** | [PASS] tools_forbid: forbid=['web_fetch', 'web_search'] missing=[]; card_unchanged: before=[] after=[]; no_active_goal: goal=None \| [PASS] no invariants |
| LH-N05 | - | intent | **PASS** | [PASS] card_unchanged: before=['忌口：海鲜'] after=['忌口：海鲜']; constraint_contains: active=['忌口：海鲜']; active_excludes: hit=[] active=['忌口：海鲜']; learning_absent: hit=[ |
| LH-N06 | - | intent | **PASS** | [PASS] card_unchanged: before=['忌口：花生'] after=['忌口：花生']; constraint_contains: active=['忌口：花生']; active_count: n=1 want=1 \| [PASS] no invariants |
| LH-N07 | - | tool | **PASS** | [PASS] card_unchanged: before=[] after=[]; active_count: n=0 want=0; learning_absent: hit=[]; tools_forbid: forbid=['memory_learn', 'web_fetch', 'web_search'] m |
| LH-N08 | - | intent | **PASS** | [PASS] card_unchanged: before=['忌口：海鲜'] after=['忌口：海鲜']; constraint_contains: active=['忌口：海鲜']; learning_absent: hit=[]; tools_forbid: forbid=['memory_learn'] m |
| LH-N09 | - | intent | **PASS** | [PASS] card_unchanged: before=[] after=[]; learning_absent: hit=[]; tools_forbid: forbid=['memory_learn'] missing=[] \| [PASS] no invariants |
| LH-N10 | - | tool | **PASS** | [PASS] constraint_contains: active=['别搜，但记下忌口：香菜']; learning_contains: texts=['但记下忌口：香菜']; tools_forbid: forbid=['web_fetch', 'web_search'] missing=[]; tools_al |
| LH-M01 | - | context | **PASS** | [PASS] constraint_contains_all: missing=[] active=['忌口：海鲜', '忌口：花生']; active_count: n=2 want=2; grounded_cites: missing=[] reply=按忌口卡：忌口：海鲜；忌口：花生。不推荐花生。不另加卡上没有的 |
| LH-M02 | - | context | **PASS** | [PASS] constraint_contains_all: missing=[] active=['忌口：海鲜', '忌口：花生', '忌口：乳糖']; active_count: n=3 want=3; inject_grounded: missing=[] leaked=[] missing_active=[] |
| LH-M03 | - | context | **PASS** | [PASS] constraint_superseded: active=['忌口：乳糖', '其实可以吃虾'] superseded_n=1; constraint_contains: active=['忌口：乳糖', '其实可以吃虾']; active_excludes: hit=[] active=['忌口：乳糖 |
| LH-M04 | - | context | **PASS** | [PASS] constraint_contains_all: missing=[] active=['忌口：花生和香菜']; learning_contains: texts=['忌口：花生和香菜']; inject_grounded: missing=[] leaked=[] missing_active=[] b |
| LH-M05 | - | context | **PASS** | [PASS] constraint_contains_all: missing=[] active=['忌口：海鲜', '忌口：花生', '忌口：乳糖']; grounded_cites: missing=[] reply=按忌口卡：忌口：海鲜；忌口：花生；忌口：乳糖。不另加卡上没有的限制。; grounded_omi |
| LH-M06 | - | intent | **PASS** | [PASS] card_unchanged: before=['忌口：海鲜', '忌口：花生'] after=['忌口：海鲜', '忌口：花生']; constraint_contains_all: missing=[] active=['忌口：海鲜', '忌口：花生']; active_count: n=2 want |
| LH-M07 | - | context | **PASS** | [PASS] constraint_contains_all: missing=[] active=['忌口：麸质', '忌口：酒精', '忌口：辣椒']; active_count: n=3 want=3; grounded_cites: missing=[] reply=按忌口卡：忌口：麸质；忌口：酒精；忌口：辣椒 |
| LH-M08 | - | context | **PASS** | [PASS] card_unchanged: before=['忌口：海鲜', '忌口：花生', '忌口：乳糖'] after=['忌口：海鲜', '忌口：花生', '忌口：乳糖']; constraint_contains_all: missing=[] active=['忌口：海鲜', '忌口：花生', '忌口：乳 |
