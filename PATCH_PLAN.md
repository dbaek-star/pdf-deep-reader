# PDF Deep Reader — 개선 패치 플랜 (v2)

- 초안: 2026-04-22 (v1)
- 개정: 2026-04-22 (v2) — Claude Opus 4.7 비판 검토 + Codex 독립 재검토 합의 반영
- 검토 이력: Claude 초안 → Codex 1차 → Claude 비판 → Codex 2차 → v2 확정

---

## v1 대비 주요 변경

1. **#5와 #7 병합** — 두 항목 모두 `save_page_as_image`를 수정하므로 단일 PR로 묶음 (신규 항목 `#5+#7`).
2. **캐시 스키마 버전 필드 도입** — `extract_meta.json`/`structure.json`에 `schema_version` 추가. 버전 불일치 시 자동 재분석.
3. **#3 배치 위치 명확화** — "main 함수 초반" → "캐시 체크 이후, `pymupdf4llm.to_markdown()` 호출 직전".
4. **#1 스펙 보강** — 한글 경계 lookbehind 추가, 번호 없는 의미 키워드는 별도 "의미 키워드" 리스트로 보존.
5. **#2 스펙 정리** — 죽은 역전 가드(step 3) 제거, 동일 페이지 중복 시 제목 병합 정책 명시.
6. **#6 null-safety** — `t.header`가 None인 경우 방어.
7. **#8 dedup 정책 재정의** — 단순 set이 아닌 "페이지+경로" 기준, 정당한 재사용 손실 가능성 명시.
8. **#11 `--force` 스크립트 동작 보정** — 문구 변경만이 아니라 스크립트의 `images/` 정리 동작도 추가.
9. **#12 환경변수 검증 단계** — 실제 Claude Code 런타임 변수 확인 후 스펙 확정.
10. **#13 title 구조 변경** — 문자열 누적 대신 list로 관리.
11. **#15 단정 완화** — "검정 렌더링" 단정 대신 회귀 테스트 케이스로 검증.
12. **#17 종속성 조건** — summary.md 생성은 Pass 3/4 성공 완료가 전제.
13. **#18 범위 확장** — `analyze_structure.py`뿐 아니라 `extract_content.py`의 ImportError 메시지도 분리. (Codex 추가 발견)

---

## 권장 작업 순서 (v2)

| 순위 | ID | 항목 | 유형 | 파일 | 상태 |
|---|---|---|---|---|---|
| 0 | #19 | 캐시 스키마 버전 필드 도입 (전제) | 호환성 | `analyze_structure.py`, `extract_content.py` | ✅ 완료 (2026-04-22) |
| 1 | #5+#7 | `save_page_as_image` 리팩터 + dedup + PDF 재오픈 제거 | 성능+일관성 | `extract_content.py`, `SKILL.md` | ✅ 완료 (2026-04-22) |
| 2 | #1 | **[재설계]** 정규식 제거 + 이미지 크기 필터 + 인라인 캡션 도출 | 신뢰도 | `extract_content.py`, `references/extraction_config.json`, `SKILL.md` | ✅ 완료 (2026-04-22) |
| 3 | #3 | 암호화 PDF 체크 (Pass 2) | 안정성 | `extract_content.py` | ✅ 완료 (2026-04-22) |
| 4 | #2 | TOC 청킹 정렬·중복 병합 | 신뢰도 | `analyze_structure.py` | ✅ 완료 (2026-04-22) |
| 5 | #15 | Pixmap 색공간/알파 처리 | 안정성 | `extract_content.py` | ✅ 완료 (2026-04-22) |
| 6 | #6 | `find_tables` 오탐 필터 (null-safe) | 비용 | `analyze_structure.py` | ✅ 완료 (2026-04-22) |
| 7 | #16 | ~~`insert_vision_markers` 중복 마커 방지~~ | 정확성 | `extract_content.py` | ❌ 불필요 (#1 재설계로 흡수) |
| 8 | #17-script | `to_markdown()` 실패 복구/진단 | 안정성 | `extract_content.py` | ✅ 완료 (2026-04-22) |
| 9 | #11-multi | ~~멀티라인 캡션 추출~~ | 품질 | `extract_content.py` | ❌ 불필요 (#1 재설계로 흡수) |
| 10 | #8 | `--force` 플래그 워크플로 + images 정리 | 일관성 | `SKILL.md`, `extract_content.py` | ✅ 완료 (2026-04-22) |
| 11 | #10 | ~~SKILL_DIR 경로 추출 명확화~~ | 신뢰성 | `SKILL.md` | ❌ 불필요 (Claude Code 스킬 활성화 전제상 자동 해석) |
| 12 | #18 | 의존성 에러 메시지 정확화 (두 스크립트) | DX | `analyze_structure.py`, `extract_content.py` | ✅ 완료 (2026-04-22) |
| 13 | #13 | `merge_small_chunks` title list 구조화 | UX | `analyze_structure.py` | ✅ 완료 (2026-04-22) |
| 14 | #6-policy | ~~비전 분석 티어 정책~~ | 비용 (정책) | `SKILL.md` | ❌ 불필요 (#1로 게이팅 해결 + 완전성 원칙 확정) |
| 15 | #12-ocr | 스캔 PDF OCR 대안 명시 (조건부 정보 제공) | 기능 | `SKILL.md` | ✅ 완료 (2026-04-22) |
| 16 | #14 | 최종 `summary.md` 산출 | 기능 | `SKILL.md` | ✅ 완료 (2026-04-22) |

> **PR 그룹 권장**:
> - **PR #1 (전제)**: #19 단독. 스키마 버전 도입 + 하위호환 무효화 로직.
> - **PR #2 (신뢰도)**: #5+#7, #1, #3, #2 묶음.
> - **PR #3 (안정성)**: #15, #6, #16, #17-script.
> - **PR #4 이후**: 점진.

※ v1에서 ID가 혼란스러웠던 "#11 멀티라인 캡션"과 "#11 `--force`"를 `#11-multi`/`#8`로 재명명.

---

## 상세 명세

### [0] #19 — 캐시 스키마 버전 필드 🔴 (신규, 전제) — ✅ 완료 (2026-04-22)

**구현 결과**:
- `analyze_structure.py`: `SCHEMA_VERSION = 2` 상수 추가, 캐시 히트 분기에서 버전 비교 후 불일치 시 재생성, `result`에 `schema_version` 필드 포함.
- `extract_content.py`: 동일 패턴 적용, `extract_meta`에 `schema_version` 필드 포함.
- `python -m py_compile` 통과.


**문제**: 이후 패치(#5+#7 등)가 `extract_meta.json`/`structure.json` 필드를 확장한다. 구 버전에서 생성된 캐시가 존재하면 히트 분기(`extract_content.py:115`, `analyze_structure.py:139`)가 구 포맷을 그대로 반환하고 종료해, 신규 필드를 참조하는 SKILL.md 로직이 조용히 빈 작업으로 넘어간다.

**해결**:
```python
SCHEMA_VERSION = 2  # 각 스크립트 상단 상수

# 캐시 히트 분기에서
cached = json.loads(meta_path.read_text(encoding="utf-8"))
if cached.get("schema_version") != SCHEMA_VERSION:
    print(f"[캐시 무효] 스키마 버전 불일치 (캐시={cached.get('schema_version')}, 현재={SCHEMA_VERSION}) — 재분석")
    # fall through to regeneration
else:
    # 기존 캐시 사용 분기
    ...

# 결과 저장 시
result["schema_version"] = SCHEMA_VERSION
```

**적용 위치**:
- `analyze_structure.py:139-142` 및 결과 저장부(`result` dict)
- `extract_content.py:115-121` 및 결과 저장부(`extract_meta`)

**검증**: v1 캐시가 남은 디렉토리에서 v2 실행 시 자동 재생성되는지 확인.

---

### [1] #5+#7 — `save_page_as_image` 통합 리팩터 🔴 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `extract_content.py`:
  - `save_page_as_image` 시그니처를 `(doc, page_num, images_dir, dpi=150)`로 변경, `if img_path.exists(): return` 가드 추가.
  - main에서 `doc = pymupdf.open(...)` 1회 오픈, 루프 종료 후 `doc.close()`.
  - `page_task_map`으로 fallback/table_verify task를 페이지 단위로 누적.
  - `extract_meta.json`에 `unified_vision_tasks`, `unified_vision_task_count` 필드 추가. 기존 `vision_fallbacks`, `table_pages`는 하위 호환 위해 유지.
- `SKILL.md`:
  - Pass 3은 `vision_targets`(개별 이미지)만 담당으로 정리.
  - Pass 4를 "페이지 이미지 통합 처리"로 재정의. `unified_vision_tasks`를 참조해 동일 페이지 이미지는 1회 Read로 모든 task 동시 수행.
  - 50페이지 초과 fallback 가드는 유지(기존 위치에서 이동).
  - 최종 보고 포맷에 `unified_vision_task_count` 반영.
- `python -m py_compile` 통과.


**문제**:
- (#5) `vision_fallbacks`와 `table_pages` 교집합 페이지는 `save_page_as_image`가 두 번 호출됨
- (#5) 동일 페이지 이미지가 Pass 3(비전 분석)과 Pass 4(표 검증)에서 각각 Read/분석됨
- (#7) 페이지당 `pymupdf.open()` — fallback + table 페이지에서만 발생하지만 대형 보고서에선 누적 비용

**위치**: `extract_content.py:35-43`, `extract_content.py:185-196`, `SKILL.md` Pass 3/4

**해결**:
1. main 상단에서 `doc = pymupdf.open(str(pdf_path))`로 한 번만 open, 종료 시 `doc.close()`.
2. 시그니처를 `save_page_as_image(doc, page_num, images_dir, dpi=150)`로 변경.
3. 함수 내에서 `if img_path.exists(): return img_filename` 가드.
4. 페이지별 이미지 저장 상태를 메인 루프에서 dict로 추적하여 중복 호출 방지.
5. `extract_meta.json`에 통합 작업 리스트 추가:
   ```json
   "unified_vision_tasks": [
     {
       "page": 12,
       "image_path": "images/page_0012.png",
       "tasks": ["fallback", "table_verify"],
       "caption": "..."
     }
   ]
   ```
   단, 기존 `vision_targets` / `vision_fallbacks` / `table_pages`는 **하위 도구 호환을 위해 유지** (deprecated 표시만). v3에서 제거 예정을 주석으로 남김.
6. `SKILL.md`: Pass 3·4 지시를 "페이지 이미지를 1회 Read하고 해당 페이지의 모든 task(비전/표검증)를 동시 수행"으로 개정.

**주의**: `pymupdf4llm.to_markdown()`이 내부에서 별도로 PDF를 열므로 외부 `doc` 오픈과 공존해도 문제 없음(pymupdf는 배타 락 걸지 않음). Windows 환경에서 한 차례 smoke test 권장.

**전제**: #19(스키마 버전) 선행.

---

### [2] #1 — 정규식 제거 + 이미지 크기 필터 + 인라인 캡션 도출 🔴 (재설계) — ✅ 완료 (2026-04-22)

**구현 결과**:
- `references/caption_keywords.json` 삭제, `references/extraction_config.json` 신설 (임계값만 포함, schema_version=2).
- `extract_content.py`:
  - `load_caption_keywords()` 제거, `load_extraction_config()` 신설 (사용자 부분 오버라이드 허용).
  - `insert_vision_markers()` 제거, `attach_vision_context()`로 대체.
  - `is_decoration()`, `resolve_image_path()` 헬퍼 신설.
  - `vision_targets` 엔트리 구조 변경: `{page, image_path, context_snippet}` (caption/confidence 필드 제거).
  - `extract_meta`에 `decoration_skips`, `decoration_skip_count` 추가.
- `SKILL.md` Pass 3:
  - Claude가 이미지+`context_snippet`을 동시에 보고 캡션을 직접 도출하도록 지시 추가.
  - 캡션 도출 우선순위 3단계 명시 (명시적 라벨 → 제목형 한 줄 → 생성 캡션 `(생성)` 표기).
  - `decoration_skips`는 기본 미분석, 사용자 요청 시에만 처리.
- Import/sanity check 통과 (PYTHONIOENCODING=utf-8).
- **연쇄 정리**: `#11-multi` 멀티라인 캡션, `#16` 중복 마커 방지는 본 재설계로 불필요해져 폐기.


**v1 대비 변경 배경**: 불특정 다수 PDF의 캡션 스타일은 작성자별로 편차가 커서(`그림 3-1`, `<표 5>`, `■ 매출 동향`, `[그래프] 변화`, 라벨 없는 제목 등) 일반 정규식으로 일관 감지 불가능. 게다가 현 SKILL.md는 `vision_targets`를 **전부** 분석하라고 지시(완전성 원칙) — 캡션 감지가 실질적 게이팅으로 기능하지 않고, 단지 오탐 시 이미지가 누락되는 결함만 남는다. **LLM이 Pass 3에서 이미지와 주변 텍스트를 동시에 보고 캡션을 직접 도출하는 편이 본질적으로 더 강건하다.**

**문제**: 정규식 유지 시 한국어 스타일 다양성 대응 불가. 정규식 제거 시 로고/아이콘까지 분석 대상이 되어 비용 폭증 위험.

**위치**: `extract_content.py`(캡션 감지 전체), `references/caption_keywords.json`(포맷/이름), `SKILL.md` Pass 3 지시.

**해결**:

1. **설정 파일 정리**: `references/caption_keywords.json` → `references/extraction_config.json`으로 리네임. 내용은 임계값만 남김.
   ```json
   {
     "schema_version": 2,
     "vision_fallback_threshold": {"min_text_chars_per_page": 100},
     "image_size_filter": {
       "min_bytes": 10240,
       "min_pixels": 10000
     }
   }
   ```

2. **`insert_vision_markers()` → `attach_vision_context()`로 대체**:
   - 이미지 주변 ±3줄 마크다운을 `context_snippet`으로 수집.
   - 캡션 탐색/마커 삽입은 하지 않음 (마크다운에 간단한 `<!-- VISION_TARGET: page=N path=X -->` 디버그 주석만 남김).
   - `vision_targets` 엔트리 구조:
     ```json
     {"page": 12, "image_path": "images/xxx.png", "context_snippet": "...±3줄 텍스트..."}
     ```
   - `caption`/`confidence` 필드 제거.

3. **이미지 크기 필터 (`is_decoration()`)**:
   - 파일 크기 < `min_bytes`(10KB) → decoration으로 제외.
   - 픽셀 수 < `min_pixels`(100×100) → decoration으로 제외 (pymupdf.Pixmap으로 측정).
   - 어느 쪽도 측정 실패 시 보수적으로 포함 (false negative 방지).

4. **SKILL.md Pass 3**: Claude가 이미지 + `context_snippet`을 동시에 보고 캡션을 스스로 도출하도록 지시. 출력 포맷의 `### Page N: {caption}`에서 {caption}은 Claude가 텍스트 맥락과 이미지 내용을 종합해 생성.

**장점**:
- 캡션 스타일 다양성에 본질적으로 강건.
- `caption_keywords.json` 및 관련 정규식 유지보수 부담 제거.
- context_snippet이 디버깅 시 사람도 맥락을 즉시 확인 가능.

**단점/트레이드오프**:
- 이미지 크기 필터 임계값 튜닝 필요 (초기값: 10KB, 100×100).
- "물리적으로 작지만 의미 있는 썸네일 차트"는 드물게 누락 가능. 해당 케이스는 사용자 피드백으로 임계값 조정.

**검증**:
- 다양한 한국어 캡션 스타일 PDF(라벨형/괄호형/기호형/무라벨형)에서 모든 유의미 이미지가 `vision_targets`에 포함되는지 확인.
- 로고/아이콘 위주 PDF에서 decoration 필터가 이들을 실제로 걸러내는지 확인.
- Pass 3에서 Claude가 `context_snippet` 없는 이미지에서도 최소한 페이지 번호 기반 임시 캡션을 생성하는지 확인.

---

### [3] #3 — 암호화 PDF 체크 (Pass 2) 🔴 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `extract_content.py:209-211`에 `doc.is_encrypted` 체크 삽입. 캐시 히트 반환 이후, `pymupdf4llm.to_markdown()` 호출 직전 위치. 암호화 감지 시 `doc.close()` 후 한국어 메시지로 종료.
- 순서 검증: `meta_path.exists()` 캐시 체크 < `is_encrypted` < `pymupdf4llm.to_markdown` (파이썬 소스 인덱스 assert로 확인).


**문제**: `extract_content.py`는 `is_encrypted` 체크 없이 `pymupdf4llm.to_markdown()` 호출. Pass 1 캐시만 남은 상태에서 Pass 2 단독 실행 시 의문의 실패.

**위치**: `extract_content.py`, **캐시 히트 분기(`line 115-121`) 이후, `pymupdf4llm.to_markdown()` 호출(`line 141`) 직전**.

**해결**:
```python
# 캐시 체크(line 115-121) 이후

# to_markdown() 호출 직전
doc = pymupdf.open(str(pdf_path))
if doc.is_encrypted:
    doc.close()
    sys.exit("암호화된 PDF입니다. 암호를 해제한 후 다시 시도하세요.")
doc.close()

print("  pymupdf4llm 실행 중...")
result = pymupdf4llm.to_markdown(...)
```

**주의**: #5+#7 이후라면 이미 `doc`이 메인에서 열려 있을 수 있다. 그 경우 `doc.close()` 없이 `doc.is_encrypted`만 체크하고 에러 시 `doc.close()` 후 exit.

---

### [4] #2 — TOC 청킹 정렬·중복 병합 🔴 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `analyze_structure.py:determine_chunks`에서 `level1_entries`를 페이지 기준 정렬.
- 동일 페이지 복수 엔트리 감지 시 `title`을 `" / "`로 병합 (dedup_entries 루프).
- 죽은 역전 가드(v1 step 3)는 미구현 — 정렬 이후 논리적으로 트리거 불가.
- 단위 테스트 2케이스 통과:
  - 뒤섞인 TOC: Ch3/Ch1/Ch2 입력 → 정렬 후 Ch1→Ch2→Ch3 순서 유지.
  - 동일 페이지 중복: A(p10)/B(p10) → `"A / B"` 병합 확인.


**문제**: `determine_chunks`가 TOC가 오름차순이라고 가정. 실제로는 순서가 뒤섞이거나 동일 페이지에 복수 엔트리 존재 가능. 단순히 중복 제거 시 뒤 항목 제목이 소실됨.

**위치**: `analyze_structure.py:85-124`

**해결**:
```python
level1_entries = [e for e in toc if e["level"] == 1]

# 1) 페이지 기준 정렬
level1_entries = sorted(level1_entries, key=lambda e: e["page"])

# 2) 동일 페이지 엔트리 제목 병합
merged_entries = []
for entry in level1_entries:
    if merged_entries and merged_entries[-1]["page"] == entry["page"]:
        merged_entries[-1]["title"] += f" / {entry['title']}"
    else:
        merged_entries.append(dict(entry))  # copy
level1_entries = merged_entries
```

**삭제**: v1의 step 3(역전 가드)은 정렬 이후엔 논리적으로 트리거 불가능한 죽은 코드 — 제거.

**검증**: TOC 순서가 뒤섞인 PDF 1개 + 동일 페이지 복수 엔트리 PDF 1개. 두 번째 케이스에서 병합된 제목이 `chunks[*].title`에 `"A / B"` 형태로 보존되는지 확인.

---

### [5] #15 — Pixmap 색공간/알파 처리 🟠 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `extract_content.py:save_page_as_image`의 `page.get_pixmap(dpi=dpi)`를 `page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)`로 변경.
- `pymupdf.csRGB` 심볼 존재 확인.
- CMYK PDF와 투명 배경 다이어그램 PDF 회귀 테스트는 테스트 fixture 부재로 스킵. 테스트 전략 시나리오 8~9번으로 추적 중.


**문제**: `save_page_as_image`의 `page.get_pixmap(dpi=dpi)`가 CMYK 페이지에서 색공간 불일치로 PNG 저장 실패 가능.

**위치**: `extract_content.py:35-43` (또는 #5+#7 이후의 리팩터된 함수)

**해결**:
```python
pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
```

**검증**:
- CMYK 이미지 포함 PDF에서 저장 성공 여부.
- **투명 배경 다이어그램 PDF**에서 렌더링 결과의 배경색 확인. v1에서 "검정으로 렌더링"이라 단정했으나 환경/문서에 따라 다름 — 회귀 테스트로 실측.
- 만약 투명 다이어그램 배경이 의도치 않게 렌더링되면 `alpha=True` 유지 + 색공간만 `csRGB`로 강제하는 옵션 재검토.

---

### [6] #6 — `find_tables` 오탐 필터 (null-safe) 🟠 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `analyze_structure.py:analyze_pages`에 필터 추가.
- `len(t.rows) < 2` 체크는 `try/except`로 감싸 안전화.
- `getattr(t, "header", None)` 후 `getattr(header, "names", None)`로 null-safe. header가 None이거나 names가 비면 제외.
- `header_names < 2`인 경우도 제외. 결과적으로 최소 2행 × 2열 구조 표만 통과.


**문제**: pymupdf의 `find_tables`는 레이아웃만 갖춘 페이지를 표로 잡는 오탐이 있음. v1 제안 `len(t.header.names) >= 2`는 `t.header`가 None일 때 AttributeError.

**위치**: `analyze_structure.py:34-38`

**해결**:
```python
tabs = page.find_tables()
valid_tables = []
for t in tabs.tables:
    if len(t.rows) < 2:
        continue
    header = getattr(t, "header", None)
    header_names = getattr(header, "names", None) if header is not None else None
    if not header_names or len(header_names) < 2:
        continue
    valid_tables.append(t)
table_count = len(valid_tables)
```

최소 2행 × 2열 필터 + header null-safe.

---

### [7] #16 — `insert_vision_markers` 중복 마커 방지 🟡

**문제**: 같은 이미지 경로에 대해 중복 마커가 누적될 수 있음 (재처리 시나리오 또는 pymupdf4llm 출력 특성).

**위치**: `extract_content.py:46-88`

**해결**: 페이지 단위로 `seen_img_paths` 집합을 유지. `vision_targets`에 추가하기 전 `(page_num, img_path)` 튜플 체크.

```python
seen_img_paths_per_page = set()  # (page_num, img_path)

# 루프 내
key = (page_num, img_path)
if key in seen_img_paths_per_page:
    continue
seen_img_paths_per_page.add(key)
```

**주의/트레이드오프**: 동일 이미지가 **서로 다른 정당한 캡션 컨텍스트에서 두 번 참조되는 경우**(재사용 로고, 반복 도식) 뒤쪽 참조는 마커가 누락됨. 현재는 "중복 마커 누적 방지"를 우선하고, 정당한 재사용 손실은 수용. 향후 중요도가 드러나면 "캡션 텍스트도 dedup 키에 포함"으로 완화 검토.

---

### [8] #17-script — `to_markdown()` 실패 복구/진단 🟡 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `extract_content.py`에서 `pymupdf4llm.to_markdown()` 호출을 `try/except Exception`으로 감쌈.
- 실패 시 `{output_dir}/extract_error.json`에 `schema_version`, `pdf_path`, `stage`, `error`, `traceback` 기록.
- `sys.exit`에 원인 + 에러 파일 경로 + 이미지 보존 안내 포함.
- `doc.close()`가 `sys.exit` 이전에 실행되도록 리소스 정리 순서 검증.


**문제**: 전체 실패 시 부분 산출물 정리/진단 없음.

**위치**: `extract_content.py:141-147`

**해결**:
```python
try:
    result = pymupdf4llm.to_markdown(...)
except Exception as e:
    import traceback
    err_info = {
        "pdf_path": str(pdf_path),
        "stage": "pymupdf4llm.to_markdown",
        "error": str(e),
        "traceback": traceback.format_exc(),
    }
    (output_dir / "extract_error.json").write_text(
        json.dumps(err_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    sys.exit(f"to_markdown() 실패: {e}. 상세: {output_dir}/extract_error.json")
```

이미 생성된 `images/` 일부는 보존 → 다음 실행에서 `if img_path.exists()` 가드(#5+#7)가 재활용.

---

### [9] #11-multi — 멀티라인 캡션 추출 🟡

**문제**: `그림 3-1. 매출 추이\n(단위: 억원)` 같은 경우 두 번째 줄 유실.

**위치**: `extract_content.py:71-74` (#1 구현 이후)

**해결**: 매칭된 캡션 라인 직후 1~2줄을 다음 조건으로 병합:
- 시작 문자가 `(`, `（`인 경우
- `단위`, `출처`, `자료`, `주:` 중 하나로 시작하는 경우
- 소문자 영문 또는 마침표 없이 이어지는 경우

병합된 캡션은 줄바꿈 대신 `" "`로 연결하여 `caption_line`에 저장.

---

### [10] #8 — `--force` 플래그 워크플로 + images 정리 🟢 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `extract_content.py`: `force=True`이면 `images/`, `chunks/`, `extract_error.json`을 삭제 후 재생성.
- 중복되던 `chunks_dir` 선언 제거(main 상단에서 1회 선언).
- `analyze_structure.py`는 `structure.json` 단일 파일만 생성하므로 별도 정리 불필요 (덮어쓰기로 충분).
- `SKILL.md` 캐시 무효화 안내를 "파일 수동 삭제" → "`--force` 플래그 재실행 + 자동 정리"로 변경.
- 격리 테스트로 정리 로직이 실제로 대상을 제거하는지 확인.


**문제**:
- (문서) SKILL.md는 "파일 수동 삭제"로 안내하지만 스크립트에 `--force`가 존재.
- (스크립트) `extract_content.py`의 `--force`는 캐시 체크만 건너뛰고 기존 `images/` 디렉토리를 정리하지 않음(`line 131-133`에서 `exist_ok=True`). 결과적으로 구 이미지가 혼재.

**위치**: `SKILL.md:42`, `extract_content.py:103, 131-133`

**해결**:
1. 스크립트: `--force` 시 `images/`를 제거하고 재생성.
   ```python
   if force and images_dir.exists():
       import shutil
       shutil.rmtree(images_dir)
   images_dir.mkdir(parents=True, exist_ok=True)
   ```
   `chunks/`도 동일 처리.
2. SKILL.md: "재분석 요청 시 `--force` 플래그를 붙여 스크립트를 재실행한다. 기존 `images/`, `chunks/`는 자동으로 정리된다"로 변경.

---

### [11] #10 — SKILL_DIR 경로 추출 명확화 🟢 — ❌ 불필요 (2026-04-22)

**폐기 사유**: Claude Code가 스킬을 활성화한 시점에 이미 스킬 루트 경로를 해석해 `SKILL.md`를 로드했다는 의미. 스킬 디렉토리 구조(`<root>/SKILL.md`, `<root>/scripts/`, `<root>/references/`)는 규약으로 고정되어 있어 Claude가 맥락에서 자연스럽게 해석 가능. 현재 SKILL.md 문구("이 SKILL.md 파일이 로드된 경로에서 디렉토리를 추출하여 사용한다")가 이미 올바른 지침. 환경변수/Glob 보강은 확인되지 않은 심볼을 박아 오히려 새로운 실패 모드를 만들 위험. 가상의 실패 모드였다고 판단.


**문제**: Claude가 "SKILL.md가 로드된 경로"를 정확히 알지 못할 수 있음. v1 제안의 `$CLAUDE_PLUGIN_ROOT`는 실제 Claude Code 런타임에 존재한다고 보장되지 않음.

**위치**: `SKILL.md:24-33`

**해결**:
1. **사전 조사**: 실제 Claude Code가 주입하는 환경변수 목록 확인 (문서 또는 소스 확인). 후보: `$CLAUDE_PLUGIN_ROOT`, `$CLAUDE_SKILL_DIR`, 없음.
2. **확인된 변수가 있으면**: SKILL.md에 해당 변수 사용 + 첫 실행 시 `ls "$VAR/scripts/"`로 존재 검증 단계 추가.
3. **없으면**: 첫 실행 시 사용자에게 "스크립트 경로가 `X`가 맞습니까?"를 한 번 확인받는 가드 스텝 명시.

**결정 필요**: 환경변수 존재 여부 조사 결과에 따라 2 또는 3으로 확정.

---

### [12] #18 — 의존성 에러 메시지 정확화 🟢 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `analyze_structure.py`: `pymupdf` 누락 시 안내를 `pip install pymupdf`로 수정 (기존 `pymupdf4llm` 오안내 제거).
- `extract_content.py`: 단일 try 블록을 두 개로 분리. `pymupdf` 누락은 `pip install pymupdf`, `pymupdf4llm` 누락은 `pip install pymupdf4llm`로 각각 안내.
- Codex 추가 발견 반영 완료.


**문제**:
- `analyze_structure.py:12-15`는 `pymupdf`만 import하는데 누락 시 `pip install pymupdf4llm` 안내.
- `extract_content.py:17-21`은 `pymupdf4llm`과 `pymupdf`를 **한 try 블록에서** import하고 어느 쪽이 빠져도 `pymupdf4llm` 미설치라고 안내. (Codex 추가 발견)

**위치**: `analyze_structure.py:12-15`, `extract_content.py:17-21`

**해결**:
```python
# analyze_structure.py
try:
    import pymupdf
except ImportError:
    sys.exit("pymupdf가 설치되지 않았습니다. 실행: pip install pymupdf")

# extract_content.py
try:
    import pymupdf
except ImportError:
    sys.exit("pymupdf가 설치되지 않았습니다. 실행: pip install pymupdf")
try:
    import pymupdf4llm
except ImportError:
    sys.exit("pymupdf4llm이 설치되지 않았습니다. 실행: pip install pymupdf4llm")
```

---

### [13] #13 — `merge_small_chunks` title list 구조화 🟢 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `merge_small_chunks`에서 제목을 `_titles` list로 관리. 병합 시 `.append()`, 최종 렌더링 시 `len(titles) <= 3`이면 `" + ".join`, 초과 시 `"{첫 제목} 외 N-1개 섹션"` 축약.
- `chunk_id` 재부여도 최종 렌더링 루프에서 처리.
- 단위 테스트 4케이스 통과:
  - 2개 병합: `A + B` 정상.
  - 4개 병합: `Sec1 외 3개 섹션` 축약.
  - 원제목에 ` + ` 포함(`A + B` + `C`): `A + B + C`로 안전 연결 (string split 기반이면 오판했을 케이스).
  - 원제목 ` + ` + 4개 총합: `A + B 외 3개 섹션`로 첫 제목 보존.


**문제**: v1 "3개 초과 시 축약" 제안은 문자열 `" + "` split 기반이라 **원제목에 ` + `가 포함된 섹션**에서 오판.

**위치**: `analyze_structure.py:63-82`

**해결**: 병합 과정에서 title을 list로 관리하다가 최종 렌더링.
```python
def merge_small_chunks(chunks, target_pages=100):
    if len(chunks) <= 1:
        return chunks

    # 내부적으로 title을 list로 관리
    for c in chunks:
        c["_titles"] = [c["title"]]

    merged = [chunks[0]]
    for chunk in chunks[1:]:
        prev = merged[-1]
        prev_size = prev["pages"][1] - prev["pages"][0] + 1
        curr_size = chunk["pages"][1] - chunk["pages"][0] + 1
        if prev_size + curr_size <= target_pages:
            prev["pages"][1] = chunk["pages"][1]
            prev["_titles"].extend(chunk["_titles"])
        else:
            merged.append(chunk)

    for i, chunk in enumerate(merged):
        chunk["chunk_id"] = i + 1
        titles = chunk.pop("_titles")
        if len(titles) <= 3:
            chunk["title"] = " + ".join(titles)
        else:
            chunk["title"] = f"{titles[0]} 외 {len(titles) - 1}개 섹션"

    return merged
```

---

### [14] #6-policy — 비전 분석 우선순위 티어 정책 🟢 (정책 결정 필요) — ❌ 불필요 (2026-04-22)

**폐기 사유**:
- `#1` B안 재설계에서 `decoration_skips` 크기 필터로 "무의미 이미지(로고/아이콘) 배제 + 나머지 전량 분석" 게이팅이 이미 달성됨.
- 사용자가 완전성 원칙을 명시적으로 확정: "이 스킬은 PDF에서 최대한 많은 정보를 추출하기 위한 목적이므로 이미지 갯수의 상한선을 설정하는 것도 반대한다".
- 따라서 v2 플랜의 B안(confidence 기반 티어)/C안(30개 초과 시 확인)은 모두 불필요.
- 본 원칙은 메모리에 `completeness_over_cost.md`로 영구 저장. 향후 비용 절감 목적의 상한/티어 신설은 사용자 확인 없이 불가.

**후속 정리 (2026-04-22)**:
- `SKILL.md` Pass 4의 "50페이지 초과 fallback 가드" 섹션 제거. fallback/table_verify는 수량 무관 전량 분석으로 변경.
- `SKILL.md` 주의사항의 "VISION_FALLBACK 50페이지 초과 시만 사용자 확인" 예외 조항 제거. 완전성 원칙 문구에 "분석 비용/범위에 대한 사용자 확인 게이트를 두지 않는다" 추가.


**문제**: "모든 이미지 무제한 분석" 원칙이 대용량 보고서에서 비용 폭발.

**위치**: `SKILL.md` Pass 3

**해결 후보**:
- **A안**: 현행 유지 (완전성 우선)
- **B안**: 티어 분리 — `confidence: high` 매칭(#1 참조)은 전량, `medium`/`low`는 소형(<100×100) 이미지면 스킵
- **C안**: 30개 초과 시 사용자에게 범위 확인

> **결정 필요**: B안이 #1 개정과 자연스럽게 연동됨. 사용자 선택 필요.

---

### [15] #12-ocr — 스캔 PDF OCR 대안 명시 🟢 — ✅ 완료 (2026-04-22)

**구현 결과**:
- A안(조건부) 채택하되 **완전성 원칙과 충돌하지 않도록 "대체"가 아닌 "정보 제공"** 형태로 구현.
- `SKILL.md` Pass 4에 "OCR 선행 권장 안내 (조건부 정보 제공)" 섹션 신설.
- 트리거: `unified_vision_tasks` 중 `fallback` 포함 엔트리가 1개 이상 존재할 때.
- 동작: Pass 4 시작 전 사용자에게 한 번만 안내 출력. **응답을 기다리지 않고 즉시 분석 진행**.
- 메시지 포함 사항: fallback 페이지 수, `ocrmypdf` 명령 예시(한국어+영문), "이번 분석에는 영향 없음" 명시, "완전성 원칙에 따라 OCR 없이도 전량 분석" 명시.
- 사용자가 명시적으로 중단/재시작을 요청한 경우에만 대응.


**문제**: 전량 VISION_FALLBACK이 비용 큼. 검색 가능한 텍스트 산출 불가.

**위치**: `SKILL.md` 4단계 VISION_FALLBACK 섹션

**해결**: "50페이지 초과 시" 분기에 `ocrmypdf` 또는 Tesseract 기반 OCR 선행 옵션 안내 문구 추가.

```
50페이지 초과 시, 비전 분석 대신 OCR 선행을 권장합니다:
  ocrmypdf input.pdf output.pdf --language kor+eng
OCR 후 결과 PDF로 재분석하면 검색 가능한 텍스트가 확보됩니다.
```

---

### [16] #14 — 최종 `summary.md` 산출 🟢 — ✅ 완료 (2026-04-22)

**구현 결과**:
- `SKILL.md` 6단계를 "최종 보고"에서 "종합 요약 산출 및 최종 보고"로 재구성.
- **분기 조건** 명시: Pass 3/4 전량 성공 시 `summary.md`, 부분 미완료 시 `partial_status.md`.
- **`summary.md` 템플릿**: 문서 개요 / 핵심 발견 / 주요 수치 / 결론 4섹션. 페이지 인용·단위·기간 명시 지침 포함.
- **`partial_status.md` 템플릿**: 각 Pass 완료 상태, 미완료 사유, 재개 방법(`--force` 가이드) 포함.
- **최종 보고 포맷**: `summary.md`의 핵심 발견에서 3~5개를 추출해 표시하도록 지시.
- 출력 파일 안내에 `summary.md`, `partial_status.md`, `extract_meta.json` 추가.


**문제**: `vision_analysis.md`는 이미지별 노트 모음. 문서 수준 통합 요약이 별도 산출물로 없음.

**위치**: `SKILL.md` 6단계

**해결**: 6단계 말미에 다음 지시 추가:
> **종속성**: Pass 3 및 Pass 4가 모두 성공 완료된 경우에만 `{output_dir}/summary.md`를 생성한다. 일부 이미지/표 검증이 사용자 중단 또는 실패로 미완료 상태라면 `summary.md` 대신 `{output_dir}/partial_status.md`에 진행 상태만 기록한다.

템플릿:
```markdown
# {pdf_name} 종합 요약

## 핵심 발견
- ...

## 주요 수치
- ...

## 결론
- ...

---
*생성일: {date} | 기반: vision_analysis.md, extract_meta.json*
```

---

## 테스트 전략

각 PR마다 다음 시나리오로 회귀 테스트:

1. **소형 일반 PDF** (10p, 텍스트 위주) — 기본 동작.
2. **대형 TOC PDF** (200p+, 다단계 목차) — 청킹 로직 (#2).
3. **동일 페이지 복수 TOC 엔트리 PDF** — 제목 병합 (#2).
4. **표 다수 PDF** — 표 감지/검증 (#6).
5. **레이아웃만 있는 false positive 표 페이지** — 필터 검증 (#6).
6. **스캔 PDF / HWP 변환 PDF** — VISION_FALLBACK 경로.
7. **암호화 PDF** — 에러 핸들링 (#3).
8. **CMYK 이미지 포함 PDF** — 색공간 처리 (#15).
9. **투명 배경 다이어그램 PDF** — `alpha=False` 부작용 검증 (#15).
10. **v1 캐시가 남은 디렉토리** — 스키마 버전 무효화 (#19).
11. **한국어 캡션 false positive 테스트** — "지도/수도/제도" 등이 본문에 섞인 PDF에서 캡션 오매칭 0건 (#1).
12. **번호 없는 한국어 캡션 PDF** — "매출 추이" 등 의미 키워드 기반 매칭 (#1).

---

## 참고

- 초안 검토: Claude Opus 4.7 → Codex CLI 1차
- v2 개정 트리거: Claude의 비판 검토 + Codex의 2차 독립 검토 (14개 항목 중 11 완전동의, 3 부분동의, 1 추가 발견)
- v2 합의 포인트:
  - 전제 항목 `#19` 신설 (스키마 버전)
  - `#5+#7` 병합
  - `#18` 범위 확장 (`extract_content.py`까지) — Codex 추가 발견 반영
  - `#15`의 "검정 렌더링" 단정 완화 → 회귀 테스트로 전환
