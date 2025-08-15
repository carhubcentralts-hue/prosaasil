import hashlib, os, sys, collections, re

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
EXCLUDE_DIRS = {"legacy", ".git", "__pycache__", "node_modules", "client/dist"}
EXCLUDE_EXT = {".png",".jpg",".jpeg",".gif",".map",".lock",".log",".ico"}

def file_iter():
    for d,_,files in os.walk(ROOT):
        parts = set(d.replace("\\","/").split("/"))
        if parts & EXCLUDE_DIRS: continue
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in EXCLUDE_EXT: continue
            p = os.path.join(d,f)
            try:
                if os.path.getsize(p) == 0: continue
                yield p
            except: pass

def md5(p):
    h = hashlib.md5()
    with open(p,"rb") as fh:
        for chunk in iter(lambda: fh.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

by_hash = collections.defaultdict(list)
for p in file_iter():
    try:
        by_hash[md5(p)].append(p)
    except Exception as e:
        print("ERR", p, e)

print("\n# Duplicate content groups:")
for h, plist in by_hash.items():
    if len(plist) > 1:
        print(f"\nMD5={h}")
        for p in plist: print("  ", p)

# שמות חשודים ("copy","clean","old","backup","bak","new","(1)")
PAT = re.compile(r"(copy|clean|old|backup|bak|new|\(\d+\)|_old|_bak)", re.I)
print("\n# Suspicious filenames:")
for p in file_iter():
    if PAT.search(os.path.basename(p)):
        print("  ", p)