# -*- coding: utf-8 -*-
"""Experimental daily signal scanner.

This is a paper-signal layer: it does not place orders. It uses the research
pattern (early post-split weakness, support/base, then daily positivity) and
records every signal so the next month can be evaluated honestly.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

CANDIDATES='reverse_split_candidates.json'
OUTPUT='daily_signals.json'
HISTORY='paper_signal_history.json'


def f(v):
    try:
        v=float(v); return None if np.isnan(v) else v
    except Exception: return None

def rsi(s,n=14):
    d=s.diff(); up=d.clip(lower=0).rolling(n).mean(); dn=(-d.clip(upper=0)).rolling(n).mean()
    return 100-(100/(1+(up/dn.replace(0,np.nan))))

def analyze(row):
    ticker=row['ticker']; split=row['split_date']
    try:
        x=yf.Ticker(ticker).history(start=pd.Timestamp(split)-pd.Timedelta(days=5), end=pd.Timestamp.now(tz='UTC').tz_localize(None)+pd.Timedelta(days=1), interval='1d', auto_adjust=False, actions=False)
        if x is None or x.empty: return {'ticker':ticker,'status':'unavailable','reason':'no_daily_data'}
        if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
        x.index=pd.to_datetime(x.index).tz_localize(None); x=x[x.index>=pd.Timestamp(split)].copy()
        if len(x)<12: return {'ticker':ticker,'status':'insufficient','reason':'أقل من 12 جلسة بعد التقسيم'}
        x['rsi']=rsi(x.Close); x['vol20']=x.Volume.rolling(20,min_periods=5).mean(); x['vr']=x.Volume/x.vol20
        x['ema12']=x.Close.ewm(span=12,adjust=False).mean(); x['ema26']=x.Close.ewm(span=26,adjust=False).mean(); x['macd']=x.ema12-x.ema26; x['macd_signal']=x.macd.ewm(span=9,adjust=False).mean(); x['hist']=x.macd-x.macd_signal
        last=x.iloc[-1]; prev=x.iloc[-2]
        recent=x.tail(min(40,len(x))); support=float(recent.Low.quantile(.20)); tol=max(support*.05,.0001)
        tests=0; last_test=None
        for idx,v in recent.Low.items():
            if abs(float(v)-support)<=tol and (last_test is None or (idx-last_test).days>=2): tests+=1; last_test=idx
        peak=float(x.High.max()); drawdown=(float(last.Low)/peak-1)*100 if peak else 0
        base_range=(float(recent.High.max())/float(recent.Low.min())-1)*100 if float(recent.Low.min()) else 0
        age=len(x)-1
        positive=bool(last['Close']>last['Open'] and last['Close']>prev['Close'])
        momentum=bool((f(last['vr']) or 0)>=1.05 or (f(last['hist']) is not None and f(prev['hist']) is not None and last['hist']>prev['hist']))
        near_support=bool(float(last.Close)<=support*1.12)
        base=bool(age<=120 and drawdown<=-30 and tests>=2 and base_range<=80)
        entry=bool(base and positive and momentum and not near_support)
        state='ENTRY_PAPER' if entry else ('BASE_WATCH' if base else 'OBSERVE')
        score=sum([age<=60,drawdown<=-40,tests>=3,near_support,positive,momentum])
        return {'ticker':ticker,'company':row.get('company'),'split_date':split,'status':'ok','state':state,'paper_signal':entry,'signal_date':last.name.date().isoformat() if entry else None,'signal_price':f(last['Close']) if entry else None,'price':f(last['Close']),'days_since_split':age,'drawdown_percent':round(drawdown,2),'support_price':f(support),'support_tests':tests,'base_range_percent':round(base_range,2),'rsi':f(last['rsi']),'rsi_previous':f(prev['rsi']),'rsi_improving':bool(last['rsi']>prev['rsi']) if pd.notna(last['rsi']) and pd.notna(prev['rsi']) else False,'volume_ratio':f(last['vr']),'macd_histogram':f(last['hist']),'macd_histogram_improving':bool(last['hist']>prev['hist']) if pd.notna(last['hist']) and pd.notna(prev['hist']) else False,'daily_positive':positive,'momentum_confirmed':momentum,'near_support':near_support,'score':score,'max_score':6,'research_note':'إشارة تجريبية يومية؛ لا تنفذ صفقة تلقائية'}
    except Exception as e: return {'ticker':ticker,'status':'error','reason':str(e)[:180]}

def main():
    rows=json.loads(Path(CANDIDATES).read_text(encoding='utf-8')); out=[]
    for i,row in enumerate(rows,1): print(f'[{i}/{len(rows)}] {row["ticker"]}',flush=True); out.append(analyze(row))
    ok=[x for x in out if x.get('status')=='ok']
    # A ticker can appear more than once in the source universe. Keep the
    # strongest/latest observation only so the dashboard does not duplicate it.
    unique={}
    for x in ok:
        key=x['ticker']; old=unique.get(key)
        if old is None or (x.get('paper_signal'), x.get('score',0), x.get('days_since_split',0)) > (old.get('paper_signal'), old.get('score',0), old.get('days_since_split',0)):
            unique[key]=x
    ok=list(unique.values()); entries=[x for x in ok if x.get('paper_signal')]; watches=[x for x in ok if x.get('state')=='BASE_WATCH']
    try: history=json.loads(Path(HISTORY).read_text(encoding='utf-8'))
    except Exception: history=[]
    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    by_id={h.get('id'):h for h in history if isinstance(h,dict) and h.get('id')}
    for item in entries:
        key=f"{item['ticker']}|{item['signal_date']}"
        old=by_id.get(key, {'id':key,'ticker':item['ticker'],'signal_date':item['signal_date'],'signal_price':item['signal_price'],'first_seen':now,'status':'monitoring','success':False})
        old.update({'last_seen':now,'latest_price':item['price'],'latest_state':item['state']})
        by_id[key]=old
    history=list(by_id.values())
    Path(HISTORY).write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    payload={'generated_at':now,'methodology':{'purpose':'مراقبة تجريبية فقط بلا تنفيذ صفقات','base':'Reverse Split خلال 120 جلسة، هبوط >=30%، اختبارات دعم >=2، نطاق قاعدة <=80%','entry':'إيجابية يومية (Close>Open وClose>Previous Close) مع تأكيد حجم أو تحسن MACD، والخروج التجريبي عند +70% من سعر الإشارة','status_definitions':{'ENTRY_PAPER':'إشارة يومية تجريبية','BASE_WATCH':'قاعدة/دعم للمراقبة','OBSERVE':'لا يطابق مرحلة القاعدة حالياً'}},'summary':{'candidates':len(rows),'ok':len(ok),'paper_entries':len(entries),'base_watches':len(watches),'unavailable':len(rows)-len(ok),'history_records':len(history)},'signals':entries,'watchlist':watches,'history':history,'all':out}
    Path(OUTPUT).write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(payload['summary'],ensure_ascii=False))
if __name__=='__main__': main()
