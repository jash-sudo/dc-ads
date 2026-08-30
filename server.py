import os,re,time,uuid,sqlite3,requests
from pathlib import Path
from flask import Flask,jsonify,request,send_from_directory
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()
ROOT=Path(__file__).resolve().parent
DB=ROOT/'ads.db'
API='https://api.democracycraft.net/economy'
TOKEN=os.getenv('DC_API_TOKEN','')
PAY_ACCOUNT=os.getenv('AD_PAYMENT_ACCOUNT_ID','113953')
PAY_PLAYER='bxpn'
PLANS={'basic':{'price':'100.00','minutes':5},'featured':{'price':'250.00','minutes':10},'premium':{'price':'600.00','minutes':30}}
BLOCKED={'fuck','shit','bitch','asshole','dick','piss','cunt','nigger','faggot'}
app=Flask(__name__,static_folder=None)
CORS(app,resources={r'/api/*':{'origins':'*'}})

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    with conn() as c:
        c.execute('CREATE TABLE IF NOT EXISTS ads(id TEXT PRIMARY KEY,business TEXT,player TEXT,category TEXT,location TEXT,text TEXT,plan TEXT,price TEXT,status TEXT,created_at INTEGER,expires_at INTEGER,payment_reference TEXT UNIQUE)')

def bad(s): return any(x in set(re.findall(r'[a-z0-9]+',s.lower())) for x in BLOCKED)

def api_get(path):
    r=requests.get(API+path,headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/json'},timeout=15); r.raise_for_status(); return r.json()

def txs(d):
    if isinstance(d,list): return d
    if isinstance(d,dict):
        for k in ('transactions','items','content','data'):
            if isinstance(d.get(k),list): return d[k]
    return []

def tx_time(tx):
    for k in ('createdAt','created_at','timestamp','date'):
        if k in tx:
            try: return int(float(tx[k])) if str(tx[k]).replace('.','',1).isdigit() else 0
            except: pass
    return 0

def amount(tx):
    for k in ('amount','value','money','total'):
        if k in tx:
            try: return float(re.sub(r'[^0-9.-]','',str(tx[k])))
            except: pass
    return None

def incoming_to_owner(tx,price,created):
    if not isinstance(tx,dict): return False
    a=amount(tx)
    if a is None or abs(a-float(price))>0.001: return False
    raw=str(tx).lower()
    # Prefer explicit incoming/credit/deposit indicators when present.
    if any(k in tx for k in ('type','direction','credit','debit')):
        vals=' '.join(str(tx.get(k,'')) for k in ('type','direction','credit','debit')).lower()
        if any(x in vals for x in ('outgoing','debit','withdraw','sent')) and 'credit' not in vals: return False
    if any(x in raw for x in ('outgoing','debit','withdrawal')) and not any(x in raw for x in ('incoming','credit','deposit','received')): return False
    t=tx_time(tx)
    if t and t < created-60: return False
    return True

init()

@app.get('/')
def home(): return send_from_directory(ROOT,'index.html')
@app.get('/<path:name>')
def static(name):
    if name in ('index.html','style.css','app.js'): return send_from_directory(ROOT,name)
    return jsonify(error='not_found'),404
@app.get('/health')
def health(): return jsonify(status='ok',api_configured=bool(TOKEN),payment_account=PAY_ACCOUNT,payment_player=PAY_PLAYER)
@app.get('/api/ads')
def ads():
    with conn() as c:
        c.execute("UPDATE ads SET status='expired' WHERE status='active' AND expires_at<=?",(int(time.time()),))
        rows=c.execute("SELECT business,player,category,location,text,expires_at FROM ads WHERE status='active' AND expires_at>?",(int(time.time()),)).fetchall()
    return jsonify([dict(x) for x in rows])
@app.post('/api/ads')
def create():
    d=request.get_json(silent=True) or {}; b=str(d.get('business','')).strip(); p=str(d.get('player','')).strip(); cat=str(d.get('category','')).strip(); loc=str(d.get('location','')).strip(); txt=str(d.get('text','')).strip(); plan=d.get('plan','basic')
    if not b or not p or not txt: return jsonify(error='Missing required fields'),400
    if plan not in PLANS: return jsonify(error='Invalid plan'),400
    if bad(' '.join((b,txt,loc))): return jsonify(error='Your ad contains blocked language'),400
    aid=str(uuid.uuid4()); ref='DCADS-'+aid[:8].upper(); pl=PLANS[plan]; now=int(time.time())
    with conn() as c: c.execute('INSERT INTO ads VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(aid,b,p,cat,loc,txt,plan,pl['price'],'pending',now,None,ref))
    return jsonify(adId=aid,status='pending_payment',price=pl['price'],durationMinutes=pl['minutes'],paymentPlayer=PAY_PLAYER,paymentAccountId=PAY_ACCOUNT,paymentReference=ref),201
@app.get('/api/ads/<aid>/status')
def status(aid):
    with conn() as c: row=c.execute('SELECT * FROM ads WHERE id=?',(aid,)).fetchone()
    if not row:return jsonify(error='Ad not found'),404
    a=dict(row)
    if a['status']!='pending': return jsonify(status=a['status'],expiresAt=a['expires_at'])
    if not TOKEN:return jsonify(status='backend_not_configured',detail='DC_API_TOKEN is not configured'),503
    try: data=api_get(f'/api/v1/accounts/{PAY_ACCOUNT}/transactions')
    except requests.RequestException as e:return jsonify(status='payment_check_error',error=str(e)),502
    if any(incoming_to_owner(x,a['price'],a['created_at']) for x in txs(data)):
        exp=int(time.time())+PLANS[a['plan']]['minutes']*60
        with conn() as c:c.execute("UPDATE ads SET status='active',expires_at=? WHERE id=?",(exp,aid))
        return jsonify(status='active',expiresAt=exp)
    return jsonify(status='pending_payment',paymentTo=PAY_PLAYER,amount=a['price'])
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','8081')),debug=False)
