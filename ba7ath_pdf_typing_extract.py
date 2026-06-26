import sys
import pdfplumber
import json
import pandas as pd
from paddleocr import PaddleOCR
import numpy as np
import re
import concurrent.futures
import time

def guess_block_type(text, font_size=None, font_bold=None):
    if font_size and font_size > 15: return "Heading"
    if font_bold: return "Heading"
    if re.match(r'^\s*[\u2022\-\*]\s.*', text): return "List"
    if re.match(r'^\d+\.', text): return "List"
    if len(text.split()) < 7 and len(text) < 60: return "Subtitle"
    return "Paragraph"

def process_page(page_tuple):
    page, pnum, lang, min_text_len, dpi, use_gpu, ocr_global = page_tuple
    ocr = ocr_global
    blocks = []
    tables = []
    try:
        text_objects = (page.extract_words(use_text_flow=True, keep_blank_chars=True) or [])
        layout_text = (page.extract_text(layout=True) or "")
        tables = page.extract_tables()
        is_text_page = len(layout_text) > min_text_len
        images = page.images or []
        if is_text_page and text_objects:
            for word_obj in text_objects:
                txt = word_obj["text"].strip()
                typ = guess_block_type(txt, font_size=word_obj.get("size", 10), font_bold=word_obj.get("bold", False))
                blocks.append({"type": typ, "text": txt, "bbox": word_obj.get("bbox", (0,0,0,0))})
        for table in tables:
            if not table or not table[0]: continue
            df = pd.DataFrame(table[1:], columns=table[0])
            blocks.append({"type": "Table", "data": df.fillna("").values.tolist(), "columns": df.columns.tolist(), "bbox": (0,0,0,0)})
        if not is_text_page and images:
            page_img = page.to_image(resolution=dpi).original
            ocr_result = ocr.ocr(np.array(page_img), cls=True)
            lines = [line[1][0] for line in ocr_result[0]] if ocr_result and ocr_result[0] else []
            blocks.append({"type": "OCR", "text": "\n".join(lines), "bbox": (0,0,0,0)})
        return {"page": pnum+1, "blocks": blocks}
    except Exception as e:
        print(f"[ERREUR PAGE] page {pnum+1}: {str(e)}")
        blocks.append({"type": "Error", "text": f"[ERROR: {str(e)}]", "bbox": (0,0,0,0)})
        return {"page": pnum+1, "blocks": blocks}

def extract_pdf_structured(pdf_in, json_out, lang="en", min_text_len=70, dpi=170, page_timeout=80, progress_file=None, max_workers=3):
    ocr_global = PaddleOCR(lang=lang, use_angle_cls=True, use_gpu=True, rec_batch_num=6, det_batch_num=6)
    results = []
    with pdfplumber.open(pdf_in) as pdf:
        total_pages = len(pdf.pages)
        args = [(pdf.pages[pnum], pnum, lang, min_text_len, dpi, True, ocr_global) for pnum in range(total_pages)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pnum = {executor.submit(process_page, arg): arg[1] for arg in args}
            for future in concurrent.futures.as_completed(future_to_pnum):
                pnum = future_to_pnum[future]
                try:
                    result = future.result(timeout=page_timeout)
                except concurrent.futures.TimeoutError:
                    print(f"[SKIP Timeout] page {pnum+1} ignorée (>{page_timeout}s)")
                    result = {"page": pnum+1, "blocks":[{"type":"Skip","text":"[Timeout page]","bbox":(0,0,0,0)}]}
                except Exception as e:
                    print(f"[ERREUR PAGE] page {pnum+1}: {str(e)}")
                    result = {"page": pnum+1, "blocks":[{"type":"Error","text":f"[ERROR: {str(e)}]","bbox":(0,0,0,0)}]}
                results.append(result)
                if progress_file:
                    try:
                        with open(progress_file, "a", encoding="utf-8") as pf:
                            pf.write(f"{pnum+1}\n")
                    except Exception as exp:
                        print(f"[ERREUR ECRITURE PROGRESS] {str(exp)}")
                print(f"Page {pnum+1} traitée avec succès")

    results.sort(key=lambda x: x["page"])
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[PDFTypingExtract] {pdf_in} → {json_out} ({len(results)} pages)")

if __name__ == "__main__":
    pdf_in, json_out = sys.argv[1], sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else "en"
    progress_file = sys.argv[4] if len(sys.argv) > 4 else None
    extract_pdf_structured(pdf_in, json_out, lang, progress_file=progress_file, max_workers=3)
