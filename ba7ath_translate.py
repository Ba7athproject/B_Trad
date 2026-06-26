import sys
import json
import re
import time
from transformers import MarianMTModel, MarianTokenizer
import torch
print("PYTHON EXE:", sys.executable)

def get_tokenizer_and_model(pair):
    model = MarianMTModel.from_pretrained(f'Helsinki-NLP/opus-mt-{pair}')
    tokenizer = MarianTokenizer.from_pretrained(f'Helsinki-NLP/opus-mt-{pair}')
    if torch.cuda.is_available():
        model = model.to("cuda")
    return tokenizer, model

def clean_ocr_text(text):
    text = re.sub(r'[|\\]+', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\x0c', '').replace('\ufffd', '')
    return text.strip()

def split_text_sentences(text):
    sentences = re.split(r'(?<=[\.\!\?؟…])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences

def smart_chunk(sentences, max_words=350):
    groups = []
    current = []
    count = 0
    for s in sentences:
        n = len(s.split())
        if count + n > max_words and current:
            groups.append(' '.join(current))
            current = []
            count = 0
        current.append(s)
        count += n
    if current:
        groups.append(' '.join(current))
    return groups

def translate_blocks_batch(blocks, tokenizer, model, max_words=350, batch_size=8):
    trad_segs = [""] * len(blocks)
    chunks = []
    idxs = []
    for idx, block in enumerate(blocks):
        clean_t = clean_ocr_text(block["text"])
        sentences = split_text_sentences(clean_t)
        seg_chunks = smart_chunk(sentences, max_words=max_words)
        for chunk in seg_chunks:
            chunks.append(chunk)
            idxs.append(idx)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    n_total = (len(chunks) + batch_size - 1) // batch_size
    for i in range(0, len(chunks), batch_size):
        segs_batch = chunks[i:i+batch_size]
        try:
            batch = tokenizer(segs_batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
            if device == "cuda":
                batch = {k: v.to("cuda") for k, v in batch.items()}
            gen = model.generate(**batch, max_new_tokens=512)
            outs = [tokenizer.decode(g, skip_special_tokens=True) for g in gen]
            for out, idx_block in zip(outs, idxs[i:i+batch_size]):
                if trad_segs[idx_block]:
                    trad_segs[idx_block] += "\n" + out
                else:
                    trad_segs[idx_block] = out
        except Exception as e:
            print(f"[Erreur traduction batch]: {str(e)}")
            for idx_block in idxs[i:i+batch_size]:
                trad_segs[idx_block] += "\n[TRAD ERROR]"
        print(f"Batch {i//batch_size+1} {n_total}", flush=True)  # <-- Pour la barre de progression GUI
    return trad_segs

if __name__ == "__main__":
    infile, outfile, langpair = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(infile, encoding="utf-8") as f:
        pages = json.load(f)
    tokenizer, model = get_tokenizer_and_model(langpair)
    blocks_all = []
    idx_pairs = []
    for page_no, page in enumerate(pages):
        for block_idx, block in enumerate(page.get("blocks", [])):
            if block.get("type") in ["Paragraph", "Heading", "Subtitle", "List"] and "text" in block:
                blocks_all.append(block)
                idx_pairs.append((page_no, block_idx))
    print(f"Total blocs à traduire : {len(blocks_all)}")
    t0 = time.time()
    trad_results = translate_blocks_batch(blocks_all, tokenizer, model, max_words=350, batch_size=8)
    for (page_no, block_idx), trad in zip(idx_pairs, trad_results):
        pages[page_no]["blocks"][block_idx]["trad"] = trad
    dt = time.time() - t0
    print(f"Traduction de {len(blocks_all)} blocs terminée en {round(dt,2)}s.")
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
