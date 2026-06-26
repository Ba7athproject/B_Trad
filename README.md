# Ba7ath PDF Translator (B_trad)

Ba7ath PDF Translator est un outil modulaire de traduction de documents PDF, intégrant l'extraction intelligente de texte, la traduction automatique neuronale, et la post-correction par modèle de langage local (LLM), le tout avec une interface graphique moderne.

## Architecture & Fonctionnement

Le projet est conçu autour d'un pipeline modulaire, composé des scripts suivants :

### 1. `ba7ath_trad.py` (Interface Graphique & Orchestrateur)
Ce script est le point d'entrée principal. Il lance une interface utilisateur moderne basée sur `ttkbootstrap` (Tkinter). 
Il orchestre l'exécution asynchrone (via des threads) des autres scripts pour former un pipeline complet :
- Sélection du PDF source.
- Déclenchement de l'extraction (`ba7ath_pdf_typing_extract.py`).
- Lancement de la traduction via `MarianMT` (`ba7ath_translate.py`).
- (Optionnel) Post-correction via un LLM local (`ba7ath_postcorrect.py`).
*Note : L'export final en DOCX peut être chaîné ou effectué manuellement.*

### 2. `ba7ath_pdf_typing_extract.py` (Extraction & Typage)
Ce module lit le fichier PDF source à l'aide de `pdfplumber`. 
- Il extrait le texte et essaie de deviner le type de chaque bloc (Titre, Paragraphe, Liste, Sous-titre) en analysant la taille et la mise en forme de la police.
- Il extrait également les tableaux avec `pandas`.
- Si des pages sont des images (scannées), il applique l'OCR avec `PaddleOCR` (support GPU).
- Il sauvegarde le résultat structuré dans un fichier JSON (`.struct.json`).

### 3. `ba7ath_translate.py` (Traduction Automatique)
Ce script utilise `Helsinki-NLP/opus-mt` (via `transformers` d'Hugging Face) pour traduire les textes.
- Il découpe intelligemment le texte en phrases et en lots (batches) pour ne pas dépasser la limite de tokens (max 350 mots par lot).
- Il utilise CUDA si un GPU est disponible pour accélérer la traduction.
- Il met à jour le fichier JSON avec une nouvelle clé contenant la traduction (`.trad.json`).

### 4. `ba7ath_postcorrect.py` (Post-Correction LLM)
Ce script améliore la qualité de la traduction automatique brute.
- Il fait appel à un serveur Ollama local (`http://localhost:11434/api/generate`) exécutant le modèle `llama3`.
- Il demande au LLM d'agir comme un traducteur natif pour corriger, enrichir et rendre le texte fluide et idiomatique, supprimant les artefacts de traduction automatique.
- Le traitement est multithreadé (par défaut 4 workers) pour accélérer le processus, puis sauvegardé dans un nouveau JSON (`.corrige.json`).

### 5. `ba7ath_json2docx_complex.py` (Export DOCX)
Ce script prend le JSON structuré et traduit pour générer un fichier Word (`.docx`).
- Il utilise `python-docx` pour reconstituer la mise en page (Titres, Paragraphes, Listes, Tableaux).
- Il intègre une fonction `is_arabic()` pour détecter l'arabe et appliquer automatiquement le formatage RTL (Right-to-Left) approprié aux paragraphes et listes.

## Environnements Virtuels
Le repo utilise des environnements virtuels isolés pour gérer les conflits de dépendances :
- `venv-paddleocr` : Utilisé principalement pour l'extraction PDF et PaddleOCR.
- `venv-translate-gpu` : Utilisé pour l'exécution des modèles PyTorch/Transformers (`ba7ath_translate.py`) et l'interface (`ba7ath_trad.py`).

Des scripts `.bat` (`Activenv.bat`, `Trad.bat`) sont fournis pour faciliter l'activation des environnements et le lancement des processus via la ligne de commande Windows.

## Lancement rapide
Pour lancer l'application avec l'interface graphique :
1. Activez l'environnement `venv-translate-gpu`.
2. Exécutez le script principal :
```bash
python ba7ath_trad.py
```
