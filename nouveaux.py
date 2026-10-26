#!/usr/bin/env python3
"""Keep only offers never shown before. Usage: nouveaux.py deja_vus.txt candidats.json [...] > nouveaux.json
An offer is 'seen' if the hash of its id OR of its fingerprint (company + title, normalised) is in deja_vus.txt,
so the same job found on Built In and on the company ATS only shows once.
Each new offer gets 'cles': the two hashes to append to deja_vus.txt once it has been shown."""
import hashlib, json, re, sys, unicodedata

def fp(company, title):
    s = unicodedata.normalize("NFKD", f"{company}|{title}").encode("ascii", "ignore").decode().lower()
    return "fp:" + re.sub(r"[^a-z0-9|]+", "", s)

def h(key):
    # deja_vus.txt stores 10-char sha1 prefixes of ids and fingerprints, to keep the Notion page small
    return hashlib.sha1(key.encode()).hexdigest()[:10]

seen = set(open(sys.argv[1]).read().split())
out, batch = [], set()
for f in sys.argv[2:]:
    for j in json.load(open(f)):
        k, p = j["id"], fp(j["company"], j["title"])
        if h(k) in seen or h(p) in seen or k in batch or p in batch:
            continue
        batch |= {k, p}; j["fp"] = p; j["cles"] = [h(k), h(p)]; out.append(j)
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} nouvelles offres", file=sys.stderr)
