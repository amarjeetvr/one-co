import csv, re, os, json

urls = [r['url'].strip() for r in csv.DictReader(open('urls/college_urls.csv', encoding='utf-8'))]
print('CSV total URLs:', len(urls))

dirty = [u for u in urls if re.search(r'/(ranking|courses-fees|placement|admission|reviews|faculty|scholarship|hostel|cutoff)/?$', u, re.I)]
print('Dirty subpage URLs in CSV:', len(dirty))
if dirty:
    for d in dirty[:5]: print(' ', d)

dids = {re.match(r'^(\d+)_', f).group(1) for f in os.listdir('html/info') if f.endswith('.html') and re.match(r'^(\d+)_', f)}
print('Downloaded info HTMLs:', len(dids))

cids = {re.search(r'/(\d+)-', u).group(1): u for u in urls if re.search(r'/(\d+)-', u)}
pend = {c: v for c, v in cids.items() if c not in dids}
print('Pending download:', len(pend))
if pend:
    for v in list(pend.values())[:3]: print(' ', v)

for name in ['colleges', 'courses', 'rankings', 'placements']:
    try:
        n = len(json.load(open(f'json_data/{name}.json', encoding='utf-8')))
        print(f'JSON {name}: {n}')
    except Exception as e:
        print(f'JSON {name}: ERROR {e}')

try:
    print('Excel sheets:', len(os.listdir('exports/colleges')))
except:
    print('Excel sheets: N/A')

state_file = 'urls/.discovery_state'
print('Discovery state:', open(state_file).read().strip() if os.path.exists(state_file) else 'NOT FOUND')

# --- Subpage completeness audit ------------------------------------------
# A college is treated as "downloaded" as soon as its info page exists, so a
# partial failure (info saved but a sibling subpage 403'd/timed out) leaves a
# silent data hole that is never retried. Concurrency makes partial failures
# more likely, so audit how many of the 9 subpages each downloaded college has.
SUBPAGES = ['info', 'courses', 'admissions', 'placements', 'reviews',
            'faculty', 'scholarships', 'hostel', 'cutoff']
present = {}  # college_id -> set(subpages present)
for sub in SUBPAGES:
    d = os.path.join('html', sub)
    if os.path.isdir(d):
        for f in os.listdir(d):
            m = re.match(r'^(\d+)_', f)
            if f.endswith('.html') and m:
                present.setdefault(m.group(1), set()).add(sub)

if present:
    full = sum(1 for s in present.values() if len(s) == len(SUBPAGES))
    print(f'\nSubpage completeness: {len(present)} colleges downloaded | '
          f'{full} complete (all {len(SUBPAGES)}) | {len(present) - full} partial')
    incomplete = {cid: s for cid, s in present.items() if len(s) < len(SUBPAGES)}
    for cid, s in list(incomplete.items())[:10]:
        missing = [x for x in SUBPAGES if x not in s]
        print(f'  {cid}: has {len(s)}/{len(SUBPAGES)}, missing {missing}')
    if len(incomplete) > 10:
        print(f'  ... and {len(incomplete) - 10} more partial colleges')
    print('  NOTE: some subpages may be legitimately absent (site has no '
          '/cutoff etc.). Spot-check a few flagged colleges in the browser.')
