import ttkbootstrap as tb
from ttkbootstrap.constants import DANGER, OUTLINE, INFO, SUCCESS
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
from pathlib import Path
import json
import os
import sys
import threading
import time

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

PY_GPU = r"C:\Ba7ath_scripts\B_trad\venv-translate-gpu\Scripts\python.exe"

class Ba7athUI:
    def __init__(self, master):
        self.master = master
        master.title("Ba7ath PDF Pipeline Modular")
        master.geometry("750x560")
        master.configure(bg="#10141B")
        if os.path.exists("logo.png") and Image and ImageTk:
            try:
                self.logo_img = Image.open("logo.png").resize((60,60))
                self.logo = ImageTk.PhotoImage(self.logo_img)
                tk.Label(master, image=self.logo, bg="#10141B").pack(pady=(14, 4))
            except Exception:
                tk.Label(master, text="", bg="#10141B").pack(pady=(14, 4))
        else:
            tk.Label(master, text="", bg="#10141B").pack(pady=(14, 4))
        tk.Label(master, text="Ba7ath PDF Translator", font=("Helvetica", 17, "bold"),
                 foreground="#39FF14", bg="#10141B").pack(pady=(0, 12))

        frame_path = tb.Frame(master)
        frame_path.pack(pady=(4,2))
        self.file_entry = tb.Entry(frame_path, width=47, font=("Consolas",10))
        self.file_entry.pack(side=tk.LEFT, padx=4)
        tb.Button(frame_path, text="Sélectionner PDF…", bootstyle=SUCCESS, command=self.select_pdf).pack(side=tk.LEFT)

        frame_out = tb.Frame(master)
        frame_out.pack(pady=(10,2))
        self.entry_out = tb.Entry(frame_out, width=50, font=("Consolas",10))
        self.entry_out.pack(side=tk.LEFT, padx=6)
        tb.Button(frame_out, text="Enregistrer sous...", bootstyle=INFO, command=self.saveas).pack(side=tk.LEFT)

        frame_opt = tb.Frame(master)
        frame_opt.pack(pady=(12,3))
        tk.Label(frame_opt, text="Langue OCR :", fg="gray", bg="#10141B", font=("Segoe UI",11)).pack(side=tk.LEFT,padx=7)
        self.lang_var = tk.StringVar(value='en')
        tb.OptionMenu(frame_opt, self.lang_var, "en", "fr", "ar").pack(side=tk.LEFT)
        tk.Label(frame_opt, text="Traduction :", fg="gray", bg="#10141B", font=("Segoe UI",11)).pack(side=tk.LEFT,padx=18)
        self.trad_pair = tk.StringVar(value="en-fr")
        tb.OptionMenu(frame_opt, self.trad_pair, "en-fr", "fr-ar", "en-ar", "fr-en").pack(side=tk.LEFT)
        tk.Label(frame_opt, text="Post-correction :", fg="gray", bg="#10141B", font=("Segoe UI",11)).pack(side=tk.LEFT,padx=18)
        self.llm_var = tk.StringVar(value="oui")
        tb.OptionMenu(frame_opt, self.llm_var, "oui", "non").pack(side=tk.LEFT)

        self.progress = tk.DoubleVar()
        self.prog_bar = tb.Progressbar(master, orient="horizontal", length=690, variable=self.progress, style="success-striped")
        self.prog_bar.pack(pady=(18,5))
        self.status = tk.StringVar()
        tk.Label(master, textvariable=self.status, fg="#39FF14", bg="#10141B", font=("Segoe UI", 12)).pack(pady=4)
        self.log_file = "ba7ath_traduction.log"
        tb.Button(master, text="Lancer tout le Workflow", bootstyle=(DANGER, OUTLINE), 
                  command=self.launch_pipeline, width=30).pack(pady=16, ipadx=10, ipady=7)
        self.marian_var = tk.DoubleVar()
        self.marian_pb = tb.Progressbar(master, orient="horizontal", length=690, variable=self.marian_var, style="info-striped")
        self.marian_pb.pack(pady=(2,5))
        self.marian_pb["value"] = 0
        self.marian_pb["maximum"] = 100

        self.preview_btn = tb.Button(master, text="Aperçu Source/Trad", bootstyle=(INFO, OUTLINE), command=self.preview, width=22, state=tk.DISABLED)
        self.preview_btn.pack(pady=5)
        self.preview_window = None
        self.open_btn = tb.Button(master, text="Ouvrir le document", bootstyle=(SUCCESS, OUTLINE), command=self.open_docx, width=26, state=tk.DISABLED)
        self.open_btn.pack(pady=5)
        self.generated_doc_path = None
        self.pipeline_thread = None

    def select_pdf(self):
        fname = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if fname:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, fname)
            base = os.path.splitext(fname)[0]
            self.entry_out.delete(0, tk.END)
            self.entry_out.insert(0, f"{base}.translated.docx")

    def saveas(self):
        out = filedialog.asksaveasfilename(defaultextension=".docx",
                                           filetypes=[("Word DOCX", "*.docx")])
        if out:
            self.entry_out.delete(0, tk.END)
            self.entry_out.insert(0, out)

    def update_progress(self, pct, status=None):
        self.progress.set(pct)
        if status:
            self.status.set(status)
        self.master.update_idletasks()

    def log(self, msg):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] {msg}\n")

    def launch_pipeline(self):
        if self.pipeline_thread and self.pipeline_thread.is_alive():
            messagebox.showinfo("Info", "Traitement déjà en cours…")
            return
        self.pipeline_thread = threading.Thread(target=self.start_pipeline)
        self.pipeline_thread.start()

    def start_pipeline(self):
        def extraction_worker():
            pdf_path = self.file_entry.get()
            docx_out = self.entry_out.get()
            lang = self.lang_var.get()
            trad = self.trad_pair.get()
            use_llm = self.llm_var.get() == "oui"
            pdf_in = Path(pdf_path)
            json_struct = pdf_in.with_suffix(".struct.json")
            progress_file = str(pdf_in.with_suffix(".struct.progress"))
            if os.path.exists(progress_file):
                os.remove(progress_file)
            self.open_btn.config(state=tk.DISABLED)
            self.preview_btn.config(state=tk.DISABLED)
            self.update_progress(0, "→ Extraction typée PDF…")
            self.log(f"Début extract type {pdf_path}")

            subprocess.run([
                sys.executable, "ba7ath_pdf_typing_extract.py", 
                str(pdf_in), str(json_struct), lang, progress_file
            ], check=True)
            self.update_progress(25, "→ Traduction…")
            self.log("Extraction typée OK")
            self.traduction_phase(str(json_struct))  # <-- cast en str obligatoire

        threading.Thread(target=extraction_worker, daemon=True).start()

    def traduction_phase(self, json_struct):
        def trad_worker():
            pdf_path = self.file_entry.get()
            docx_out = self.entry_out.get()
            trad = self.trad_pair.get()
            use_llm = self.llm_var.get() == "oui"
            json_trad = str(Path(json_struct).with_suffix(".trad.json"))
            json_corrige = str(Path(json_struct).with_suffix(".corrige.json"))
            target_lang = trad.split("-")[-1]

            self.marian_var.set(0)
            proc = subprocess.Popen(
                [PY_GPU, "ba7ath_translate.py", str(json_struct), json_trad, trad],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            cur, total = 0, 1
            for line in proc.stdout:
                if line.startswith("Batch"):
                    parts = line.strip().split()
                    try:
                        cur = int(parts[1])
                        total = int(parts[2])
                    except Exception:
                        cur = 0
                        total = 1
                    percent = min(100, int(100 * cur / (total or 1)))
                    self.marian_var.set(percent)
                    self.status.set(f"MarianMT : batch {cur}/{total}")
                    self.master.update_idletasks()
            proc.stdout.close()
            proc.wait()
            self.marian_var.set(100)
            self.update_progress(55, "→ Post-correction LLM…")
            self.log("Traduction OK")

            # --- AJOUT : post-correction asynchrone via module dédié ---
            if use_llm:
                def corrige_worker():
                    self.status.set("LLM post-correction en cours…")
                    proc_corr = subprocess.Popen(
                        [PY_GPU, "ba7ath_postcorrect.py", json_trad, json_corrige, target_lang],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
                    )
                    for line in proc_corr.stdout:
                        self.status.set(f"LLM: {line.strip()}")
                        self.master.update_idletasks()
                    proc_corr.stdout.close()
                    proc_corr.wait()
                    self.update_progress(75, "→ Export DOCX…")
                    self.log("Correction LLM OK")
                    # Chaine ici export DOCX si tu veux
                threading.Thread(target=corrige_worker, daemon=True).start()
            else:
                self.update_progress(75, "→ Export DOCX…")
                # Chainer export DOCX ici si besoin

        threading.Thread(target=trad_worker, daemon=True).start()


    def open_docx(self):
        if self.generated_doc_path and os.path.isfile(self.generated_doc_path):
            os.startfile(self.generated_doc_path)

    def preview(self):
        pdf_path = self.file_entry.get()
        pdf_in = Path(pdf_path)
        json_trad = pdf_in.with_suffix(".struct.trad.json")
        if not os.path.exists(json_trad):
            messagebox.showinfo("Info", "Traduction non trouvée.")
            return
        with open(json_trad, encoding="utf-8") as f:
            trad_blocks = json.load(f)
        preview_txt = ""
        for page in trad_blocks[:2]:
            for block in page["blocks"][:5]:
                preview_txt += f"--- PAGE {page['page']} ---\n"
                preview_txt += f"[SOURCE]:\n{block.get('source') or block.get('text','')[:500]}\n\n"
                preview_txt += f"[TRAD]:\n{block.get('trad','')[:500]}\n\n"
        if self.preview_window and tk.Toplevel.winfo_exists(self.preview_window):
            self.preview_window.destroy()
        self.preview_window = tk.Toplevel(self.master)
        self.preview_window.title("Aperçu")
        text_area = tk.Text(self.preview_window, wrap=tk.WORD, font=("Consolas", 11), bg="#24262d", fg="#39FF14")
        text_area.insert("1.0", preview_txt)
        text_area.configure(state="disabled")
        text_area.pack(expand=1, fill=tk.BOTH, padx=12, pady=12)

if __name__ == "__main__":
    root = tb.Window(themename="darkly")
    app = Ba7athUI(root)
    root.mainloop()
