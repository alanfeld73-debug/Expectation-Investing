"""Base rates de crecimiento de ventas a 10 años (Mauboussin, The Base Rate Book).
Fuente: SEC XBRL frames (todas las compañías que reportan a la SEC), CY2015 -> CY2025.
Sesgo de supervivencia: solo entran compañías que siguen reportando en 2025."""
import json,glob,os,time,urllib.request,numpy as np
DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),'br')
def _download():
    os.makedirs(DIR,exist_ok=True)
    for y in (2012,2015,2022,2025):
        for c in ('Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet'):
            p=os.path.join(DIR,f'{c}_{y}.json')
            if os.path.exists(p): continue
            req=urllib.request.Request(f'https://data.sec.gov/api/xbrl/frames/us-gaap/{c}/USD/CY{y}.json',headers={'User-Agent':'osojuanferpity@xmail.com'})
            try: open(p,'wb').write(urllib.request.urlopen(req).read())
            except Exception: pass
            time.sleep(0.2)
_download()
def load(y):
    r={}
    for f in glob.glob(os.path.join(DIR,f'*_{y}.json')):
        try: d=json.load(open(f))
        except: continue
        for x in d['data']:
            r[x['cik']]=max(r.get(x['cik'],0),x['val'])
    return r
R={y:load(y) for y in (2012,2015,2022,2025)}
rows=[]
for cik,s15 in R[2015].items():
    s25=R[2025].get(cik); s12=R[2012].get(cik)
    if s25 and s15>1e8 and s25>0:
        rows.append((s15,(s25/s15)**0.1-1,(s15/s12)**(1/3)-1 if s12 and s12>0 else None))
A=np.array([(a,b) for a,b,_ in rows])
BUCK=[(1e8,5e8),(5e8,2e9),(2e9,1e10),(1e10,5e10),(5e10,1e13)]
def dist(lo,hi,prior=None):
    sel=[g for s,g,p in rows if lo<=s<hi and (prior is None or (p is not None and prior[0]<=p<prior[1]))]
    return np.array(sel)
def prob(sales,g_req,prior_g=None):
    for lo,hi in BUCK:
        if lo<=sales<hi: break
    pr=None
    if prior_g is not None:
        for b in [(-1,0),(0,0.05),(0.05,0.10),(0.10,0.20),(0.20,10)]:
            if b[0]<=prior_g<b[1]: pr=b
    d=dist(lo,hi,pr)
    if len(d)<30: d=dist(lo,hi)
    return float((d>=g_req).mean()), len(d), float(np.median(d))
if __name__=='__main__':
    print('N companies',len(rows))
    for lo,hi in BUCK:
        d=dist(lo,hi); print(f'{lo/1e9:>6.1f}-{hi/1e9:<8.0f}bn n={len(d):4d} p25={np.percentile(d,25):.1%} med={np.median(d):.1%} p75={np.percentile(d,75):.1%} p90={np.percentile(d,90):.1%}')
    for b in [(-1,0),(0,0.05),(0.05,0.10),(0.10,0.20),(0.20,10)]:
        d=dist(1e10,1e13,b); print('large, prior',b,len(d), f'{np.median(d):.1%}' if len(d) else '')
