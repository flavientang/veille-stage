#!/usr/bin/env python3
"""Scan public ATS job boards (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee)
and list sales-development style postings in target locations.
Usage: scan.py companies.json LOCATION_REGEX [out.json]"""
import json, re, sys, html, urllib.request, concurrent.futures as cf

UA = {"User-Agent": "Mozilla/5.0 (veille-stage)"}
TITLE_OK = re.compile(r"sales development|business development|\bsdr\b|\bbdr\b|development rep|account executive|"
                      r"inside sales|sales (intern|associate|trainee|representative|coordinator)|business developer|"
                      r"new business|intern.*sales|sales.*intern|stagiaire|\bstage\b|commercial|growth (rep|associate)|account development|"
                      r"(gtm|go-to-market|revenue|business) (intern|trainee)|\bvertrieb", re.I)
TITLE_BAD = re.compile(r"\b(senior|sr\.?|lead|manager|director|head|principal|vp|enterprise account executive|"
                       r"strategic|engineer|partner manager|marketing|recruit|solutions)\b", re.I)

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def clean(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()

def greenhouse(slug):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    for j in d.get("jobs", []):
        yield dict(id=f"gh:{slug}:{j['id']}", title=j["title"], location=j["location"]["name"],
                   url=j["absolute_url"], updated=j.get("updated_at"), published=j.get("first_published"),
                   text=clean(j.get("content")), meta={m["name"]: m["value"] for m in j.get("metadata") or [] if m.get("value")})

def lever(slug):
    for j in get(f"https://api.lever.co/v0/postings/{slug}?mode=json"):
        c = j.get("categories", {})
        txt = clean(j.get("descriptionPlain") or j.get("description")) + " " + " ".join(
            clean(l.get("content")) for l in j.get("lists", [])) + " " + clean(j.get("additionalPlain"))
        yield dict(id=f"lv:{slug}:{j['id']}", title=j["text"], location=c.get("location") or ", ".join(c.get("allLocations") or []),
                   url=j["hostedUrl"], updated=None, published=j.get("createdAt"), text=txt,
                   meta={"commitment": c.get("commitment"), "team": c.get("team")})

def ashby(slug):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false")
    for j in d.get("jobs", []):
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        yield dict(id=f"ab:{slug}:{j['id']}", title=j["title"], location="; ".join(locs), url=j["jobUrl"],
                   updated=None, published=j.get("publishedAt"), text=clean(j.get("descriptionPlain") or j.get("descriptionHtml")),
                   meta={"employmentType": j.get("employmentType")})

def smartrecruiters(slug):
    off, total = 0, 1
    while off < total and off < 2000:
        d = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={off}")
        total, off = d.get("totalFound", 0), off + 100
        for j in d.get("content", []):
            if not TITLE_OK.search(j["name"]) or TITLE_BAD.search(j["name"]):
                continue
            l = j.get("location", {})
            det = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{j['id']}")
            sec = (det.get("jobAd") or {}).get("sections") or {}
            txt = " ".join(clean((sec.get(k) or {}).get("text")) for k in ("jobDescription", "qualifications", "additionalInformation"))
            yield dict(id=f"sr:{slug}:{j['id']}", title=j["name"], location=f"{l.get('city')}, {l.get('country')}",
                       url=det.get("postingUrl") or f"https://jobs.smartrecruiters.com/{slug}/{j['id']}", updated=None,
                       published=j.get("releasedDate"), text=txt, meta={"type": (j.get("typeOfEmployment") or {}).get("label")})

def workable(slug):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    for j in d.get("jobs", []):
        yield dict(id=f"wk:{slug}:{j['shortcode']}", title=j["title"], location=f"{j.get('city')}, {j.get('country')}",
                   url=j["url"], updated=None, published=j.get("published_on"), text="",
                   meta={"employment_type": j.get("employment_type")})

def recruitee(slug):
    d = get(f"https://{slug}.recruitee.com/api/offers/")
    for j in d.get("offers", []):
        yield dict(id=f"rc:{slug}:{j['id']}", title=j["title"], location=j.get("location") or "", url=j["careers_url"],
                   updated=j.get("updated_at"), published=j.get("published_at"),
                   text=clean(j.get("description")) + " " + clean(j.get("requirements")),
                   meta={"employment_type": j.get("employment_type_code")})

def workday(slug, loc_re=None):
    # slug = "tenant|wdN|site" ; the list API only gives relative dates, so read each detail page
    ten, wd, site = slug.split("|")
    base = f"https://{ten}.{wd}.myworkdayjobs.com/wday/cxs/{ten}/{site}"
    seen = {}
    for q in ["sales development", "business development", "sales intern", "account executive", "inside sales"]:
        for off in range(0, 200, 20):
            body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": off, "searchText": q}).encode()
            req = urllib.request.Request(base + "/jobs", data=body, headers={**UA, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read())
            for p in d.get("jobPostings", []):
                if TITLE_OK.search(p.get("title", "")) and not TITLE_BAD.search(p.get("title", "")):
                    seen[p["externalPath"]] = p
            if off + 20 >= d.get("total", 0):
                break
    for path, p in seen.items():
        if loc_re and not loc_re.search(p.get("locationsText", "") + " " + path):
            # "2 Locations" hides the cities: keep it and let the detail decide
            if "Locations" not in p.get("locationsText", ""):
                continue
        info = get(base + path).get("jobPostingInfo", {})
        locs = "; ".join([info.get("location", "")] + (info.get("additionalLocations") or []))
        yield dict(id=f"wd:{ten}:{info.get('jobReqId') or path}", title=info.get("title", p["title"]), location=locs,
                   url=info.get("externalUrl") or f"https://{ten}.{wd}.myworkdayjobs.com/{site}{path}",
                   updated=None, published=info.get("startDate"), text=clean(info.get("jobDescription")),
                   meta={"timeType": info.get("timeType"), "reqId": info.get("jobReqId")})

def gethtml(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return r.read().decode("utf-8", "replace")

def builtin(slug):
    # slug = "https://builtindublin.ie|sales/entry-level,sales/internship" (server-rendered listing pages)
    site, paths = slug.split("|")
    cards = {}
    for p in paths.split(","):
        for page in range(1, 6):
            h = gethtml(f"{site}/jobs/{p}?page={page}")
            found = re.findall(r'data-id="company-title"[^>]*data-builtin-track-job-id="(\d+)"[^>]*><span>([^<]+)</span>', h)
            titles = dict(re.findall(r'data-id="job-card-title"[^>]*data-builtin-track-job-id="(\d+)"[^>]*>([^<]+)', h))
            links = dict((i, l) for l, i in re.findall(r'href="(/job/[^"]+/(\d+))"', h))
            for jid, comp in found:
                cards[jid] = (html.unescape(comp.strip()), html.unescape(titles.get(jid, "").strip()), site + links.get(jid, ""))
            if not found:
                break
    for jid, (comp, title, url) in cards.items():
        if not (TITLE_OK.search(title) and not TITLE_BAD.search(title)):
            continue
        h = gethtml(url)
        removed = re.search(r"this job was removed[^<]*", h)
        body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
        m = re.search(r'job-post-content|job-description', body)
        text = clean(body[m.start():m.start() + 40000] if m else body).split("Similar Jobs")[0]
        yield dict(id=f"bi:{jid}", title=title, location=site.split("//")[1], url=url, updated=None, published=None,
                   text=text[:8000], meta={"via": "Built In", "company": comp, "removed": removed.group(0) if removed else None},
                   company_override=comp)

ATS = dict(builtin=builtin, workday=workday, greenhouse=greenhouse, lever=lever, ashby=ashby, smartrecruiters=smartrecruiters, workable=workable, recruitee=recruitee)

def scan(company, loc_re):
    out, err = [], None
    try:
        fn = ATS[company["ats"]]
        for j in (fn(company["slug"], loc_re) if fn is workday else fn(company["slug"])):
            if loc_re.search(j["location"] or "") and TITLE_OK.search(j["title"]) and not TITLE_BAD.search(j["title"]):
                j["company"] = j.pop("company_override", None) or company["name"]; out.append(j)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    return company, out, err

if __name__ == "__main__":
    companies = json.load(open(sys.argv[1])); loc_re = re.compile(sys.argv[2], re.I)
    res, errs = [], []
    with cf.ThreadPoolExecutor(12) as ex:
        for c, out, err in ex.map(lambda c: scan(c, loc_re), companies):
            if err: errs.append(f"{c['name']} ({c['ats']}:{c['slug']}): {err}")
            res += out
    json.dump(res, open(sys.argv[3] if len(sys.argv) > 3 else "candidates.json", "w"), ensure_ascii=False, indent=1)
    for j in res: print(f"{j['company']:<18} | {j['title'][:70]:<70} | {j['location'][:40]} | {j['url']}")
    print(f"\n{len(res)} candidats, {len(errs)} erreurs", file=sys.stderr)
    for e in errs: print("ERR", e, file=sys.stderr)
