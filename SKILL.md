---
name: pdf-deep-reader
description: >
  PDF 문서의 텍스트·표·그래프·다이어그램을 멀티패스로 깊이 분석하는 스킬.
  pymupdf4llm으로 구조화된 텍스트/이미지를 추출하고, Claude 네이티브 비전으로
  그래프 수치와 표 정확성을 검증한다.
  이 스킬은 PDF의 내용을 "이해"하고 "분석"하는 작업에 특화되어 있으며,
  단순 텍스트 추출이나 변환과는 다르다.
  반드시 사용해야 하는 경우: 사용자가 PDF의 내용 파악, 보고서 분석, 그래프/표 데이터 추출,
  문서 요약, 핵심 정보 정리를 요청할 때. 한국어/영문 PDF 모두 지원.
  트리거 키워드: "PDF 분석", "PDF 읽어줘", "보고서 분석", "보고서 내용 파악",
  "PDF에서 데이터 추출", "analyze PDF", "PDF 파악", "이 PDF 분석해줘",
  "보고서 파악해줘", "PDF 내용 정리", "PDF 요약", "이 문서 분석",
  "보고서에서 데이터 찾아줘", "PDF 그래프 분석".
  사용하지 않는 경우: PDF 병합, 분할, 워터마크 추가, PDF→워드 변환,
  PDF 암호화/복호화, 폼 채우기 등 단순 조작 작업은 기존 pdf 스킬이 처리.
---

# Hybrid PDF Deep Reader Skill

PDF 문서의 **모든 자료 형식**(텍스트, 표, 그래프, 다이어그램)을 멀티패스로 분석한다.
스크립트가 안정적으로 추출·청킹하고, Claude가 비전 분석·판단·검증을 수행한다.

## 스킬 디렉토리 경로 확인

이 스킬을 실행하려면 먼저 스크립트 경로를 확인해야 한다.
이 SKILL.md 파일이 로드된 경로에서 디렉토리를 추출하여 사용한다.

예를 들어 이 파일이 `C:/Users/user/.claude/skills/pdf-deep-reader/SKILL.md`에서 로드되었다면:
- analyze_structure.py → `C:/Users/user/.claude/skills/pdf-deep-reader/scripts/analyze_structure.py`
- extract_content.py → `C:/Users/user/.claude/skills/pdf-deep-reader/scripts/extract_content.py`

이 경로를 아래 워크플로 전체에서 사용한다. 이하 이 경로를 `SKILL_DIR`로 표기한다.

## 워크플로

### 1단계: 입력 확인

- 사용자가 제공한 PDF 파일 경로를 확인한다.
- PDF 파일이 존재하는지 확인한다.
- 출력 디렉토리를 결정한다: PDF와 같은 디렉토리에 `{pdf_name}_analysis/` 폴더.
- 캐시 무효화: 사용자가 "다시 분석", "재추출", "캐시 무시"를 요청한 경우, 두 스크립트를 `--force` 플래그와 함께 재실행한다. 스크립트가 자동으로 `images/`, `chunks/`, `extract_error.json` 등 기존 산출물을 정리한 뒤 재생성한다.

```
예시:
  입력: F:/docs/report.pdf
  출력: F:/docs/report_analysis/
```

### 2단계: Pass 1 — 구조 분석 (스크립트)

Bash로 analyze_structure.py를 실행한다 (timeout: 7200000):

```bash
python "SKILL_DIR/scripts/analyze_structure.py" "{pdf_path}" "{output_dir}"
```

실행 후 `{output_dir}/structure.json`을 Read로 읽는다.
summary 섹션을 확인하여 사용자에게 간단히 보고한다:

```
문서 구조 분석 완료:
- 총 {page_count}페이지, {chunks_count}개 섹션으로 분할
- 표 {total_tables}개 감지
- 텍스트 부족 페이지: {low_text_page_count}개 (비전 폴백 대상)
```

### 3단계: Pass 2 — 콘텐츠 추출 (스크립트)

Bash로 extract_content.py를 실행한다 (timeout: 7200000):

```bash
python "SKILL_DIR/scripts/extract_content.py" "{pdf_path}" "{output_dir}" --structure "{output_dir}/structure.json"
```

실행 후 `{output_dir}/extract_meta.json`을 Read로 읽어서 비전 분석 대상을 파악한다.

### 4단계: Pass 3 — 비전 분석 (Claude 직접 수행)

extract_meta.json을 기반으로 비전 분석을 수행한다.

#### 일반 비전 분석 (vision_targets)

`vision_targets` 목록의 이미지는 pymupdf4llm이 추출한 개별 이미지(그래프/다이어그램/사진)이다.
이미 크기 필터(로고/아이콘 배제)를 통과한 이미지들이므로 **전부** Read로 열어 비전 분석한다.
수량 제한 없이 모두 분석한다. 이미지가 많으면 30개 단위 배치로 나누어 처리한다.

각 엔트리는 다음 필드를 가진다:
- `page`: 페이지 번호
- `image_path`: `{output_dir}` 기준 상대 경로
- `context_snippet`: 이미지 전후 ±3줄의 마크다운 텍스트 (캡션 후보 포함 가능)

**캡션은 사전 저장되지 않는다.** Claude가 이미지 + `context_snippet`을 동시에 보고 맥락에 맞는 캡션을 직접 도출한다. 도출 시 우선순위:
1. `context_snippet`에 명시적 라벨(`그림/표/Figure/Table` + 번호/기호형 불릿 등)이 있으면 그 문구를 캡션으로 사용.
2. 명시적 라벨이 없고 이미지 위/아래에 제목형 한 줄이 있으면 그 줄을 캡션으로 사용.
3. 둘 다 없으면 이미지 내용과 주변 문맥을 종합해 1문장(20자 내외)으로 생성한 캡션을 사용하되, 생성된 캡션임을 `(생성)` 표기로 구분.

각 이미지에 대해:
1. `{output_dir}/{image_path}`를 Read 도구로 연다.
2. `context_snippet`을 참조해 캡션을 확정한다.
3. 이미지의 내용을 분석한다 (차트 유형, 축, 수치, 트렌드, 또는 다이어그램 구조).
4. 분석 결과를 사용자에게 보고하고, 별도 파일 `{output_dir}/vision_analysis.md`에 누적 저장한다.

그래프/차트인 경우:
```markdown
### Page {page_num}: {derived_caption}
> **[그래프 분석]** 유형: {차트 유형}
> X축: {설명}, Y축: {설명}
> 주요 수치: {핵심 데이터 포인트}
> 트렌드: {패턴 요약}
> 신뢰도: {직접 읽음 / 추정값 (±오차)}
```

다이어그램/사진/구조도인 경우:
```markdown
### Page {page_num}: {derived_caption}
> **[이미지 분석]** 유형: {다이어그램/사진/구조도/지도 등}
> 내용: {이미지가 보여주는 핵심 내용 설명}
> 주요 요소: {식별 가능한 핵심 요소 나열}
```

> **참고**: `extract_meta.json`의 `decoration_skips`는 크기 필터로 제외된 이미지(로고/아이콘/장식 등)이다. 기본적으로 분석 대상이 아니며, 사용자가 "누락 이미지도 분석해줘"라고 명시적으로 요청한 경우에만 추가로 처리한다.

### 5단계: Pass 4 — 페이지 이미지 통합 처리 (Claude 직접 수행)

`unified_vision_tasks` 목록은 페이지 전체 이미지를 기반으로 수행할 task(fallback, table_verify)를 페이지 단위로 묶은 것이다.
**동일 페이지 이미지는 1회만 Read하고, 해당 페이지에 속한 모든 task를 동시에 수행한다.**

각 엔트리의 `tasks` 배열은 다음 중 하나 이상을 포함한다:
- `fallback` — 텍스트 추출 실패 페이지 (HWP→PDF 변환, 스캔 등). 페이지 전체를 비전으로 읽어 내용을 복원한다.
- `table_verify` — 표 감지 페이지. 마크다운의 해당 페이지 표와 원본 이미지를 비교 검증한다.

> **완전성 원칙**: fallback/table_verify 대상은 수량과 관계없이 **전량 분석한다**. 이미지가 많으면 30개 단위 배치로 나누어 순차 처리하되, 분석 대상 범위를 사용자에게 확인받지 않는다. 분석 비용 상한을 두지 않는다.

#### OCR 선행 권장 안내 (조건부 정보 제공)

`tasks`에 `fallback`이 포함된 엔트리가 **1개 이상** 존재하면 Pass 4 시작 전에 사용자에게 한 번만 다음 안내를 출력한다 (응답을 기다리지 않고 그대로 분석 진행):

> "감지된 fallback 페이지 {N}개는 텍스트 추출이 불완전한 페이지입니다(HWP 변환/스캔 등). 이대로 비전 분석으로 내용을 복원합니다. 참고로, 향후 동일 PDF를 자주 분석할 예정이면 아래 명령으로 OCR 선행 PDF를 만들어두면 검색 가능한 텍스트를 확보할 수 있습니다. (이번 분석에는 영향 없음)
>
>     ocrmypdf input.pdf output.pdf --language kor+eng
>
> 필수는 아니며, 완전성 원칙에 따라 OCR 없이도 전량 분석합니다."

사용자가 중단/재시작을 요청하지 않는 한 즉시 다음 단계(처리 절차)로 진행한다.

#### 처리 절차

각 엔트리에 대해:
1. `{output_dir}/{image_path}`를 Read로 1회 연다.
2. `tasks`에 포함된 모든 task를 동일 이미지 컨텍스트에서 수행한다.
3. 결과를 `{output_dir}/vision_analysis.md`에 누적 저장한다.

`fallback` 결과 포맷:
```markdown
### Page {page_num}: 페이지 내용 복원 (fallback)
> **[비전 fallback]** 텍스트 추출 실패 페이지.
> 내용 요약: {페이지의 핵심 내용}
> 식별된 요소: {제목/본문/표/그림 등}
```

`table_verify` 결과 포맷:
```markdown
### Page {page_num}: 표 검증
> **[표 검증]** 원본 PDF 이미지와 비교 완료. {검증 결과}.
```

대형 복잡 표(30행 x 10열 이상)인 경우:
```markdown
> ⚠️ 대형 표 — 세부 수치의 오차 가능성 있음.
```

> **하위 호환**: `extract_meta.json`은 `vision_fallbacks`, `table_pages` 필드를 여전히 포함하지만 Pass 4는 `unified_vision_tasks`만 참조한다. 구 필드는 디버깅/로깅 용도로만 사용한다.

### 6단계: 종합 요약 산출 및 최종 보고

#### 분기 조건

- **Pass 3(vision_targets 전량) + Pass 4(unified_vision_tasks 전량)가 모두 성공 완료된 경우** → `{output_dir}/summary.md`를 생성한다.
- **일부가 미완료/실패 상태인 경우** (사용자 중단, Read 실패, 장시간 배치 중단 등) → `summary.md` 대신 `{output_dir}/partial_status.md`에 진행 상태만 기록한다.

#### `summary.md` 템플릿

문서 전체를 관통하는 통합 요약이다. 이미지별 노트 모음인 `vision_analysis.md`와 구분된다.

```markdown
# {pdf_name} 종합 요약

*생성일: {YYYY-MM-DD} | 기반: vision_analysis.md, {pdf_name}.md, extract_meta.json*

## 문서 개요
- 총 {total_pages}페이지 / {chunks_count}개 섹션
- 문서 유형: {보고서/논문/백서/매뉴얼 등}
- 핵심 주제: {1~2줄}

## 핵심 발견
- {문서에서 가장 중요한 3~7개 사실/주장. 페이지 인용 포함}

## 주요 수치
- {그래프/표에서 추출한 핵심 데이터 포인트. 단위·기간 명시}
- {수치 간 비교가 의미 있으면 요약}

## 결론
- {저자의 결론 또는 독자가 이 문서에서 얻어야 할 take-away. 3~5줄}
```

#### `partial_status.md` 템플릿

```markdown
# {pdf_name} 부분 분석 상태

*기록일: {YYYY-MM-DD}*

## 완료 상태
- Pass 1 구조 분석: {완료/실패}
- Pass 2 콘텐츠 추출: {완료/실패}
- Pass 3 비전 분석: {N/M개 완료}
- Pass 4 페이지 이미지 task: {N/M개 완료}

## 미완료 사유
- {사용자 중단 / Read 실패 / 기타}

## 재개 방법
- `--force` 없이 재실행 시 완료된 부분은 건너뛰고 남은 대상부터 처리됩니다.
- 전체 재분석이 필요하면 `--force` 플래그를 사용하세요.
```

#### 최종 보고 (사용자에게 출력)

```
PDF 분석 완료:
- 총 {total_pages}페이지 / {chunks_count}개 섹션
- 비전 분석: {vision_target_count}개 이미지
- 페이지 이미지 task: {unified_vision_task_count}개 (fallback {vision_fallback_count} + table {table_page_count}, 중복 제거)
- 출력: {output_dir}/

주요 발견 사항:
- {summary.md의 '핵심 발견' 섹션에서 3~5개 추출}
```

출력 파일 안내:
- `{pdf_name}.md` — 전체 마크다운 (텍스트+구조)
- `vision_analysis.md` — 이미지별 비전 분석 + 표 검증 상세 노트
- `summary.md` — 문서 수준 종합 요약 (Pass 3/4 전량 완료 시에만 생성)
- `partial_status.md` — 부분 완료 시 진행 상태 기록 (대체 산출물)
- `structure.json` — 문서 구조 맵
- `extract_meta.json` — 추출 메타데이터
- `images/` — 추출된 이미지 파일
- `chunks/` — (대용량 시) 섹션별 마크다운

## 주의사항

- **완전성 원칙**: 감지된 모든 이미지와 표를 빠짐없이 분석한다. 수량이나 시간 제한으로 건너뛰지 않는다. 분석 비용/범위에 대한 사용자 확인 게이트를 두지 않는다.
- **중간 저장**: 배치 처리 완료 시마다 vision_analysis.md에 즉시 반영한다.
- **캐싱**: structure.json 또는 extract_meta.json이 이미 존재하면 해당 Pass를 건너뛴다.
- **경로**: 모든 경로는 절대 경로로 처리한다.
- **에러**: 스크립트 실행 실패 시 에러 메시지를 사용자에게 그대로 전달한다. pymupdf4llm 미설치 시 `pip install pymupdf4llm` 안내를 제공한다.
- **timeout**: Bash 실행 시 timeout을 7200000 (최대값)으로 설정한다.
