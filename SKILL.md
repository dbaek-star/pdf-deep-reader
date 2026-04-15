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
- 캐시 무효화: 사용자가 "다시 분석", "재추출", "캐시 무시"를 요청한 경우, 출력 디렉토리 내의 `structure.json`과 `extract_meta.json`을 삭제한 뒤 진행한다.

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

`vision_targets` 목록의 이미지를 **전부** Read로 열어 비전 분석한다.
수량 제한 없이 모두 분석한다. 이미지가 많으면 30개 단위 배치로 나누어 처리한다.

각 이미지에 대해:
1. `{output_dir}/{image_path}`를 Read 도구로 연다.
2. 이미지의 내용을 분석한다 (차트 유형, 축, 수치, 트렌드, 또는 다이어그램 구조).
3. 분석 결과를 사용자에게 보고하고, 별도 파일 `{output_dir}/vision_analysis.md`에 누적 저장한다.

그래프/차트인 경우:
```markdown
### Page {page_num}: {caption}
> **[그래프 분석]** 유형: {차트 유형}
> X축: {설명}, Y축: {설명}
> 주요 수치: {핵심 데이터 포인트}
> 트렌드: {패턴 요약}
> 신뢰도: {직접 읽음 / 추정값 (±오차)}
```

다이어그램/사진/구조도인 경우:
```markdown
### Page {page_num}: {caption}
> **[이미지 분석]** 유형: {다이어그램/사진/구조도/지도 등}
> 내용: {이미지가 보여주는 핵심 내용 설명}
> 주요 요소: {식별 가능한 핵심 요소 나열}
```

#### VISION_FALLBACK 페이지 처리

`vision_fallbacks` 목록의 페이지는 텍스트 추출에 실패한 페이지이다 (HWP→PDF 변환 등).

- **50페이지 이하**: 전부 `{output_dir}/images/page_{NNNN}.png`를 Read로 비전 분석한다.
- **50페이지 초과**: 사용자에게 "이 PDF는 이미지 기반 문서(스캔/HWP 변환 등)로 보입니다. {N}페이지 중 분석할 범위를 지정해주세요. (예: 1-30, 전체)"라고 안내하고, 사용자 응답에 따라 처리한다.

### 5단계: Pass 4 — 표 검증 (Claude 직접 수행)

extract_meta.json의 `table_pages` 목록에 있는 페이지에 대해:
1. `{output_dir}/images/page_{NNNN}.png`를 Read로 열어 원본 표 이미지를 확인한다.
2. 마크다운의 해당 페이지 표와 원본 이미지를 비교한다.
3. 검증 결과를 `{output_dir}/vision_analysis.md`에 추가한다.

```markdown
### Page {page_num}: 표 검증
> **[표 검증]** 원본 PDF 이미지와 비교 완료. {검증 결과}.
```

대형 복잡 표(30행 x 10열 이상)인 경우:
```markdown
> ⚠️ 대형 표 — 세부 수치의 오차 가능성 있음.
```

### 6단계: 최종 보고

모든 비전 분석과 표 검증이 완료되면 사용자에게 결과를 요약 보고한다:

```
PDF 분석 완료:
- 총 {total_pages}페이지 / {chunks_count}개 섹션
- 비전 분석: {vision_target_count}개 이미지
- 비전 폴백: {vision_fallback_count}페이지
- 표 검증: {table_page_count}개 표
- 출력: {output_dir}/

주요 발견 사항:
- {문서의 핵심 내용 3~5줄 요약}
```

출력 파일 안내:
- `{pdf_name}.md` — 전체 마크다운 (텍스트+구조)
- `vision_analysis.md` — 비전 분석 + 표 검증 결과
- `structure.json` — 문서 구조 맵
- `images/` — 추출된 이미지 파일
- `chunks/` — (대용량 시) 섹션별 마크다운

## 주의사항

- **완전성 원칙**: 감지된 모든 이미지와 표를 빠짐없이 분석한다. 수량이나 시간 제한으로 건너뛰지 않는다 (VISION_FALLBACK 50페이지 초과 시만 사용자 확인).
- **중간 저장**: 배치 처리 완료 시마다 vision_analysis.md에 즉시 반영한다.
- **캐싱**: structure.json 또는 extract_meta.json이 이미 존재하면 해당 Pass를 건너뛴다.
- **경로**: 모든 경로는 절대 경로로 처리한다.
- **에러**: 스크립트 실행 실패 시 에러 메시지를 사용자에게 그대로 전달한다. pymupdf4llm 미설치 시 `pip install pymupdf4llm` 안내를 제공한다.
- **timeout**: Bash 실행 시 timeout을 7200000 (최대값)으로 설정한다.
