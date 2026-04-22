"""
analyze_structure.py — Pass 1: PDF 구조 분석 + 청킹 단위 결정

사용법: python analyze_structure.py <pdf_path> <output_dir>
출력:   <output_dir>/structure.json
"""

import io
import sys
import json
from pathlib import Path


def _ensure_utf8_console():
    """Windows cp949 등 비-utf8 콘솔에서 한국어 print 깨짐 방지.
    reconfigure 미지원(Python 3.6 이하 또는 stdout 치환 런타임) 환경에서는 조용히 넘어감."""
    for stream in (sys.stdout, sys.stderr):
        if not hasattr(stream, "reconfigure"):
            continue
        encoding = getattr(stream, "encoding", None) or ""
        if encoding.lower() == "utf-8":
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, io.UnsupportedOperation, OSError):
            pass


_ensure_utf8_console()

try:
    import pymupdf
except ImportError:
    sys.exit("pymupdf가 설치되지 않았습니다. 실행: pip install pymupdf")


SCHEMA_VERSION = 2


def load_config():
    config_path = Path(__file__).parent.parent / "references" / "extraction_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {"vision_fallback_threshold": {"min_text_chars_per_page": 100}}


def analyze_pages(doc, min_text_threshold):
    pages = []
    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text()
        text_len = len(text.strip())
        images = page.get_images()

        table_count = 0
        try:
            tabs = page.find_tables()
            # 오탐 필터: 최소 2행 × 2열. header는 옵션 메타데이터로 강등.
            # (header 기반 gate는 header 미감지 표를 누락시켜 완전성 원칙 위반)
            valid_tables = []
            for t in tabs.tables:
                try:
                    if len(t.rows) < 2:
                        continue
                except Exception:
                    continue

                col_count = getattr(t, "col_count", None)
                if col_count is None:
                    # 구버전 pymupdf 방어: 추출 결과에서 열 수 추정
                    try:
                        extracted = t.extract()
                        col_count = max((len(r) for r in extracted), default=0)
                    except Exception:
                        col_count = 0

                if col_count < 2:
                    continue
                valid_tables.append(t)
            table_count = len(valid_tables)
        except Exception:
            pass

        pages.append({
            "page": i + 1,
            "text_chars": text_len,
            "image_count": len(images),
            "table_count": table_count,
            "has_low_text": text_len < min_text_threshold,
        })
    return pages


def extract_toc(doc):
    raw_toc = doc.get_toc()
    toc = []
    for entry in raw_toc:
        level, title, page = entry[0], entry[1], entry[2]
        try:
            title = title.encode("utf-8", errors="replace").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        toc.append({"level": level, "title": title, "page": page})
    return toc


def merge_small_chunks(chunks, target_pages=100):
    if len(chunks) <= 1:
        return chunks

    # 병합 과정에서 title을 list로 관리 (원제목에 " + "가 포함돼도 안전)
    working = [dict(chunks[0], _titles=[chunks[0]["title"]])]
    for chunk in chunks[1:]:
        prev = working[-1]
        prev_size = prev["pages"][1] - prev["pages"][0] + 1
        curr_size = chunk["pages"][1] - chunk["pages"][0] + 1

        if prev_size + curr_size <= target_pages:
            prev["pages"][1] = chunk["pages"][1]
            prev["_titles"].append(chunk["title"])
        else:
            working.append(dict(chunk, _titles=[chunk["title"]]))

    merged = []
    for i, chunk in enumerate(working):
        titles = chunk.pop("_titles")
        if len(titles) <= 3:
            chunk["title"] = " + ".join(titles)
        else:
            chunk["title"] = f"{titles[0]} 외 {len(titles) - 1}개 섹션"
        chunk["chunk_id"] = i + 1
        merged.append(chunk)

    return merged


def determine_chunks(page_count, toc):
    if page_count <= 30:
        return [{"chunk_id": 1, "pages": [1, page_count], "title": "전체"}]

    level1_entries = [e for e in toc if e["level"] == 1]

    if level1_entries:
        # 페이지 기준 정렬 (TOC가 뒤섞인 문서 방어)
        level1_entries = sorted(level1_entries, key=lambda e: e["page"])

        # 동일 페이지에 여러 레벨1 엔트리가 있으면 제목을 " / "로 병합 (소실 방지)
        dedup_entries = []
        for entry in level1_entries:
            if dedup_entries and dedup_entries[-1]["page"] == entry["page"]:
                dedup_entries[-1]["title"] += f" / {entry['title']}"
            else:
                dedup_entries.append({"page": entry["page"], "title": entry["title"]})
        level1_entries = dedup_entries

        chunks = []
        for i, entry in enumerate(level1_entries):
            start_page = entry["page"]
            if i + 1 < len(level1_entries):
                end_page = level1_entries[i + 1]["page"] - 1
            else:
                end_page = page_count
            chunks.append({
                "chunk_id": i + 1,
                "pages": [start_page, end_page],
                "title": entry["title"],
            })

        if chunks and chunks[0]["pages"][0] > 1:
            chunks.insert(0, {
                "chunk_id": 0,
                "pages": [1, chunks[0]["pages"][0] - 1],
                "title": "서문",
            })

        return merge_small_chunks(chunks, target_pages=100)

    chunk_size = 50 if page_count > 100 else 30
    chunks = []
    for i in range(0, page_count, chunk_size):
        start = i + 1
        end = min(i + chunk_size, page_count)
        chunks.append({
            "chunk_id": len(chunks) + 1,
            "pages": [start, end],
            "title": f"Pages {start}-{end}",
        })
    return chunks


def main():
    if len(sys.argv) < 3:
        sys.exit("사용법: python analyze_structure.py <pdf_path> <output_dir> [--force]")

    pdf_path = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    force = "--force" in sys.argv

    if not pdf_path.exists():
        sys.exit(f"파일을 찾을 수 없습니다: {pdf_path}")

    structure_path = output_dir / "structure.json"
    if structure_path.exists() and not force:
        cached = json.loads(structure_path.read_text(encoding="utf-8"))
        cached_version = cached.get("schema_version")
        if cached_version == SCHEMA_VERSION:
            print(f"[캐싱] 구조 분석 결과가 이미 존재합니다: {structure_path}")
            print(cached.get("metadata", {}))
            return
        print(
            f"[캐시 무효] 스키마 버전 불일치 (캐시={cached_version}, 현재={SCHEMA_VERSION}) — 재분석"
        )

    config = load_config()
    min_text = config["vision_fallback_threshold"]["min_text_chars_per_page"]

    doc = pymupdf.open(str(pdf_path))

    if doc.is_encrypted:
        doc.close()
        sys.exit("암호화된 PDF입니다. 암호를 해제한 후 다시 시도하세요.")

    metadata = {
        "file_path": str(pdf_path),
        "file_name": pdf_path.name,
        "page_count": doc.page_count,
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
    }

    print(f"[Pass 1] 구조 분석 시작: {pdf_path.name} ({doc.page_count}페이지)")

    toc = extract_toc(doc)
    pages = analyze_pages(doc, min_text)
    chunks = determine_chunks(doc.page_count, toc)

    doc.close()

    summary = {
        "total_images": sum(p["image_count"] for p in pages),
        "total_tables": sum(p["table_count"] for p in pages),
        "low_text_pages": [p["page"] for p in pages if p["has_low_text"]],
        "low_text_page_count": sum(1 for p in pages if p["has_low_text"]),
        "pages_with_images": [p["page"] for p in pages if p["image_count"] > 0],
        "pages_with_tables": [p["page"] for p in pages if p["table_count"] > 0],
        "chunks_count": len(chunks),
    }

    result = {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "toc": toc,
        "pages": pages,
        "chunks": chunks,
        "summary": summary,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    structure_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[Pass 1] 완료: {structure_path}")
    print(f"  페이지: {metadata['page_count']}")
    print(f"  이미지: {summary['total_images']}")
    print(f"  표: {summary['total_tables']}")
    print(f"  텍스트 부족 페이지: {summary['low_text_page_count']}")
    print(f"  청크: {summary['chunks_count']}")


if __name__ == "__main__":
    main()
