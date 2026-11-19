"""Builds data/catalog.json from the content files and the PDFs.
Run again with:  python build_catalog.py   (only needed if you add PDFs)."""
import json, glob, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
pdfs = {f: f for f in os.listdir(os.path.join(HERE, "static", "pdfs")) if f.lower().endswith(".pdf")}
items = []
for path in sorted(glob.glob(os.path.join(HERE, "data", "content", "*.json"))):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    meta = doc["meta"]
    prefix = f'{meta["level"]}_{int(meta["number"]):02d}_'
    match = [f for f in pdfs if f.startswith(prefix)]
    if not match:
        print("No PDF for", path); continue
    n_ex = sum(len(b.get("items", [])) for b in doc["blocks"] if b.get("type") == "exercises")
    items.append({
        "id": match[0][:-4], "file": match[0], "level": meta["level"], "number": int(meta["number"]),
        "section": meta.get("section", ""), "title": meta["title"], "subtitle": meta.get("subtitle", ""),
        "content": os.path.basename(path), "exercise_count": n_ex})
order = ["A1", "A2", "B1", "B2", "C1", "C2"]
items.sort(key=lambda x: (order.index(x["level"]), x["number"]))
with open(os.path.join(HERE, "data", "catalog.json"), "w", encoding="utf-8") as fh:
    json.dump(items, fh, ensure_ascii=False, indent=1)
print(len(items), "PDFs catalogued")
