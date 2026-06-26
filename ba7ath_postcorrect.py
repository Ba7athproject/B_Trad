import sys
import json
import requests
import time
import concurrent.futures

def llama_correct_batch(blocks, lang="arabe", endpoint="http://localhost:11434/api/generate", timeout=70):
    results = []
    for block in blocks:
        if block.get("trad") and block["trad"].strip():
            prompt = (
                f"Tu es traducteur professionnel natif. "
                f"Corrige, enrichis et perfectionne cette traduction en {lang}. "
                f"Ne conserve aucun artefact de l’automatique. "
                f"Retourne uniquement la version corrigée, idiomatique et fluide :\n----\n{block['trad']}\n----\n"
            )
            try:
                t0 = time.time()
                r = requests.post(
                    endpoint,
                    json={
                        "model": "llama3",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1}
                    },
                    timeout=timeout
                )
                data = r.json()
                tf = round(time.time() - t0, 2)
                corr = data.get('response', block['trad'])
                print(f"[OK bloc] corrigé en {tf}s")
                block["corrige"] = corr
            except Exception as e:
                print(f"[Erreur LLM bloc]: {e}")
                block["corrige"] = block["trad"]
        else:
            block["corrige"] = block.get("trad", "")
        results.append(block)
    return results

def postcorrect_with_llama3_parallel(pages, lang="arabe", max_workers=4, batch_size=8):
    # Regroupe tous les blocs à corriger avec leur index
    blocks_all = []
    index_pairs = []
    for page_no, page in enumerate(pages):
        for block_idx, block in enumerate(page.get("blocks", [])):
            if block.get("trad") and block["trad"].strip():
                blocks_all.append(block)
                index_pairs.append((page_no, block_idx))
    print(f"Total blocs à postcorriger : {len(blocks_all)}")
    t0 = time.time()
    # Méthode par batchs + pool threads
    corrected_blocks = [None] * len(blocks_all)
    def batch_iter(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for batch in batch_iter(blocks_all, batch_size):
            futures.append(executor.submit(llama_correct_batch, batch, lang))
        for i, fut in enumerate(concurrent.futures.as_completed(futures)):
            batch_result = fut.result()
            st = i*batch_size
            corrected_blocks[st:st+len(batch_result)] = batch_result
    dt = time.time() - t0
    print(f"Post-correction {len(blocks_all)} blocs terminée en {round(dt,2)}s")
    # Réinjection dans la structure pages
    for (page_no, block_idx), cor in zip(index_pairs, corrected_blocks):
        pages[page_no]["blocks"][block_idx]["corrige"] = cor.get("corrige", "")
    return pages

if __name__ == "__main__":
    infile, outfile = sys.argv[1], sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else "arabe"
    with open(infile, encoding="utf-8") as f:
        pages = json.load(f)
    corrected = postcorrect_with_llama3_parallel(pages, lang, max_workers=4, batch_size=6)
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(corrected, f, ensure_ascii=False, indent=2)
    print(f"[POSTCORRECT] {infile} → {outfile}")
