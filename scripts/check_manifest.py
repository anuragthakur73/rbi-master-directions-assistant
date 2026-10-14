import csv, pathlib

raw = pathlib.Path("data/raw")
on_disk = {p.name for p in raw.glob("*.pdf")}
with open("data/manifest.csv", newline="", encoding="utf-8") as f:
    listed = {row["filename"] for row in csv.DictReader(f)}

print("In folder but not in manifest:", sorted(on_disk - listed) or "none")
print("In manifest but not in folder:", sorted(listed - on_disk) or "none")


