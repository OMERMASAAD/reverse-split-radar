# -*- coding: utf-8 -*-
"""Auditable reverse-split strategy discovery.

The engine consumes labelled historical windows, enriches them with point-in-time
RSI snapshots from daily OHLCV when available, compares +70% cases with controls,
and writes machine-readable research outputs and a report. It never invents
float/short values when historical coverage is unavailable.
"""
from __future__ import annotations
import json, math, warnings
from pathlib import Path
from datetime import datetime, timezone
import numpy as np, pandas as pd
import yfinance as yf
from scipy import stats
warnings.filterwarnings('ignore')

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'research'/'raw_historical_cases.json'
OUT=ROOT/'research'
SNAPS=['D-20','D-15','D-10','D-7','D-5','D-4','D-3','D-2','D-1']
RSI_BINS=[(-math.inf,20),(20,22),(22,25),(25,27),(27,30),(30,35),(35,40),(40,50),(50,math.inf)]

def rsi(close,n=14):
    d=close.diff(); up=d.clip(lower=0); down=-d.clip(upper=0)
    a=up.ewm(alpha=1/n,min_periods=n,adjust=False).mean(); b=down.ewm(alpha=1/n,min_periods=n,adjust=False).mean()
    return 100-100/(1+a/b.replace(0,np.nan))

def num(x):
    try:
        v=float(x); return None if not np.isfinite(v) else v
    except: return None

def clean(v):
    if isinstance(v,(np.floating,np.integer)): return v.item()
    if isinstance(v,float) and not np.isfinite(v): return None
    return v

def download_prices(rows):
    tickers=sorted({r['ticker'] for r in rows})
    start=(min(pd.Timestamp(r['split_date']) for r in rows)-pd.Timedelta(days=60)).date().isoformat()
    end=(max(pd.Timestamp(r.get('explosion_date',r.get('observation_date'))) for r in rows)+pd.Timedelta(days=3)).date().isoformat()
    frames={}
    for i in range(0,len(tickers),40):
        chunk=tickers[i:i+40]; print(f'download {i+1}-{i+len(chunk)}/{len(tickers)}',flush=True)
        try:
            z=yf.download(chunk,start=start,end=end,auto_adjust=False,actions=False,group_by='ticker',threads=True,progress=False)
            for t in chunk:
                try:
                    x=z[t].copy() if isinstance(z.columns,pd.MultiIndex) and t in z.columns.get_level_values(0) else z.copy()
                    if 'Close' not in x: continue
                    x=x[['Open','High','Low','Close','Volume']].dropna(subset=['Close']); x.index=pd.to_datetime(x.index).tz_localize(None); frames[t]=x
                except Exception: pass
        except Exception as e: print('download error',str(e)[:120])
    return frames

def snapshots(frame, date):
    if frame is None or frame.empty: return {}
    d=pd.Timestamp(date); x=frame.loc[frame.index<=d].copy()
    if len(x)<20: return {}
    x['rsi14']=rsi(x.Close); x['ma20']=x.Close.rolling(20).mean(); x['ma50']=x.Close.rolling(50).mean()
    x['ema12']=x.Close.ewm(span=12,adjust=False).mean(); x['ema26']=x.Close.ewm(span=26,adjust=False).mean(); x['macd']=x.ema12-x.ema26; x['signal']=x.macd.ewm(span=9,adjust=False).mean(); x['hist']=x.macd-x.signal
    out={}
    for k,n in [('D-20',20),('D-15',15),('D-10',10),('D-7',7),('D-5',5),('D-4',4),('D-3',3),('D-2',2),('D-1',1)]:
        if len(x)>=n: 
            q=x.iloc[-n]; out[k]={'date':q.name.date().isoformat(),'rsi14':num(q.rsi14),'macd':num(q.macd),'macd_signal':num(q.signal),'macd_histogram':num(q.hist),'close':num(q.Close),'volume':num(q.Volume),'ma20':num(q.ma20),'ma50':num(q.ma50)}
    return out

def enrich(rows,frames):
    out=[]
    for r in rows:
        obs=r.get('explosion_date',r.get('observation_date')); s=snapshots(frames.get(r['ticker']),obs)
        q=dict(r); q['point_in_time_snapshots']=s; q['data_coverage']={'rsi_snapshots':len([v for v in s.values() if v.get('rsi14') is not None]),'required_rsi_snapshots':len(SNAPS),'historical_float':False,'historical_short':False}; out.append(q)
    return out

def vals(rows,key):
    return [num(r.get('features',{}).get(key)) for r in rows if num(r.get('features',{}).get(key)) is not None]

def feature_stats(success,control):
    keys=sorted(set().union(*(r.get('features',{}).keys() for r in success+control)))
    result={}
    for k in keys:
        a,b=vals(success,k),vals(control,k)
        if len(a)<5 or len(b)<5: continue
        u,p=stats.mannwhitneyu(a,b,alternative='two-sided')
        diff=float(np.mean(a)-np.mean(b)); se=math.sqrt(np.var(a,ddof=1)/len(a)+np.var(b,ddof=1)/len(b)) if len(a)>1 and len(b)>1 else None
        result[k]={'success_n':len(a),'control_n':len(b),'success_mean':float(np.mean(a)),'control_mean':float(np.mean(b)),'success_median':float(np.median(a)),'control_median':float(np.median(b)),'success_std':float(np.std(a,ddof=1)) if len(a)>1 else None,'control_std':float(np.std(b,ddof=1)) if len(b)>1 else None,'mean_difference':diff,'mean_difference_ci95':[diff-1.96*se,diff+1.96*se] if se else None,'cliffs_delta':float(2*u/(len(a)*len(b))-1),'mann_whitney_u':float(u),'p_value':float(p),'lift_median':float((np.median(a)-np.median(b))/(abs(np.median(b))+1e-9))}
    return result

def rsi_analysis(success,control):
    def all_snap(rows, day): return [num(r.get('point_in_time_snapshots',{}).get(day,{}).get('rsi14')) for r in rows if num(r.get('point_in_time_snapshots',{}).get(day,{}).get('rsi14')) is not None]
    result={'coverage':{},'snapshots':{},'bins_D-1':[],'trend_tests':{}}
    for day in SNAPS:
        a,b=all_snap(success,day),all_snap(control,day); result['coverage'][day]={'success':len(a),'control':len(b),'required_success':len(success),'required_control':len(control)}
        if a:
            result['snapshots'][day]={'success_mean':float(np.mean(a)),'success_median':float(np.median(a)),'success_min':float(np.min(a)),'success_max':float(np.max(a)),'success_std':float(np.std(a,ddof=1)) if len(a)>1 else 0,'success_percentiles':{str(q):float(np.percentile(a,q)) for q in [10,25,50,75,90]},'control_mean':float(np.mean(b)) if b else None,'control_median':float(np.median(b)) if b else None}
    for lo,hi in RSI_BINS:
        a=[v for v in all_snap(success,'D-1') if lo<=v<hi]; b=[v for v in all_snap(control,'D-1') if lo<=v<hi]; total=len(a)+len(b)
        result['bins_D-1'].append({'range':f'{lo if np.isfinite(lo) else "<"}{"-" if np.isfinite(lo) else ""}{hi if np.isfinite(hi) else "+"}','success_cases':len(a),'control_cases':len(b),'success_rate':len(a)/total if total else None})
    s5,s3,s1=[],[],[]
    for r in success:
        q=r.get('point_in_time_snapshots',{}); 
        if all(num(q.get(k,{}).get('rsi14')) is not None for k in ['D-5','D-3','D-1']): s5.append(q['D-5']['rsi14']);s3.append(q['D-3']['rsi14']);s1.append(q['D-1']['rsi14'])
    if s1:
        a5,a3,a1=np.array(s5),np.array(s3),np.array(s1); delta=a1-a5
        result['trend_tests']={'n':len(s1),'d5_to_d1_mean':float(np.mean(delta)),'d3_to_d1_mean':float(np.mean(a1-a3)),'rsi_recovery_rate':float(np.mean(delta>0)),'rsi_d5_22_27_rate':float(np.mean((a5>=22)&(a5<27))),'low_decreasing':int(np.sum((a5<30)&(delta<-2))),'low_stable':int(np.sum((a5<30)&(np.abs(delta)<=2))),'low_rising':int(np.sum((a5<30)&(delta>2))),'cross_20_up':int(np.sum((a5<20)&(a1>=20))),'cross_25_up':int(np.sum((a5<25)&(a1>=25))),'cross_30_up':int(np.sum((a5<30)&(a1>=30))),'reclaim_35':int(np.sum((a5<35)&(a1>=35)))}
    return result

def thresholds(success):
    result={}
    for t in [20,50,70,100,200]:
        events=[e for r in success for e in r.get('all_threshold_events',[]) if e.get('threshold')==t]
        if t in (20,50) and not events:
            gains=[num(r.get('maximum_gain_percent')) for r in success if num(r.get('maximum_gain_percent')) is not None and num(r.get('maximum_gain_percent'))>=t]
            result[str(t)]={'successful_events':len(gains),'unique_tickers':len({r.get('ticker') for r in success if num(r.get('maximum_gain_percent')) is not None and num(r.get('maximum_gain_percent'))>=t}),'median_sessions':None,'median_days':None,'scope':'within the labelled +70% cohort; full-universe first-hit labels unavailable'}
        else:
            result[str(t)]={'successful_events':len(events),'unique_tickers':len({e.get('ticker',r.get('ticker')) for r,e in [(r,e) for r in success for e in r.get('all_threshold_events',[]) if e.get('threshold')==t]}),'median_sessions':float(np.median([e['trading_sessions_from_split_to_explosion'] for e in events])) if events else None,'median_days':float(np.median([e['days_from_split_to_explosion'] for e in events])) if events else None,'scope':'labelled event threshold'}
    return result

def combos(success,control):
    rows=success+control; labels=np.array([1]*len(success)+[0]*len(control)); out=[]
    tests={'rsi_22_27':lambda r:22<=num(r.get('features',{}).get('rsi14') or -1)<27,'rsi_recovering':lambda r:num(r.get('features',{}).get('rsi_change_5d')) is not None and r['features']['rsi_change_5d']>0,'support_2plus':lambda r:num(r.get('features',{}).get('support_tests_20d') or 0)>=2,'drawdown_30':lambda r:num(r.get('features',{}).get('drawdown_from_previous_peak_percent') or 0)<=-30,'volume_1_05':lambda r:num(r.get('features',{}).get('volume_ratio_20d') or 0)>=1.05,'macd_improving':lambda r:num(r.get('features',{}).get('histogram_change') or 0)>0}
    names=list(tests)
    for n in names:
        for m in names:
            if n>=m: continue
            mask=np.array([tests[n](r) and tests[m](r) for r in rows]); den=mask.sum(); wins=labels[mask].sum(); out.append({'combination':n+' + '+m,'n':int(den),'successes':int(wins),'success_rate':float(wins/den) if den else None,'coverage':float(den/len(rows))})
    return sorted(out,key=lambda z:(z['success_rate'] if z['success_rate'] is not None else -1,z['n']),reverse=True)

def strategy_backtest(success,control,frames):
    """Next-session open, stop -20%, target exits; no intrabar best-price assumption.

    Labels are kept separate from the execution simulation: controls are the
    non-event windows and successes are the +70% event windows.
    """
    rows=[]
    for label,group in [(1,success),(0,control)]:
        for r in group:
            f=frames.get(r['ticker']); obs=pd.Timestamp(r.get('explosion_date',r.get('observation_date')))
            if f is None or f.empty: continue
            future=f.loc[f.index>obs].head(12)
            if future.empty: continue
            feat=r.get('features',{})
            rule=bool(num(feat.get('drawdown_from_previous_peak_percent')) is not None and num(feat.get('drawdown_from_previous_peak_percent'))<=-30 and num(feat.get('volume_ratio_20d')) is not None and num(feat.get('volume_ratio_20d'))>=1.05)
            rows.append({'ticker':r['ticker'],'date':obs.date().isoformat(),'label':label,'rule':rule,'entry':num(future.iloc[0].Open),'future':future})
    eligible=[r for r in rows if r['rule'] and r['entry'] and r['entry']>0]
    dates=sorted(r['date'] for r in eligible); cut=dates[max(0,int(len(dates)*.7)-1)] if dates else None
    def calc(sample):
        out={}
        for target in [20,50,70,100,200]:
            wins=[]; losses=[]; holds=[]
            for r in sample:
                entry=r['entry']; stop=entry*.80; target_px=entry*(1+target/100); result=None
                for i,(_,bar) in enumerate(r['future'].iterrows(),1):
                    o,h,l=float(bar.Open),float(bar.High),float(bar.Low)
                    if o>=target_px: result=target/100; holds.append(i); break
                    if o<=stop: result=(o/entry)-1; losses.append(result); holds.append(i); break
                    # Conservative ordering when both stop and target occur in one bar.
                    if l<=stop: result=-.20; losses.append(result); holds.append(i); break
                    if h>=target_px: result=target/100; wins.append(result); holds.append(i); break
                if result is None:
                    close=float(r['future'].iloc[-1].Close); result=close/entry-1; (wins if result>0 else losses).append(result); holds.append(len(r['future']))
            allret=wins+losses; gross=sum(wins); loss_abs=abs(sum(x for x in losses if x<0))
            out[str(target)]={'trades':len(allret),'wins':sum(x>=target/100 for x in allret),'win_rate':sum(x>=target/100 for x in allret)/len(allret) if allret else None,'avg_return':float(np.mean(allret)) if allret else None,'median_return':float(np.median(allret)) if allret else None,'profit_factor':gross/loss_abs if loss_abs else None,'max_holding_sessions':max(holds) if holds else None}
        return out
    return {'rule':'drawdown <= -30% AND volume_ratio_20d >= 1.05','all':calc(eligible),'train':calc([r for r in eligible if not cut or r['date']<=cut]),'out_of_sample':calc([r for r in eligible if cut and r['date']>cut]),'eligible_trades':len(eligible),'train_cutoff':cut,'note':'Entry is next available session open. Stop/target ordering is conservative; this is not a broker fill simulation.'}

def main():
    OUT.mkdir(exist_ok=True); d=json.loads(RAW.read_text(encoding='utf-8')); success=d['success_cases']; control=d['control_windows']; allrows=success+control
    frames=download_prices(allrows); enriched=enrich(allrows,frames); es=enriched[:len(success)]; ec=enriched[len(success):]
    # Save enriched cases separately; do not overwrite the original labels.
    (OUT/'enriched_cases.json').write_text(json.dumps(enriched,ensure_ascii=False,indent=2,default=clean),encoding='utf-8')
    fs=feature_stats(success,control); ra=rsi_analysis(es,ec); th=thresholds(success); co=combos(success,control); bt=strategy_backtest(success,control,frames)
    coverage={'cases':len(allrows),'tickers_requested':len(set(r['ticker'] for r in allrows)),'tickers_downloaded':len(frames),'rsi_D-1_success':ra['coverage']['D-1']['success'],'rsi_D-1_control':ra['coverage']['D-1']['control'],'historical_float':0,'historical_short':0}
    report={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'methodology':{'primary_label':'+70%','lookback_calendar_days':180,'features_pre_event_only':True,'control_group':True,'point_in_time_fundamentals':False,'note':'Float/Short historical coverage is unavailable and is not substituted with current values.'},'sample':{'success_cases':len(success),'control_windows':len(control),'unique_success_tickers':len(set(r['ticker'] for r in success))},'data_coverage':coverage,'thresholds':th,'rsi_analysis':ra,'feature_statistics':fs,'combination_tests':co[:30],'limitations':['The archived labels are event-labelled windows; they are not a broker-executable portfolio backtest.','RSI snapshots are computed only where OHLCV history is available.','Float and Short Interest are excluded from causal conclusions because point-in-time history is unavailable.','Multiple windows can belong to one ticker; confidence intervals should be clustered by ticker in a later revision.']}
    report['strategy_backtest']=bt
    (OUT/'statistical_analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=clean),encoding='utf-8')
    (OUT/'strategy_backtest.json').write_text(json.dumps(bt,ensure_ascii=False,indent=2,default=clean),encoding='utf-8')
    write_report(report,success,control)

def write_report(r,success,control):
    ra=r['rsi_analysis']; th=r['thresholds']; top=r['combination_tests'][:5]; cov=r['data_coverage']
    lines=['# Reverse Split Explosion Radar — Statistical Strategy Discovery','',f"Generated: {r['generated_at']}",'','## Executive conclusion','',f"The research universe contains **{r['sample']['success_cases']} +70% success windows** and **{r['sample']['control_windows']} control windows** from the 180-calendar-day universe. This is a discovery study, not a validated live strategy. The key point is that RSI 22–27 is tested rather than assumed.",'', '## Threshold outcomes','', '| Target | Successful events | Median sessions | Median calendar days |','|---|---:|---:|---:|']
    for k,v in th.items(): lines.append(f"| +{k}% | {v['successful_events']} | {v['median_sessions'] if v['median_sessions'] is not None else '—'} | {v['median_days'] if v['median_days'] is not None else '—'} |")
    lines+=['','## RSI14 analysis','',f"RSI D-1 coverage: {cov['rsi_D-1_success']} successful windows and {cov['rsi_D-1_control']} controls. Historical OHLCV coverage determines whether earlier snapshots D-20 through D-2 are populated.",'','| Snapshot | Success mean | Success median | Control mean | Control median |','|---|---:|---:|---:|---:|']
    for k,v in ra['snapshots'].items(): lines.append(f"| {k} | {v.get('success_mean','—'):.2f} | {v.get('success_median','—'):.2f} | {v.get('control_mean','—') if v.get('control_mean') is not None else '—'} | {v.get('control_median','—') if v.get('control_median') is not None else '—'} |")
    lines+=['','### RSI 22–27 test','', '| RSI D-1 range | Success cases | Control cases | Success rate |','|---|---:|---:|---:|']
    for v in ra['bins_D-1']: lines.append(f"| {v['range']} | {v['success_cases']} | {v['control_cases']} | {v['success_rate']:.1%} |" if v['success_rate'] is not None else f"| {v['range']} | {v['success_cases']} | {v['control_cases']} | — |")
    lines+=['','## Feature comparison','', 'Feature statistics, p-values, effect proxies, and median lift are in `statistical_analysis.json`. These are discovery statistics and are not adjusted for multiple testing.','', '## Candidate combinations','', '| Combination | N | Successes | Success rate | Coverage |','|---|---:|---:|---:|---:|']
    for v in top: lines.append(f"| {v['combination']} | {v['n']} | {v['successes']} | {v['success_rate']:.1%} | {v['coverage']:.1%} |" if v['success_rate'] is not None else f"| {v['combination']} | {v['n']} | {v['successes']} | — | {v['coverage']:.1%} |")
    bt=r.get('strategy_backtest',{})
    lines+=['','## Candidate next-session backtest','',f"Rule tested: `{bt.get('rule','—')}`. Eligible windows: **{bt.get('eligible_trades','—')}**; train cutoff: **{bt.get('train_cutoff','—')}**. Entry is the next available session open, with a conservative -20% stop and target exits.",'', '| Target | Trades | Win rate | Avg return | Profit factor | OOS win rate |','|---|---:|---:|---:|---:|---:|']
    for k,v in bt.get('all',{}).items():
        o=bt.get('out_of_sample',{}).get(k,{})
        lines.append(f"| +{k}% | {v.get('trades',0)} | {v.get('win_rate',0):.1%} | {v.get('avg_return',0):.1%} | {v.get('profit_factor') if v.get('profit_factor') is not None else '—'} | {o.get('win_rate',0):.1%} |")
    lines+=['','## Final status','', '**No final validated STRONG SETUP is declared yet.** The candidate rule is shown for auditability, not adoption. It must survive an independent later sample, clustered confidence intervals, realistic liquidity/slippage, and a pre-registered stop/target policy before being considered a strategy.','', '## Data limitations','', '- Historical Float and Short Interest are not available point-in-time and are not used as predictors.','- A success label is event-based (+70% reached); it is not by itself an executable trade return.','- Duplicate windows may belong to the same ticker; future confidence intervals should cluster by ticker.','- Current outputs should not be interpreted as investment advice.']
    (OUT/'research_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__': main()
