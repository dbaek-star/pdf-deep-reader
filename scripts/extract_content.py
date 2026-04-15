"""
extract_content.py — Pass 2: 콘텐츠 추출 + VISION_TARGET 마커 + 청크 분할

사용법: python extract_content.py <pdf_path> <output_dir> [--structure structure.json]
출력:
  <output_dir>/{pdf_name}.md          (소규모: 단일 마크다운)
  <output_dir>/chunks/section_NN.md   (대규모: 청크별 마크다운)
  <output_dir>/images/                (추출된 이미지)
  <output_dir>/extract_meta.json      (추출 메타데이터)
"""

import sys
import json
import re
from pathlib import Path

try:
    import pymupdf4llm
    import pymupdf
except ImportError:
    sys.exit("pymupdf4llm이 설치되지 않았습니다. 실행: pip install pymupdf4llm")


def load_caption_keywords():
    config_path = Path(__file__).parent.parent / "references" / "caption_keywords.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        kw = config.get("vision_target_keywords", {})
        all_keywords = kw.get("en", []) + kw.get("ko", [])
        threshold = config.get("vision_fallback_threshold", {}).get("min_text_chars_per_page", 100)
        return all_keywords, threshold
    return ["Figure", "Fig.", "Table", "Chart", "그림", "표"], 100


def save_page_as_image(pdf_path, page_num, images_dir, dpi=150):
    doc = pymupdf.open(str(pdf_path))
    page = doc[page_num - 1]
    pix = page.get_pixmap(dpi=dpi)
    img_filename = f"page_{page_num:04d}.png"
    img_path = images_dir / img_filename
    pix.save(str(img_path))
    doc.close()
    return img_filename


def insert_vision_markers(page_text, page_num, keywords, vision_targets):
    lines = page_text.split("\n")
    new_lines = []

    for i, line in enumerate(lines):
        new_lines.append(line)

        if "![" not in line:
            continue

        context_start = max(0, i - 3)
        context_end = min(len(lines), i + 4)
        context_lines = lines[context_start:context_end]
        context_text = " ".join(context_lines)

        matched_keyword = None
        for kw in keywords:
            if kw.lower() in context_text.lower():
                matched_keyword = kw
                break

        if not matched_keyword:
            continue

        caption_line = ""
        for ctx_line in context_lines:
            if matched_keyword.lower() in ctx_line.lower():
                caption_line = ctx_line.strip().strip("*").strip()
                break

        marker = f"<!-- VISION_TARGET: {caption_line} -->"
        new_lines.append(marker)

        img_match = re.search(r"!\[.*?\]\((.*?)\)", line)
        img_path = img_match.group(1) if img_match else ""

        vision_targets.append({
            "page": page_num,
            "image_path": img_path,
            "caption": caption_line,
        })

    return "\n".join(new_lines)


def load_structure(structure_path):
    if structure_path and Path(structure_path).exists():
        return json.loads(Path(structure_path).read_text(encoding="utf-8"))
    return None


def main():
    if len(sys.argv) < 3:
        sys.exit("사용법: python extract_content.py <pdf_path> <output_dir> [--structure structure.json] [--force]")

    pdf_path = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    force = "--force" in sys.argv

    structure_path = None
    if "--structure" in sys.argv:
        idx = sys.argv.index("--structure")
        if idx + 1 < len(sys.argv):
            structure_path = sys.argv[idx + 1]

    if not pdf_path.exists():
        sys.exit(f"파일을 찾을 수 없습니다: {pdf_path}")

    meta_path = output_dir / "extract_meta.json"
    if meta_path.exists() and not force:
        print(f"[캐싱] 추출 결과가 이미 존재합니다: {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        print(f"  비전 대상: {len(meta.get('vision_targets', []))}개")
        print(f"  비전 폴백: {len(meta.get('vision_fallbacks', []))}페이지")
        print(f"  표 페이지: {len(meta.get('table_pages', []))}개")
        return

    keywords, fallback_threshold = load_caption_keywords()
    structure = load_structure(structure_path)

    if structure:
        chunks_def = structure.get("chunks", [{"chunk_id": 1, "pages": [1, None], "title": "전체"}])
    else:
        chunks_def = [{"chunk_id": 1, "pages": [1, None], "title": "전체"}]

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    pdf_name = pdf_path.stem

    print(f"[Pass 2] 콘텐츠 추출 시작: {pdf_path.name}")

    # pymupdf4llm 실행 (전체 페이지)
    print("  pymupdf4llm 실행 중...")
    result = pymupdf4llm.to_markdown(
        str(pdf_path),
        page_chunks=True,
        write_images=True,
        image_path=str(images_dir),
    )
    print(f"  {len(result)}페이지 추출 완료")

    # 페이지 번호 → 청크 매핑
    page_to_chunk = {}
    for chunk_def in chunks_def:
        start = chunk_def["pages"][0]
        end = chunk_def["pages"][1] or len(result)
        for p in range(start, end + 1):
            page_to_chunk[p] = chunk_def["chunk_id"]

    # 청크별 마크다운 수집
    chunk_texts = {}
    for chunk_def in chunks_def:
        chunk_texts[chunk_def["chunk_id"]] = {
            "title": chunk_def["title"],
            "text": "",
        }

    vision_targets = []
    vision_fallbacks = []
    table_pages = []

    # 표 페이지 사전 수집 (structure.json에서)
    table_page_set = set()
    if structure:
        table_page_set = set(structure.get("summary", {}).get("pages_with_tables", []))

    for page_chunk in result:
        page_num = page_chunk["metadata"]["page_number"]
        page_text = page_chunk["text"]

        # 텍스트 추출 실패 감지
        stripped_text = page_text.strip()
        # 마크다운 이미지 참조를 제외한 실제 텍스트 길이
        text_only = re.sub(r"!\[.*?\]\(.*?\)", "", stripped_text)
        text_only = re.sub(r"<!--.*?-->", "", text_only)
        actual_text_len = len(text_only.strip())

        if actual_text_len < fallback_threshold:
            vision_fallbacks.append(page_num)
            img_filename = save_page_as_image(pdf_path, page_num, images_dir)
            page_text += f"\n\n<!-- VISION_FALLBACK: page {page_num} → images/{img_filename} -->\n"

        # VISION_TARGET 마커 삽입
        page_text = insert_vision_markers(page_text, page_num, keywords, vision_targets)

        # 표 페이지 이미지 저장 (비전 검증용)
        if page_num in table_page_set:
            table_pages.append(page_num)
            save_page_as_image(pdf_path, page_num, images_dir)

        # 청크에 추가
        chunk_id = page_to_chunk.get(page_num, 1)
        if chunk_id in chunk_texts:
            chunk_texts[chunk_id]["text"] += page_text + "\n\n"

    # 마크다운 파일 저장
    use_chunks = len(chunks_def) > 1
    written_files = []

    if use_chunks:
        chunks_dir = output_dir / "chunks"
        chunks_dir.mkdir(exist_ok=True)

        for chunk_id, chunk_data in chunk_texts.items():
            md_filename = f"section_{chunk_id:02d}.md"
            md_path = chunks_dir / md_filename
            header = f"# {chunk_data['title']}\n\n"
            md_path.write_text(header + chunk_data["text"], encoding="utf-8")
            written_files.append(str(md_path))

        # 통합 마크다운도 생성
        full_md_path = output_dir / f"{pdf_name}.md"
        full_text = ""
        for chunk_id in sorted(chunk_texts.keys()):
            full_text += chunk_texts[chunk_id]["text"]
        full_md_path.write_text(full_text, encoding="utf-8")
        written_files.append(str(full_md_path))
    else:
        md_path = output_dir / f"{pdf_name}.md"
        md_path.write_text(chunk_texts[1]["text"], encoding="utf-8")
        written_files.append(str(md_path))

    # 추출 메타데이터 저장
    extract_meta = {
        "pdf_path": str(pdf_path),
        "pdf_name": pdf_name,
        "output_dir": str(output_dir),
        "total_pages": len(result),
        "chunks_count": len(chunks_def),
        "chunk_files": written_files,
        "vision_targets": vision_targets,
        "vision_target_count": len(vision_targets),
        "vision_fallbacks": vision_fallbacks,
        "vision_fallback_count": len(vision_fallbacks),
        "table_pages": table_pages,
        "table_page_count": len(table_pages),
        "images_dir": str(images_dir),
    }

    meta_path.write_text(
        json.dumps(extract_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[Pass 2] 완료: {output_dir}")
    print(f"  마크다운: {len(written_files)}개 파일")
    print(f"  비전 대상 (VISION_TARGET): {len(vision_targets)}개")
    print(f"  비전 폴백 (VISION_FALLBACK): {len(vision_fallbacks)}페이지")
    print(f"  표 페이지: {len(table_pages)}개")


if __name__ == "__main__":
    main()
