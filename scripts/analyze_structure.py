"""
analyze_structure.py — Pass 1: PDF 구조 분석 + 청킹 단위 결정

사용법: python analyze_structure.py <pdf_path> <output_dir>
출력:   <output_dir>/structure.json
"""

import sys
import json
from pathlib import Path

try:
    import pymupdf
except ImportError:
    sys.exit("pymupdf가 설치되지 않았습니다. 실행: pip install pymupdf4llm")


def load_config():
    config_path = Path(__file__).parent.parent / "references" / "caption_keywords.json"
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
            table_count = len(tabs.tables)
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

    merged = [chunks[0]]
    for chunk in chunks[1:]:
        prev = merged[-1]
        prev_size = prev["pages"][1] - prev["pages"][0] + 1
        curr_size = chunk["pages"][1] - chunk["pages"][0] + 1

        if prev_size + curr_size <= target_pages:
            prev["pages"][1] = chunk["pages"][1]
            prev["title"] += " + " + chunk["title"]
        else:
            merged.append(chunk)

    for i, chunk in enumerate(merged):
        chunk["chunk_id"] = i + 1

    return merged


def determine_chunks(page_count, toc):
    if page_count <= 30:
        return [{"chunk_id": 1, "pages": [1, page_count], "title": "전체"}]

    level1_entries = [e for e in toc if e["level"] == 1]

    if level1_entries:
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
        print(f"[캐싱] 구조 분석 결과가 이미 존재합니다: {structure_path}")
        print(json.loads(structure_path.read_text(encoding="utf-8")).get("metadata", {}))
        return

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
