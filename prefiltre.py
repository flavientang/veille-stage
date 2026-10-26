#!/usr/bin/env python3
"""First-pass triage of new offers. Usage: prefiltre.py nouveaux.json > tri.json
Adds to each offer: 'auto' (an obvious rejection reason, or None) and 'signals' (contract/duration/start/
experience/language snippets quoted from the page). Offers with auto=None must be read in full by the agent;
auto reasons are only shortcuts for clear-cut cases and stay overridable."""
import json, re, sys

OTHER_LANG = (r"german|deutsch|dach|dutch|flemish|nordic|nordics|swedish|danish|norwegian|finnish|italian|"
              r"spanish|iberia|portuguese|polish|arabic|turkish|czech|hebrew|japanese|greek|hungarian|romanian")
FRANCE = re.compile(r"\bfrance\b|paris|lyon|marseille|lille|bordeaux|toulouse|nantes|\bFRA\b", re.I)
ABROAD = re.compile(open(__file__.rsplit("/", 1)[0] + "/europe.regex").read().strip(), re.I)

def snippets(pat, text, n=4, w=70):
    out = []
    for m in re.finditer(pat, text, re.I):
        s = text[max(0, m.start() - w):m.end() + w].strip()
        if not any(s[:40] in o for o in out):
            out.append(s)
        if len(out) >= n:
            break
    return out

def auto_reason(j):
    t, x, loc = j["title"], j.get("text") or "", j.get("location") or ""
    if re.search(r"\b(USA|United States)\b|, (MA|CT|NY|CA|TX|WA|IL|MD|GA|CO|FL)\b", loc) and not re.search(
            r"ireland|belgi|luxembourg|switzerland|italy|spain|portugal|netherlands|germany|united kingdom|\bUK\b|england|europe|emea", loc, re.I):
        return "hors Europe"
    if FRANCE.search(loc) and not ABROAD.search(FRANCE.sub(" ", loc)):
        return "en France (pas à l'étranger)"
    if re.search(OTHER_LANG, t, re.I) and not re.search(r"french|fran[cç]ais", t, re.I):
        return "langue exigée (intitulé) : " + re.search(OTHER_LANG, t, re.I).group(0)
    if re.search(r"native[- ]level english|english \(native|native english|english native", x, re.I):
        return "anglais natif exigé"
    m = re.search(r"(?:fluen\w+|native|business[- ]level|proficien\w+)\s+(?:in\s+|level\s+)?(?:\w+\s+(?:and|&)\s+)?(" + OTHER_LANG + r")", x, re.I)
    if m and not re.search(r"french|fran[cç]ais", x[max(0, m.start() - 80):m.end() + 80], re.I) \
            and not re.search(r"plus|bonus|advantage|nice to have|preferred|desirable", x[m.start():m.end() + 60], re.I):
        return "langue exigée (texte) : " + m.group(1)
    if re.search(r"\b1[23][- ]week|summer (internship|program|20\d\d)|internship.{0,40}summer 20\d\d", t + " " + x, re.I):
        return "programme d'été de 12-13 semaines"
    if re.search(r"account executive|\bAE\b|closing", t, re.I):
        for m in re.finditer(r"(\d+)\s*\+?\s*(?:-|–|to)?\s*\d*\+?\s*years?", x, re.I):
            ctx = x[m.start():m.end() + 80]
            if int(m.group(1)) >= 2 and re.search(r"clos|quota|sales|account exec|full[- ]cycle|b2b|saas", ctx, re.I):
                return f"expérience exigée : {m.group(0)} ({ctx[len(m.group(0)):60].strip()}…)"
    if re.search(r"\bunpaid\b|non r[ée]mun[ée]r", x, re.I):
        return "non rémunéré"
    return None

def signals(j):
    x = j.get("text") or ""
    return {
        "contrat": snippets(r"intern(ship)?\b|stage\b|stagiaire|fixed[- ]term|\bFTC\b|temporary|contract(or)?\b|permanent|CDD|CDI|maternity cover", x),
        "duree_debut": snippets(r"\b\d+[- ]?(months?|mois)\b|start(ing)? (date|in|from)|january|february|march 2027|janvier|f[ée]vrier|mars 2027", x),
        "experience": snippets(r"\d+\s*\+?\s*(?:-|–|to)?\s*\d*\+?\s*(years?|months?) of|no (prior )?experience|graduat\w+", x, 3),
        "langues": snippets(r"french|fran[cç]ais|english|fluen\w+|native", x, 4, 50),
        "outbound": sorted(set(m.group(0).lower() for m in re.finditer(r"outbound|inbound|cold[- ]call\w*", x, re.I))),
        "meta": j.get("meta"),
    }

def priority(j):
    s = " ".join(j["signals"]["contrat"] + j["signals"]["duree_debut"]).lower()
    return (0 if re.search(r"intern|stage|fixed|ftc|cdd|temporary|month|mois", s) else 1,
            0 if re.search(r"french|fran[cç]ais", j["title"] + " " + " ".join(j["signals"]["langues"]), re.I) else 1)

offers = json.load(open(sys.argv[1]))
for j in offers:
    j["auto"] = auto_reason(j)
    j["signals"] = signals(j)
offers.sort(key=lambda j: (j["auto"] is not None,) + priority(j))
json.dump(offers, sys.stdout, ensure_ascii=False, indent=1)
print(f"{sum(j['auto'] is None for j in offers)} à lire, {sum(j['auto'] is not None for j in offers)} écartées d'office", file=sys.stderr)
