# PDF Deep Reader — Claude Code Skill

PDF 문서의 텍스트, 표, 그래프, 다이어그램을 **멀티패스로 깊이 분석**하는 Claude Code 스킬.

pymupdf4llm으로 구조화된 텍스트/이미지를 추출하고, Claude 네이티브 비전으로 그래프의 수치 정보와 표의 정확성을 검증한다.

## 왜 필요한가?

Claude Code는 PDF의 **텍스트만** 효과적으로 추출하며, 그래프/차트/다이어그램 내부의 수치 정보는 파악하지 못한다. 이 스킬은:

- **"이 PDF 분석해줘"** 한 마디로, 텍스트 + 표 + 그래프 정보가 모두 포함된 분석 결과를 제공
- 대용량 문서(400+ 페이지)를 자동으로 청킹하여 처리
- 한국어/영문 PDF 모두 지원 (HWP→PDF 변환 문서 포함)

## 파이프라인

```
[Pass 1] analyze_structure.py  → structure.json (구조 분석 + 청킹)
[Pass 2] extract_content.py   → markdown + images/ (추출 + VISION_TARGET 마커)
[Pass 3] Claude 네이티브 비전  → 캡션 있는 이미지 분석 (그래프 수치, 다이어그램 해석)
[Pass 4] Claude 네이티브 비전  → 표 페이지 원본 이미지와 비교 검증
```

- **Pass 1~2**: Python 스크립트가 안정적으로 추출·청킹·캐싱
- **Pass 3~4**: Claude가 비전 분석·판단·검증

## 설치

### 1. 의존성 설치

```bash
pip install pymupdf4llm
```

### 2. 스킬 설치

```bash
# 스킬 디렉토리에 복사
cp -r . ~/.claude/skills/pdf-deep-reader/
```

또는 수동으로:

```
~/.claude/skills/pdf-deep-reader/
├── SKILL.md
├── scripts/
│   ├── analyze_structure.py
│   └── extract_content.py
└── references/
    └── caption_keywords.json
```

### 3. 사용

Claude Code에서:

```
이 PDF 분석해줘 /path/to/document.pdf
```

## 출력

PDF와 같은 디렉토리에 `{pdf_name}_analysis/` 폴더가 생성된다:

```
report_analysis/
├── report.md              # 전체 마크다운 (텍스트+구조)
├── vision_analysis.md     # 비전 분석 + 표 검증 결과
├── structure.json         # 문서 구조 맵
├── extract_meta.json      # 추출 메타데이터
├── images/                # 추출된 이미지 파일
└── chunks/                # (대용량 시) 섹션별 마크다운
```

## 주요 기능

| 기능 | 설명 |
|------|------|
| VISION_TARGET 마커 | 캡션 있는 이미지를 자동 감지하여 비전 분석 대상으로 마킹 |
| VISION_FALLBACK | 텍스트 추출 실패 페이지(HWP→PDF 등)를 감지하여 비전 폴백 처리 |
| 자동 청킹 | 목차 기반 또는 고정 크기로 대용량 문서를 섹션별 분할 |
| 캐싱 | 동일 PDF 재분석 시 Pass 1~2를 건너뛰어 처리 시간 단축 |
| 표 검증 | 마크다운 표를 원본 PDF 이미지와 비교하여 오류 보정 |
| 한/영 지원 | caption_keywords.json에 한국어·영문 키워드 모두 포함 |

## 트리거 조건

이 스킬은 PDF **분석/파악** 의도가 있는 요청에서 트리거된다:

- "이 PDF 분석해줘", "보고서 내용 파악해줘", "PDF에서 데이터 추출해줘"

다음은 기존 pdf 스킬이 처리:

- "PDF 합쳐줘", "PDF를 워드로 변환", "PDF 암호화"

## 테스트 결과

| PDF | 페이지 | 결과 |
|-----|--------|------|
| EFDC 매뉴얼 (영문) | 231p | VISION_TARGET 14개, 표 1개, 5청크 분할, 추출 비율 98.8% |
| 홍수위험지도 지침 (한국어, HWP→PDF) | 130p | VISION_FALLBACK 130페이지 전부 감지 |

## 라이선스

MIT
