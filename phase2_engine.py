# -*- coding: utf-8 -*-
"""Phase 2 discovery-only engine.

Finds several candidate START_OF_EXPLOSION definitions independently of the
future +70% label, then measures only post-signal outcomes. It does not select
an entry, stop, target, score, or live strategy.
"""
from __future__ import annotations
import json, math, warnings
from pathlib import Path
from datetime import datetime, timezone
import numpy as np, pandas as pd
import yfinance as yf
from scipy import stats
warnings.filterwarnings('ignore')
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'research'; CAND=ROOT/'reverse_split_candidates.json'
HORIZONS=[1,3,5,10,20]; TARGETS=[20,50,70,100,200]
RSI_BINS=[(-math.inf,20),(20,22),(22,25),(25,27),(27,30),(30,35),(35,40),(40,50),(50,math.inf)]

def n(v):
 try:
  x=float(v); return None if not np.isfinite(x) else x
 except: return None

def rsi(s,p=14):
 d=s.diff(); u=d.clip(lower=0); dn=-d.clip(upper=0); a=u.ewm(alpha=1/p,min_periods=p,adjust=False).mean(); b=dn.ewm(alpha=1/p,min_periods=p,adjust=False).mean(); return 100-100/(1+a/b.replace(0,np.nan))

def frame(x):
 x=x.copy()
 if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
 if 'Close' not in x: return None
 x=x[['Open','High','Low','Close','Volume']].dropna(subset=['Close']); x.index=pd.to_datetime(x.index).tz_localize(None)
 if x.empty:return None
 x['rsi']=rsi(x.Close); x['rsi_slope']=x.rsi.diff(3)/3; x['atr']=pd.concat([(x.High-x.Low),(x.High-x.Close.shift()).abs(),(x.Low-x.Close.shift()).abs()],axis=1).max(axis=1).rolling(14).mean(); x['ma20']=x.Close.rolling(20).mean(); x['ma50']=x.Close.rolling(50).mean(); x['ema12']=x.Close.ewm(span=12,adjust=False).mean(); x['ema26']=x.Close.ewm(span=26,adjust=False).mean(); x['macd']=x.ema12-x.ema26; x['macd_signal']=x.macd.ewm(span=9,adjust=False).mean(); x['hist']=x.macd-x.macd_signal; x['vol5']=x.Volume.rolling(5).mean(); x['vol10']=x.Volume.rolling(10).mean(); x['vol20']=x.Volume.rolling(20).mean(); x['vr20']=x.Volume/x.vol20
 return x

def download(cands):
 tickers=sorted({r['ticker'] for r in cands}); start=(min(pd.Timestamp(r['split_date']) for r in cands)-pd.Timedelta(days=80)).date().isoformat(); end=(pd.Timestamp.now()+pd.Timedelta(days=1)).date().isoformat(); out={}
 for i in range(0,len(tickers),40):
  ch=tickers[i:i+40]; print(f'download {i+1}-{i+len(ch)}/{len(tickers)}',flush=True)
  try:z=yf.download(ch,start=start,end=end,auto_adjust=False,actions=False,group_by='ticker',threads=True,progress=False)
  except Exception as e: print('download error',e);continue
  for t in ch:
   try:
    q=z[t] if isinstance(z.columns,pd.MultiIndex) and t in z.columns.get_level_values(0) else z; q=frame(q)
    if q is not None:out[t]=q
   except Exception:pass
 return out

def first_idx(mask):
 z=mask[mask].index
 return z[0] if len(z) else None

def signal_defs(x,split):
 y=x.loc[x.index>=pd.Timestamp(split)].copy()
 if len(y)<25:return {}
 # Reference is the first post-split close. The local-low definitions use only data through candidate date.
 ref=float(y.iloc[0].Close); result={}
 for i in range(0,len(y)):
  q=y.iloc[:i+1]; close=float(q.iloc[-1].Close); low=float(q.Low.min()); prev20=float(q.Close.tail(20).max()); base=q.tail(10); base_low=float(base.Low.min()); base_high=float(base.High.max()); base_range=(base_high/base_low-1)*100 if base_low>0 else 999
  # A/B: first recovery from the lowest observed close, with no future information.
  for name,pct in [('A_10_from_low',10),('B_20_from_low',20)]:
   if name not in result and low>0 and close/low-1>=pct/100: result[name]=q.index[-1]
  # C: first 20% close return over any rolling 1-3 session window.
  if 'C_20_in_1_3' not in result and len(q)>=4 and float(q.Close.iloc[-1]/q.Close.iloc[-4]-1)>=.20: result['C_20_in_1_3']=q.index[-1]
  # D: rapid expansion requires simultaneous price and volume expansion, evaluated historically at date.
  vr=float(q.iloc[-1].vr20) if pd.notna(q.iloc[-1].vr20) else 0
  ret3=float(q.Close.iloc[-1]/q.Close.iloc[-4]-1) if len(q)>=4 else 0
  if 'D_rapid_expansion' not in result and ret3>=.20 and vr>=1.5: result['D_rapid_expansion']=q.index[-1]
  # E: at least 5 sessions of base followed by close above prior 10-day high with volume expansion.
  if 'E_base_breakout' not in result and len(q)>=15:
   prior=q.iloc[-11:-1]; ph=float(prior.High.max()); br=(float(q.iloc[-11:-1].High.max())/float(q.iloc[-11:-1].Low.min())-1)*100; cur=float(q.iloc[-1].Close)
   if br<=60 and cur>ph and vr>=1.2: result['E_base_breakout']=q.index[-1]
 return result

def features(x,signal,split):
 q=x.loc[x.index<=signal].copy(); row=q.iloc[-1]; vals={}
 for k,days in [('S',0),('S-1',1),('S-2',2),('S-3',3),('S-4',4),('S-5',5),('S-6',6),('S-7',7),('S-10',10),('S-15',15),('S-20',20)]:
  if len(q)>days:
   z=q.iloc[-1-days]; vals[k]={'date':z.name.date().isoformat(),'rsi':n(z['rsi']),'rsi_slope':n(z['rsi_slope']),'close':n(z['Close']),'volume':n(z['Volume']),'vr20':n(z['vr20']),'macd':n(z['macd']),'hist':n(z['hist']),'ma20':n(z['ma20']),'ma50':n(z['ma50'])}
 def rv(days): return (float(q.iloc[-1].Close/q.iloc[-1-days].Close)-1)*100 if len(q)>days and q.iloc[-1-days].Close else None
 rsi_vals=[v['rsi'] for v in vals.values() if v.get('rsi') is not None]; low=min(rsi_vals) if rsi_vals else None; high=max(rsi_vals) if rsi_vals else None
 return {'snapshots':vals,'rsi_mean':float(np.mean(rsi_vals)) if rsi_vals else None,'rsi_median':float(np.median(rsi_vals)) if rsi_vals else None,'rsi_min':low,'rsi_max':high,'rsi_range':high-low if low is not None and high is not None else None,'rsi_change':{f'S_minus_{d}':(vals['S']['rsi']-vals[f'S-{d}']['rsi']) if vals.get(f'S-{d}',{}).get('rsi') is not None and vals['S'].get('rsi') is not None else None for d in [1,3,5,7,10,15,20]},'rsi_slope_5':n((vals['S']['rsi']-vals['S-5']['rsi'])/5) if vals.get('S-5',{}).get('rsi') is not None and vals['S'].get('rsi') is not None else None,'returns':{str(d):rv(d) for d in [5,10,15,20]},'green_days_10':int((q.tail(10)['Close']>q.tail(10)['Open']).sum()),'red_days_10':int((q.tail(10)['Close']<q.tail(10)['Open']).sum()),'range_5':float((q.tail(5)['High'].max()/q.tail(5)['Low'].min()-1)*100) if q.tail(5)['Low'].min()>0 else None,'range_10':float((q.tail(10)['High'].max()/q.tail(10)['Low'].min()-1)*100) if q.tail(10)['Low'].min()>0 else None,'atr_percent':n(row['atr']/row['Close']*100) if pd.notna(row['atr']) and row['Close'] else None,'body_percent':n(abs(row['Close']-row['Open'])/row['Open']*100) if row['Open'] else None,'upper_wick_percent':n((row['High']-max(row['Open'],row['Close']))/row['Open']*100) if row['Open'] else None,'lower_wick_percent':n((min(row['Open'],row['Close'])-row['Low'])/row['Open']*100) if row['Open'] else None,'drawdown_peak':n((row['Close']/q['Close'].cummax().iloc[-1]-1)*100),'distance_recent_low':n((row['Close']/q.tail(20)['Low'].min()-1)*100),'distance_ma20':n((row['Close']/row['ma20']-1)*100) if pd.notna(row['ma20']) else None,'distance_ma50':n((row['Close']/row['ma50']-1)*100) if pd.notna(row['ma50']) else None,'volume_ratio_5':n(row['Volume']/q.tail(5)['Volume'].mean()) if q.tail(5)['Volume'].mean() else None,'volume_ratio_10':n(row['Volume']/q.tail(10)['Volume'].mean()) if q.tail(10)['Volume'].mean() else None,'volume_ratio_20':n(row['vr20']),'macd':n(row['macd']),'macd_signal':n(row['macd_signal']),'macd_hist':n(row['hist']),'macd_hist_change_5':n(row['hist']-q.iloc[-6]['hist']) if len(q)>6 else None,'ma20_above_ma50':bool(row['ma20']>row['ma50']) if pd.notna(row['ma20']) and pd.notna(row['ma50']) else None,'support_tests_20':int(sum(abs(q.tail(20)['Low']-q.tail(20)['Low'].quantile(.2))<=max(q.tail(20)['Low'].quantile(.2)*.05,.0001))),'prior_rally_30':n((q['Close'].iloc[-1]/q.tail(30)['Close'].min()-1)*100) if len(q)>=30 else None,'age_sessions':int((q.index>=pd.Timestamp(split)).sum())}

def outcomes(x,signal):
 fut=x.loc[x.index>signal].copy(); out={'targets':{},'max_high_20':None,'max_return_20':None}
 for h in HORIZONS:
  z=fut.head(h); out['targets'][str(h)]={str(t):bool(len(z)>0 and z.High.max()>=float(x.loc[signal].Close)*(1+t/100)) for t in TARGETS}
  out['targets'][str(h)]['max_return']=n((z.High.max()/float(x.loc[signal].Close)-1)*100) if len(z) else None
 if len(fut):out['max_high_20']=n(fut.head(20).High.max());out['max_return_20']=n((fut.head(20).High.max()/float(x.loc[signal].Close)-1)*100)
 return out

def classify(o):
 r=o.get('max_return_20') or 0; h=o['targets']; first70=None
 for k in ['1','3','5','10','20']:
  if h.get(k,{}).get('70'):first70=int(k);break
 if r>=70 and first70 is not None:
  if first70<=3:return 'True Explosion'
  if first70<=10:return 'Rapid Move'
  return 'Gradual Rise'
 if r>=70 and r>0:return 'Pump & Fade'
 if r>=20:return 'Temporary Spike'
 return 'No Significant Move'

def stats_table(rows):
 groups={}
 for r in rows:
  key=r['classification']; groups.setdefault(key,[]).append(r)
 out=[]
 for k,g in groups.items():
  rs=[r['features'].get('rsi_change',{}).get('S_minus_5') for r in g if r['features'].get('rsi_change',{}).get('S_minus_5') is not None]
  out.append({'class':k,'n':len(g),'tickers':len(set(r['ticker'] for r in g)),'rsi_change_S_to_S-5_mean':float(np.mean(rs)) if rs else None,'rsi_change_median':float(np.median(rs)) if rs else None,'rsi_recovery_rate':float(np.mean(np.array(rs)>0)) if rs else None,'mean_return_20':float(np.mean([r['outcomes'].get('max_return_20') or 0 for r in g]))})
 return out

def main():
 c=json.loads(CAND.read_text()); frames=download(c); rows=[]
 for j,r in enumerate(c,1):
  x=frames.get(r['ticker']);
  if x is None:continue
  defs=signal_defs(x,r['split_date'])
  for definition,sig in defs.items():
   f=features(x,sig,r['split_date']); o=outcomes(x,sig); rows.append({'ticker':r['ticker'],'company':r.get('company'),'split_date':r['split_date'],'split_ratio':r.get('reverse_split'),'definition':definition,'signal_date':sig.date().isoformat(),'age_sessions':f['age_sessions'],'features':f,'outcomes':o,'classification':classify(o)})
 print('signals',len(rows),'tickers',len(set(r['ticker'] for r in rows)))
 OUT.mkdir(exist_ok=True); (OUT/'explosion_start_cases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else x),encoding='utf-8')
 pd.DataFrame([{'ticker':r['ticker'],'definition':r['definition'],'signal_date':r['signal_date'],'age_sessions':r['age_sessions'],'classification':r['classification'],'max_return_20':r['outcomes']['max_return_20'],'rsi_S':r['features']['snapshots'].get('S',{}).get('rsi'),'rsi_S-5':r['features']['snapshots'].get('S-5',{}).get('rsi'),'rsi_change_S_to_S-5':r['features']['rsi_change'].get('S_minus_5'),'volume_ratio_20':r['features']['volume_ratio_20'],'drawdown_peak':r['features']['drawdown_peak']} for r in rows]).to_csv(OUT/'explosion_start_cases.csv',index=False)
 # Flatten RSI timing and distributions.
 timing=[]; dist=[]
 for r in rows:
  for k,v in r['features']['snapshots'].items(): timing.append({'ticker':r['ticker'],'definition':r['definition'],'signal_date':r['signal_date'],'classification':r['classification'],'relative_day':k,'rsi':v.get('rsi'),'rsi_slope':v.get('rsi_slope'),'volume_ratio_20':v.get('vr20'),'macd_hist':v.get('hist')})
  for lo,hi in RSI_BINS:
   v=r['features']['snapshots'].get('S',{}).get('rsi');
   if v is not None and lo<=v<hi:dist.append({'definition':r['definition'],'classification':r['classification'],'rsi_range':f'{lo}-{hi}','success_70_within_10d':bool(r['outcomes']['targets'].get('10',{}).get('70'))})
 pd.DataFrame(timing).to_csv(OUT/'rsi_timing_analysis.csv',index=False); pd.DataFrame(dist).to_csv(OUT/'rsi_distribution.csv',index=False)
 # Feature timing: first detectable improvement dates relative to signal for every row.
 ft=[]
 for r in rows:
  s=r['features']['snapshots']; events={}
  for label,cond in [('RSI recovery 20',lambda q:q.get('rsi') is not None and q['rsi']>=20),('RSI recovery 25',lambda q:q.get('rsi') is not None and q['rsi']>=25),('RSI recovery 30',lambda q:q.get('rsi') is not None and q['rsi']>=30),('RSI rising',lambda q:q.get('rsi_slope') is not None and q['rsi_slope']>0),('Volume expansion',lambda q:q.get('vr20') is not None and q['vr20']>=1.5),('MACD improvement',lambda q:q.get('hist') is not None and q['hist']>0),('MA20 reclaim',lambda q:q.get('close') is not None and q.get('ma20') is not None and q['close']>q['ma20'])]:
   found=None
   for k in ['S-20','S-15','S-10','S-7','S-5','S-3','S-2','S-1','S']:
    if k in s and cond(s[k]):found=k;break
   events[label]=found
  ft.append({'ticker':r['ticker'],'definition':r['definition'],'classification':r['classification'],**events})
 pd.DataFrame(ft).to_csv(OUT/'feature_timing_analysis.csv',index=False)
 # Compare classes and definitions; no strategy score.
 summary={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'purpose':'Discovery only; no entry/stop/target strategy selected','universe_candidates':len(c),'tickers_with_daily_ohlcv':len(frames),'signal_rows':len(rows),'unique_signal_tickers':len(set(r['ticker'] for r in rows)),'definitions_tested':sorted(set(r['definition'] for r in rows)),'classification_summary':stats_table(rows),'limitations':['Signal definitions are candidate event-timing definitions, not trading rules.','Outcomes begin after Signal Date; future OHLCV is never placed in features.','Historical Float and Short Interest are unavailable and excluded.','Rows are clustered by ticker in interpretation; no random row split is used.']}
 (OUT/'success_vs_failure.csv').write_text(pd.DataFrame(stats_table(rows)).to_csv(index=False),encoding='utf-8')
 # Hypotheses are explicitly proposed for later testing only.
 hyps=[{'id':'H1','name':'RSI Recovery + Volume Expansion','status':'hypothesis_only','features':['RSI recovery before signal','volume ratio expansion'],'not_tested_as_strategy':True},{'id':'H2','name':'RSI Rising + Base + Price Confirmation','status':'hypothesis_only','features':['positive RSI slope','base/consolidation','price expansion'],'not_tested_as_strategy':True},{'id':'H3','name':'Oversold Recovery + Price Confirmation','status':'hypothesis_only','features':['RSI recovery from below 30','positive price structure'],'not_tested_as_strategy':True},{'id':'H4','name':'Volume Leads RSI','status':'hypothesis_only','features':['first volume expansion precedes RSI recovery'],'not_tested_as_strategy':True}]
 (OUT/'hypotheses_phase2.json').write_text(json.dumps(hyps,ensure_ascii=False,indent=2),encoding='utf-8'); (OUT/'oos_results.json').write_text(json.dumps({'status':'not_run','reason':'Phase 2 is discovery-only; no rules frozen and no entry/stop/target selected.'},ensure_ascii=False,indent=2),encoding='utf-8')
 report(summary,rows,ft)

def report(s,rows,ft):
 lines=['# Phase 2 — First Explosion Start & RSI Timing Discovery','',f"Generated: {s['generated_at']}",'','## Status','', '**Discovery only.** This phase does not build a trading strategy and does not select Entry, Stop Loss, Take Profit, or Research Score.','', '## Objective','', 'The purpose is to identify when a rapid move first becomes observable without using the later knowledge that the stock eventually reached +70%. Several event-timing definitions are compared independently. Future prices are used only for outcomes after the signal date.','', '## Sample and coverage','',f"The current universe contains **{s['universe_candidates']} candidate rows**, **{s['tickers_with_daily_ohlcv']} tickers with daily OHLCV**, and **{s['signal_rows']} generated signal rows** across {len(s['definitions_tested'])} candidate definitions.",'', '| Definition | Meaning |','|---|---|','| A_10_from_low | First close at least 10% above the lowest close observed up to that date |','| B_20_from_low | First close at least 20% above the lowest close observed up to that date |','| C_20_in_1_3 | First close at least 20% above the close three sessions earlier |','| D_rapid_expansion | +20% over three sessions plus volume ratio 20D at least 1.5 |','| E_base_breakout | Close above prior ten-session high after a narrow base with volume expansion |','', '## Classification summary','', '| Class | Rows | Unique tickers | Mean RSI change S vs S-5 | Recovery rate | Mean max return 20 sessions |','|---|---:|---:|---:|---:|---:|']
 for x in s['classification_summary']: lines.append(f"| {x['class']} | {x['n']} | {x['tickers']} | {x['rsi_change_S_to_S-5_mean'] if x['rsi_change_S_to_S-5_mean'] is not None else '—'} | {x['rsi_recovery_rate']:.1%} | {x['mean_return_20']:.1f}% |" if x['rsi_recovery_rate'] is not None else f"| {x['class']} | {x['n']} | {x['tickers']} | — | — | {x['mean_return_20']:.1f}% |")
 lines+=['','## RSI timing fields','', 'For every candidate signal, RSI14 is recorded at S, S-1, S-2, S-3, S-4, S-5, S-6, S-7, S-10, S-15, and S-20. The outputs also include mean, median, minimum, maximum, range, changes over each lookback, and a five-session slope.','', 'The key question is not whether RSI is high at D-1 after a move. The key question is whether RSI recovery, RSI slope, price expansion, or volume expansion appears earliest before the candidate start date.','', '## Outcome design','', 'For each candidate signal date S, outcomes are measured only from S+1 onward over 1, 3, 5, 10, and 20 sessions. Each horizon tests +20%, +50%, +70%, +100%, and +200%. The future outcome is never used to create the signal features.','', '## Hypotheses for later testing only','', 'The following are hypotheses, not strategies: RSI Recovery + Volume Expansion; RSI Rising + Base + Price Confirmation; Oversold Recovery + Price Confirmation; and Volume Leads RSI. They must be frozen and tested only after this discovery report is reviewed.','', '## What is not concluded','', '- No definition is declared the best before comparing coverage, speed, class purity, and robustness.','- No RSI threshold is declared an entry condition.','- No OOS strategy result is produced in this phase.','- Historical Float and Short Interest remain unavailable and are not substituted with current values.','- Repeated observations from the same ticker must be interpreted with stock-level clustering.','', '## Files','', '- `explosion_start_cases.csv` and `.json`: candidate signal rows and post-signal outcomes.','- `rsi_timing_analysis.csv`: RSI and indicator snapshots by relative day.','- `rsi_distribution.csv`: RSI bins at candidate signal dates.','- `feature_timing_analysis.csv`: earliest observed indicator conditions in the available lookback grid.','- `success_vs_failure.csv`: class-level comparison summary.','- `hypotheses_phase2.json`: hypotheses reserved for later testing.','- `oos_results.json`: intentionally marked not run because no rules were frozen.','', '## Limitations','', *[f'- {x}' for x in s['limitations']]]
 (OUT/'research_phase2_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__':main()
