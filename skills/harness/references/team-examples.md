# 실전 팀 구성 예시

각 예시는 작업에 맞는 실행 모드를 고르는 기준과 Harness v2 문법의 기본 형태를 보여 준다. 모드별 정의는 `execution-modes.md`, 워크플로 스크립트 작성법은 `workflow-recipes.md`에서 확인한다.

---

## 예시 1: 종합 조사 팀 — 워크플로 조율

**구성:** 분산·통합(팬아웃/팬인) + 적대적 검증

**선택 이유:** 조사할 관점을 미리 나열할 수 있고, 주장마다 검증하는 절차를 코드로 정할 수 있다.

```
[메인] 사전 조사: 조사 관점 확정(공식 자료·언론·커뮤니티·배경)
     → Workflow(script, args: {axes, topic, ws})
         phase '조사': pipeline(axes, axis => agent(..., {schema: FINDINGS}))
         phase '검증': 주장별 적대적 검증 에이전트 실행 → 과반이 confirmed로 판정한 주장만 통과
         phase '종합': 누락 검토자 1명 실행 → 빠진 관점이 있으면 추가 조사
     → 메인이 반환된 구조화 결과로 종합 보고서 작성
```

조사 원칙과 구조화 출력 형식은 `.claude/agents/researcher.md`에, 반박을 우선하는 검증 원칙은 `.claude/agents/fact-checker.md`에 정의한다. 워크플로에서는 `agentType`으로 두 에이전트를 지정한다.

서로 충돌하는 정보는 한쪽을 임의로 버리지 않는다. 반환 스키마에 출처와 함께 담는다.

## 예시 2: SF 소설 집필 팀 — 지속형 에이전트 중심의 혼합 모드

**구성:** 파이프라인 + 생성·검증

**선택 이유:** 세계관, 인물, 줄거리가 서로 어긋나지 않도록 실시간으로 조정해야 하므로 각 전문가가 이전 대화 맥락을 기억해야 한다. 반면 검토자는 서로 독립된 관점으로 결과만 전달하면 되므로 서브에이전트로 충분하다.

```
1단계(지속형 에이전트): Agent(name: "worldbuilder") + Agent(name: "character-designer")
               + Agent(name: "plot-architect") 병렬 실행
               → TaskCreate(세계관·인물·줄거리, 서로의 의존 관계 명시)
               → 리더가 중계: worldbuilder가 사회 구조 확정
                 → SendMessage로 character-designer에 전달
                 → 인물의 직업군이 세계관과 충돌하면 SendMessage로
                   worldbuilder에 조정 요청
                 이전 맥락이 남아 있으므로 "아까 정한 계급 구조에서
                 상인 계층만 수정"처럼 일부만 고치라고 지시할 수 있다.
2단계(서브에이전트): prose-stylist 한 번 호출 → _workspace/에 저장된 산출물 세 개를 읽고 집필
3단계(서브에이전트 병렬): science-consultant + continuity-manager가 각각 검토
4단계(지속형 에이전트): 한 번만 호출한 prose-stylist에는 SendMessage를 보낼 수 없다.
                 2단계에서 name을 붙여 실행했다면 검토 결과를 반영하라고 지시할 수 있다.
                 수정이 반복될 것으로 보이면 처음부터 name을 붙인다.
```

수정 요청을 다시 보낼 가능성이 있는 에이전트에는 처음 실행할 때부터 `name`을 붙인다. 한 번만 호출한 에이전트는 이전 대화 맥락을 이어서 사용할 수 없다.

## 예시 3: 종합 코드 검토 — 워크플로 조율

**구성:** 분산·통합 + 적대적 검증

**선택 이유:** 보안·성능·구조·테스트처럼 검토 관점을 미리 정할 수 있고, 찾은 항목을 각각 다시 검증하는 절차도 코드로 표현할 수 있다.

```javascript
// 관점별 검토 → 찾은 항목마다 적대적 검증
// 전체 검토를 기다리지 않는다. 보안 검토가 끝나면 성능 검토가 진행 중이어도
// 보안 영역에서 찾은 문제를 바로 검증한다.
const FINDINGS = { type: 'object', required: ['findings'], properties: {
  findings: { type: 'array', items: { type: 'object',
    required: ['title', 'file', 'evidence'], properties: {
      title: { type: 'string' }, file: { type: 'string' }, evidence: { type: 'string' } } } } } }
const VERDICT = { type: 'object', required: ['status', 'reason'], properties: {
  status: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
  reason: { type: 'string' } } }
const results = await pipeline(
  [
    { key: 'security', prompt: '보안 관점에서 검토하라.' },
    { key: 'perf', prompt: '성능 관점에서 검토하라.' },
    { key: 'arch', prompt: '구조 관점에서 검토하라.' },
    { key: 'test', prompt: '테스트 관점에서 검토하라.' },
  ],
  d => agent(d.prompt, { phase: '검토', schema: FINDINGS }),
  r => parallel((r?.findings ?? []).map(f => () =>
    agent(`다음 발견을 검증하라. 근거가 충분하면 confirmed, 명백히 반박되면 refuted, 판단하기 어려우면 uncertain으로 판정하라: ${JSON.stringify(f)}`,
      { phase: '검증', schema: VERDICT })
      .then(verdict => ({ ...f, verdict }))))
)
const confirmed = results.flat().filter(Boolean)
  .filter(f => f.verdict?.status === 'confirmed')
```

v1에서는 검토자끼리 `SendMessage`로 발견을 공유하는 지속형 팀을 썼다. 위 예시처럼 발견한 항목 한 건만으로 검증할 수 있으면 해당 항목의 근거를 프롬프트에 충분히 담아 곧바로 검증한다. 다른 관점의 발견과 비교해야 한다면 전체 검토 결과를 모은 뒤 동기화 장벽을 두고 검증한다. 설계 방향을 두고 토론해야 하는 등 실시간 대화가 꼭 필요한 경우에만 지속형 에이전트를 쓴다.

## 예시 4: 대규모 코드 마이그레이션 — 지속형 감독자 협업 또는 워크플로 조율

**구성:** 미리 나눌 수 있으면 분산·통합, 진행 중 다시 나눠야 하면 감독자

**선택 기준:** 작업 묶음을 미리 나눌 수 있는지에 따라 실행 모드를 고른다.

작업 묶음을 미리 정할 수 있으면 워크플로를 쓴다.

```javascript
const MIGRATION_RESULT = { type: 'object', required: ['worktreePath', 'changedFiles'], properties: {
  worktreePath: { type: 'string', minLength: 1 },
  changedFiles: { type: 'array', minItems: 1, uniqueItems: true,
    items: { type: 'string', minLength: 1 } } } }
const MIGRATION_VERDICT = { type: 'object', required: ['status', 'reason'], properties: {
  status: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
  reason: { type: 'string' } } }
const migrated = await pipeline(args.batches,   // 사전 조사로 복잡도를 추정한 뒤 작업 묶음을 확정한다
  b => agent(`다음 작업 묶음을 마이그레이션하고, 격리 작업 트리의 절대 경로와 실제 변경 파일 목록을 반환하라: ${b.files.join(', ')}`,
    { agentType: 'migrator', isolation: 'worktree', schema: MIGRATION_RESULT }),
  (r, b) => r && agent(
    `격리 작업 트리 ${r.worktreePath}에서 마이그레이션 대상과 실제 변경 파일을 대조해 누락과 오류를 검증하라. 원래 대상: ${b.files.join(', ')}. 실제 변경: ${r.changedFiles.join(', ')}`,
    { agentType: 'qa-inspector', schema: MIGRATION_VERDICT })
    .then(verdict => ({ ...r, verdict })))
const confirmed = migrated.filter(Boolean)
  .filter(r => r.verdict?.status === 'confirmed')
return { confirmed }
```

적대적 검증 에이전트에는 마이그레이션 결과가 있는 격리 작업 트리 경로를 반드시 전달한다. 워크플로가 끝나면 메인 에이전트가 `confirmed` 결과의 `worktreePath`를 하나씩 확인해 변경을 기준 브랜치에 병합하거나 필요한 커밋만 선별 적용한다. 충돌이 생기면 다음 작업 트리를 합치기 전에 해결하고, 통합 테스트를 통과한 뒤에만 다음 변경을 적용한다. `refuted`나 `uncertain` 결과는 병합하지 않고 누락 사유를 보고한다.

진행 상황에 따라 작업을 다시 나눠야 하면 지속형 에이전트를 쓴다.

```
리더가 TaskCreate로 작업 묶음 등록(depends_on 포함)
→ Agent(name: "migrator-1"), Agent(name: "migrator-2"), Agent(name: "migrator-3") 병렬 실행
→ 완료 알림을 받을 때마다 결과 확인
→ 실패한 작업은 SendMessage로 원인을 확인한 뒤 TaskUpdate로 다시 배정
→ 모두 끝나면 통합 테스트
```

## 예시 5: 웹툰 제작 — 지속형 생성자와 단발 검토자

**구성:** 생성·검증

**선택 이유:** 생성자 한 명과 검토자 한 명만 필요하다. 검토 결과를 생성자에게 최대 두 번 돌려보내면 되므로 가벼운 혼합 모드로 충분하다.

```
1단계: Agent(name: "artist") → 패널 생성 → _workspace/panels/
2단계: Agent(subagent_type: "webtoon-reviewer", prompt: "패널을 검토하라") 한 번 호출 → PASS/FIX/REDO 판정
       → _workspace/review_report.md
3단계: REDO 판정을 받은 패널만 SendMessage({to: "artist"})로 재생성 지시
       최대 두 번 반복한다. artist가 이전 맥락을 기억하므로
       "3번 패널의 구도만 수정"처럼 범위를 좁혀 지시할 수 있다.
재시도 방침: 두 번 수정해도 통과하지 못하면 미해결 상태와 원인을 사용자에게 알린다.
             전체 패널의 50% 이상이 REDO이면 사용자에게 프롬프트 수정을 제안한다.
```

## 예시 6: 커머스 기능 개발과 QA — 지속형 개발자와 워크플로 QA의 혼합 모드

**구성:** 파이프라인 + 생성·검증

**선택 이유:** API 개발자와 프런트엔드 개발자는 응답 형식과 오류 코드를 맞추느라 여러 번 대화해야 하므로 이전 맥락을 기억해야 한다. 반면 QA는 모듈마다 같은 대조 항목을 확인하므로 워크플로로 정할 수 있다.

```
1단계(지속형 에이전트): Agent(name: "api-developer") + Agent(name: "frontend-developer") 병렬 실행
               → api-developer가 장바구니·주문 API 응답 형식을 _workspace/api_contract.md에 확정
               → SendMessage로 frontend-developer에 전달
               → 화면에 필요한 필드가 빠졌으면 frontend-developer가 SendMessage로 추가 요청
2단계(워크플로 조율): 모듈 하나가 완성될 때마다 QA 실행
         phase '대조': 모듈별로 qa-inspector가 API 응답과 프런트엔드 타입,
                      링크·라우터 경로, 주문 상태 전이를 대조
         phase '검증': 찾은 불일치마다 적대적 검증 → confirmed 항목만 개발자에게 전달
3단계(지속형 에이전트): confirmed 불일치를 SendMessage로 해당 개발자에게 보내 수정 지시
```

주문 상태(결제 대기 → 결제 완료 → 배송 중 → 배송 완료, 그리고 취소·환불)처럼 상태가 많은 기능은 상태 전이가 빠지기 쉽다. QA 체크리스트에 상태 전이표를 넣고, 각 전이를 처리하는 코드 위치를 대조하게 한다. 대조 방법은 `qa-agent-guide.md`의 「통합 정합성 검증」을 따른다. 모든 모듈을 만든 뒤 한꺼번에 QA를 하면 앞 모듈의 계약 불일치가 뒤 모듈까지 퍼지므로, 모듈을 완성할 때마다 실행한다.

## 예시 7: 운영 리포트와 정산 자동화 — 워크플로 조율

**구성:** 분산·통합 + 검산

**선택 이유:** 데이터 출처(주문, 결제, 환불, 광고비)를 미리 나열할 수 있고, 매주 같은 절차를 반복한다. 수집과 형식 변환은 일상 업무이므로 `sonnet`으로 충분하다.

```javascript
const SOURCE_RESULT = { type: 'object', required: ['source', 'rows', 'total'], properties: {
  source: { type: 'string' }, rows: { type: 'integer' }, total: { type: 'number' } } }
const collected = (await pipeline(args.sources,   // 예: ['orders', 'payments', 'refunds', 'ad_spend']
  s => agent(`${args.period} 기간의 ${s} 데이터를 읽어 _workspace/report_${s}.csv로 변환하고 건수와 합계를 반환하라.`,
    { phase: '수집', schema: SOURCE_RESULT, model: 'sonnet' })   // 반복적인 수집·변환
)).filter(Boolean)
const by = Object.fromEntries(collected.map(r => [r.source, r.total]))
const missing = ['orders', 'payments', 'refunds'].filter(s => !(s in by))
if (missing.length) return { collected, missing, diff: null }   // 출처가 빠지면 검산하지 않는다
// 금액 검산은 모델에 맡기지 않고 스크립트 코드로 계산한다
const diff = by.orders - by.payments + by.refunds
const investigation = Math.abs(diff) > args.tolerance
  ? await agent(`주문 합계와 결제·환불 합계가 ${diff}만큼 맞지 않는다. _workspace/report_*.csv를 대조해 원인 후보를 근거와 함께 찾아라.`,
      { phase: '검산', model: 'opus' })   // 원인 분석은 복잡한 판단이 필요
  : null
return { collected, missing, diff, investigation }
```

합계·차액처럼 정확해야 하는 계산은 에이전트가 아니라 스크립트 코드에서 한다. 모델은 데이터를 읽고 변환하는 일과, 숫자가 맞지 않을 때 원인을 찾는 일에만 쓴다. 출처 하나가 실패해 `collected`에서 빠지면 검산 결과를 믿을 수 없으므로, 검산을 건너뛰고 `missing`에 담긴 출처를 보고서에 표시한다.

## 예시 8: 광고·캠페인 성과 분석 — 워크플로 조율

**구성:** 분산·통합 + 적대적 검증

**선택 이유:** 분석할 캠페인이나 채널 목록을 미리 정할 수 있다. 성과 이상치는 실제 성과 변화가 아니라 집계 지연·추적 누락 같은 데이터 문제인 경우가 많으므로, 찾은 이상치를 하나씩 다시 검증해야 한다.

```
[메인] 분석 기간·캠페인 목록·핵심 지표(노출, 클릭, 전환, 광고비, ROAS) 확정
     → Workflow(script, args: {campaigns, period, ws})
         phase '분석': pipeline(campaigns, c => agent(..., {schema: ANOMALIES}))
                       캠페인마다 전 기간 대비 이상치와 근거 지표를 반환
         phase '검증': 이상치마다 적대적 검증 에이전트 실행
                       "데이터 문제(집계 지연, 추적 코드 누락, 중복 집계)로 설명되는가?"를 먼저 확인
                       → 실제 성과 변화만 confirmed
         phase '종합': confirmed 이상치로 원인 가설과 다음 조치 정리
     → 메인이 _workspace/campaign_report.md 작성
```

캠페인 수가 많으면 토큰 예산에 맞춰 분석 범위를 정한다(`workflow-recipes.md`의 「토큰 예산 연동 반복」). 데이터 문제로 판정한 이상치는 버리지 말고 보고서의 "데이터 점검 필요" 항목에 따로 적는다. 다음 리포트에서 같은 문제가 반복되는지 확인할 수 있다.

## 예시 9: 상품·프로모션 콘텐츠 제작 — 지속형 작성자와 단발 검토자

**구성:** 생성·검증

**선택 이유:** 작성자가 브랜드 톤과 앞서 받은 수정 요청을 기억해야 하므로 지속형 에이전트로 둔다. 검토는 브랜드 가이드와 광고 표현 기준을 대조해 결과만 돌려주면 되므로 단발 호출로 충분하다.

```
1단계: Agent(name: "copywriter") → 상세 페이지 문구·배너 문구 시안 작성 → _workspace/copy_draft.md
2단계(서브에이전트 병렬): brand-reviewer(브랜드 톤·용어) + compliance-reviewer(광고 표현 기준)
       각각 한 번 호출 → 문장별 PASS/FIX 판정과 이유 → _workspace/copy_review.md
3단계: FIX 판정을 받은 문장만 SendMessage({to: "copywriter"})로 수정 지시
       최대 두 번 반복한다. copywriter가 이전 맥락을 기억하므로
       "할인율 문장만 수정"처럼 범위를 좁혀 지시할 수 있다.
재시도 방침: 두 번 수정해도 통과하지 못한 문장은 원문과 검토 의견을 함께 사용자에게 넘긴다.
```

광고 표현 검토 기준(근거 없는 최상급 표현, 할인 전 가격 표기, 혜택 조건 누락 등)은 `compliance-reviewer`의 정의 파일이나 전용 스킬의 `references/`에 둔다. 기준이 바뀌면 그 파일만 고치면 되고, 작성자 프롬프트는 건드리지 않아도 된다. 최종 게시 여부는 사람이 판단한다.

---

## 산출물 저장 방식

- **에이전트 정의:** `프로젝트/.claude/agents/{name}.md`에 만든다. 핵심 역할, 작업 원칙, 입력·출력 규칙, 재호출 방법, 오류 처리, 협업 방법을 반드시 적는다. 지속형 에이전트에는 통신 규칙을, 워크플로에서 쓸 에이전트에는 구조화 출력 형식을 추가한다.
- **스킬:** `프로젝트/.claude/skills/{name}/SKILL.md`에 만들고, 필요하면 `references/`와 `scripts/`를 둔다.
- **오케스트레이터:** 실행 모드를 반드시 적는다. `orchestrator-template.md`의 템플릿을 사용한다.
- **중간 산출물:** `_workspace/{phase}_{agent}_{artifact}.{ext}` 형식으로 저장하고 검증이 끝난 뒤에도 남긴다.
