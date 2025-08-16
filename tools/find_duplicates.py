# tools/find_duplicates.py
import hashlib, os, json
ROOT = os.path.dirname(os.path.dirname(__file__))
seen, dups = {}, []
for r,_,fs in os.walk(ROOT):
    if any(skip in r for skip in ('.git','node_modules','dist','.local','static/voice_responses','logs')): 
        continue
    for f in fs:
        p = os.path.join(r,f)
        try:
            h = hashlib.sha256(open(p,'rb').read()).hexdigest()
        except: 
            continue
        if h in seen: dups.append([seen[h], p])
        else: seen[h] = p
print(json.dumps({"duplicates": dups}, ensure_ascii=False, indent=2))