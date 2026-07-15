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
