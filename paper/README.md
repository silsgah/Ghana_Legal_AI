# Paper: Sovereign Legal AI

## Structure

```
paper/
├── main.tex          # Full paper (ACL 2024 format, ~8 pages)
├── references.bib    # 25+ citations organised by section
├── figures/          # (create this; add architecture.pdf etc.)
└── README.md         # This file
```

## Compilation

```bash
# Using pdflatex + bibtex
cd paper
pdflatex main
bibtex main
pdflatex main
pdflatex main

# Or using latexmk (recommended)
latexmk -pdf main.tex
```

## Before Submitting

1. Download the official [ACL 2024/2025 style files](https://github.com/acl-org/acl-style-files)
2. Replace `\usepackage[hyperref]{acl2023}` with the correct year
3. Uncomment `\aclfinalcopy` for camera-ready
4. Fill all `TBD` fields with actual experimental results
5. Replace `\textit{[...]}` placeholder blocks with real prose
6. Add `figures/architecture.pdf`

## Sections to Complete (in order)

| # | Section | Status | Action Required |
|---|---------|--------|-----------------|
| 1 | Introduction | ✅ Drafted | Review & polish |
| 2 | Related Work | 📝 Skeleton | Write ~50-80 citation survey |
| 3 | Dataset | ✅ Drafted | Add expert validation results |
| 4 | Architecture | 📝 Skeleton | Add figure, expand prose |
| 5 | Retrieval | ✅ Partially | Expand search analysis |
| 6 | Fine-Tuning | ✅ Drafted | Fill ablation results |
| 7 | Evaluation | 📝 Skeleton | **Run experiments, fill tables** |
| 8 | Responsible AI | 📝 Skeleton | Expand discussion |
| 9 | Conclusion | ✅ Drafted | Update with final numbers |
