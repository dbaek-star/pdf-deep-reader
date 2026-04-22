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
    import pymupdf
except ImportError:
    sys.exit("pymupdf가 설치되지 않았습니다. 실행: pip install pymupdf")

try:
    import pymupdf4llm
except ImportError:
    sys.exit("pymupdf4llm이 설치되지 않았습니다. 실행: pip install pymupdf4llm")


SCHEMA_VERSION = 2


def load_extraction_config():
    config_path = Path(__file__).parent.parent / "references" / "extraction_config.json"
    defaults = {
        "vision_fallback_threshold": {"min_text_chars_per_page": 100},
        "image_size_filter": {"min_bytes": 10240, "min_pixels": 10000},
    }
    if config_path.exists():
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
        for key, default_val in defaults.items():
            if key in loaded:
                # shallow merge per subkey so user overrides partial fields cleanly
                merged = dict(default_val)
                merged.update(loaded[key])
                loaded[key] = merged
            else:
                loaded[key] = default_val
        return loaded
    return defaults


def save_page_as_image(doc, page_num, images_dir, dpi=150):
    img_filename = f"page_{page_num:04d}.png"
    img_path = images_dir / img_filename
    if img_path.exists():
        return img_filename
    page = doc[page_num - 1]
    # CMYK/이색 PDF 방어: RGB 강제. alpha=False로 PNG 저장 경로 안정화.
    # (투명 배경 다이어그램 렌더링 부작용 가능성은 회귀 테스트로 검증 예정.)
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    pix.save(str(img_path))
    return img_filename


def resolve_image_path(raw_path, output_dir, images_dir):
    """pymupdf4llm 마크다운의 이미지 경로를 실제 파일로 해석. 실패 시 None."""
    if not raw_path:
        return None
    p = Path(raw_path)
    candidates = []
    if p.is_absolute():
        candidates.append(p)
    candidates.append(output_dir / raw_path)
    candidates.append(images_dir / p.name)
    for c in candidates:
        try:
            if c.exists():
                return c
        except OSError:
            continue
    return None


def is_decoration(img_full_path, size_filter):
    """로고/아이콘 등 분석 가치가 낮은 이미지인지 보수적으로 판정."""
    try:
        if img_full_path.stat().st_size < size_filter["min_bytes"]:
            return True
    except OSError:
        return False
    try:
        pix = pymupdf.Pixmap(str(img_full_path))
        pixel_count = pix.width * pix.height
        if pixel_count < size_filter["min_pixels"]:
            return True
    except Exception:
        # 측정 실패 시 보수적으로 유지 (false negative 방지)
        return False
    return False


def attach_vision_context(
    page_text, page_num, output_dir, images_dir, size_filter, vision_targets, decoration_skips
):
    """페이지 텍스트에서 이미지 참조를 찾아 ±3줄 맥락을 수집하고 vision_targets에 등록.
    decoration 필터에 걸린 이미지는 decoration_skips에 기록하고 targets에서 제외.
    마크다운에는 간단한 디버그 주석만 삽입 (캡션은 Pass 3에서 LLM이 도출)."""
    lines = page_text.split("\n")
    new_lines = []

    for i, line in enumerate(lines):
        new_lines.append(line)

        if "![" not in line:
            continue

        img_match = re.search(r"!\[.*?\]\((.*?)\)", line)
        if not img_match:
            continue
        raw_path = img_match.group(1)

        img_full = resolve_image_path(raw_path, output_dir, images_dir)
        if img_full is None:
            # 파일 미존재: 경로를 있는 그대로 보존하되 targets에는 추가 안 함
            continue

        if is_decoration(img_full, size_filter):
            decoration_skips.append({
                "page": page_num,
                "image_path": raw_path,
                "reason": "size_below_threshold",
            })
            continue

        # 상대 경로로 정규화 (output_dir 기준)
        try:
            rel_path = img_full.relative_to(output_dir).as_posix()
        except ValueError:
            rel_path = raw_path

        context_start = max(0, i - 3)
        context_end = min(len(lines), i + 4)
        context_snippet = "\n".join(lines[context_start:context_end]).strip()

        marker = f"<!-- VISION_TARGET: page={page_num} path={rel_path} -->"
        new_lines.append(marker)

        vision_targets.append({
            "page": page_num,
            "image_path": rel_path,
            "context_snippet": context_snippet,
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
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cached_version = meta.get("schema_version")
        if cached_version == SCHEMA_VERSION:
            print(f"[캐싱] 추출 결과가 이미 존재합니다: {meta_path}")
            print(f"  비전 대상: {len(meta.get('vision_targets', []))}개")
            print(f"  비전 폴백: {len(meta.get('vision_fallbacks', []))}페이지")
            print(f"  표 페이지: {len(meta.get('table_pages', []))}개")
            print(f"  페이지 이미지 task: {len(meta.get('unified_vision_tasks', []))}개")
            return
        print(
            f"[캐시 무효] 스키마 버전 불일치 (캐시={cached_version}, 현재={SCHEMA_VERSION}) — 재추출"
        )

    config = load_extraction_config()
    fallback_threshold = config["vision_fallback_threshold"]["min_text_chars_per_page"]
    size_filter = config["image_size_filter"]
    structure = load_structure(structure_path)

    if structure:
        chunks_def = structure.get("chunks", [{"chunk_id": 1, "pages": [1, None], "title": "전체"}])
    else:
        chunks_def = [{"chunk_id": 1, "pages": [1, None], "title": "전체"}]

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    chunks_dir = output_dir / "chunks"

    # --force 시 기존 산출물(images, chunks) 정리. 캐시 파일은 이미 무시됨.
    if force:
        import shutil
        for d in (images_dir, chunks_dir):
            if d.exists():
                shutil.rmtree(d)
        err_file = output_dir / "extract_error.json"
        if err_file.exists():
            err_file.unlink()

    images_dir.mkdir(exist_ok=True)

    pdf_name = pdf_path.stem

    print(f"[Pass 2] 콘텐츠 추출 시작: {pdf_path.name}")

    # 페이지 이미지 저장용 공유 Document (한 번만 오픈)
    doc = pymupdf.open(str(pdf_path))

    if doc.is_encrypted:
        doc.close()
        sys.exit("암호화된 PDF입니다. 암호를 해제한 후 다시 시도하세요.")

    # pymupdf4llm 실행 (전체 페이지)
    print("  pymupdf4llm 실행 중...")
    try:
        result = pymupdf4llm.to_markdown(
            str(pdf_path),
            page_chunks=True,
            write_images=True,
            image_path=str(images_dir),
        )
    except Exception as e:
        import traceback
        err_info = {
            "schema_version": SCHEMA_VERSION,
            "pdf_path": str(pdf_path),
            "stage": "pymupdf4llm.to_markdown",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        err_path = output_dir / "extract_error.json"
        err_path.write_text(
            json.dumps(err_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        doc.close()
        sys.exit(
            f"to_markdown() 실패: {e}\n"
            f"  상세: {err_path}\n"
            f"  이미 생성된 images/는 보존됩니다. 재실행 시 재활용됩니다."
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
    decoration_skips = []
    # 페이지 이미지 단위로 task 누적 (fallback/table_verify)
    page_task_map = {}

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
            img_filename = save_page_as_image(doc, page_num, images_dir)
            page_text += f"\n\n<!-- VISION_FALLBACK: page {page_num} → images/{img_filename} -->\n"
            entry = page_task_map.setdefault(
                page_num,
                {"image_path": f"images/{img_filename}", "tasks": set()},
            )
            entry["tasks"].add("fallback")

        # VISION_TARGET 맥락 수집 (캡션은 Pass 3에서 LLM이 도출)
        page_text = attach_vision_context(
            page_text,
            page_num,
            output_dir,
            images_dir,
            size_filter,
            vision_targets,
            decoration_skips,
        )

        # 표 페이지 이미지 저장 (비전 검증용)
        if page_num in table_page_set:
            table_pages.append(page_num)
            img_filename = save_page_as_image(doc, page_num, images_dir)
            entry = page_task_map.setdefault(
                page_num,
                {"image_path": f"images/{img_filename}", "tasks": set()},
            )
            entry["tasks"].add("table_verify")

        # 청크에 추가
        chunk_id = page_to_chunk.get(page_num, 1)
        if chunk_id in chunk_texts:
            chunk_texts[chunk_id]["text"] += page_text + "\n\n"

    doc.close()

    unified_vision_tasks = [
        {
            "page": p,
            "image_path": entry["image_path"],
            "tasks": sorted(entry["tasks"]),
        }
        for p, entry in sorted(page_task_map.items())
    ]

    # 마크다운 파일 저장
    use_chunks = len(chunks_def) > 1
    written_files = []

    if use_chunks:
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
        "schema_version": SCHEMA_VERSION,
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
        "unified_vision_tasks": unified_vision_tasks,
        "unified_vision_task_count": len(unified_vision_tasks),
        "decoration_skips": decoration_skips,
        "decoration_skip_count": len(decoration_skips),
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
    print(f"  통합 페이지 이미지 task: {len(unified_vision_tasks)}개")
    print(f"  decoration 필터 제외: {len(decoration_skips)}개")


if __name__ == "__main__":
    main()
