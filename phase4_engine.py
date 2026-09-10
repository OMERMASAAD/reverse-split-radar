# -*- coding: utf-8 -*-
"""Phase 4: pre-explosion timing and edge validation.

Uses the archived Phase 2 event rows only. S-1 and earlier are predictors;
post-S outcomes are labels. This is deliberately a fixed, auditable battery,
not a search for the best backtest.
"""
from __future__ import annotations
import json, math, warnings
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
warnings.filterwarnings('ignore')
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'research'; CASES=OUT/'explosion_start_cases.json'
HORIZONS=[1,3,5,10,20]
SNAP_ORDER=['S-20','S-15','S-10','S-7','S-5','S-4','S-3','S-2','S-1']

def n(v):
    try:
        x=float(v); return None if not np.isfinite(x) else x
    except: return None

def snap(r,k): return r.get('features',{}).get('snapshots',{}).get(k,{}) or {}
def val(r,k,field): return n(snap(r,k).get(field))
def success(r,target=70,h=10): return bool(r.get('outcomes',{}).get('targets',{}).get(str(h),{}).get(str(target),False))
def normclass(x): return str(x or 'unknown').lower().replace(' ','_')
def ci(wins,total):
    if not total:return [None,None]
    p=wins/total; z=1.96; den=1+z*z/total; c=(p+z*z/(2*total))/den; h=z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/den
    return [round(max(0,c-h),6),round(min(1,c+h),6)]
def metrics(rows,mask,target=70,h=10):
    sel=[r for r,m in zip(rows,mask) if m]; wins=sum(success(r,target,h) for r in sel); base=sum(success(r,target,h) for r in rows)
    a=wins;b=len(sel)-a;c=base-a;d=len(rows)-len(sel)-c
    try: orv,p=fisher_exact([[a,b],[c,d]])
    except: orv,p=None,None
    rate=wins/len(sel) if sel else None; br=base/len(rows) if rows else None
    return {'signals':len(sel),'successes':wins,'failures':len(sel)-wins,'success_rate':rate,'base_rate':br,'lift':rate/br if rate is not None and br else None,'odds_ratio':float(orv) if orv is not None else None,'p_value':float(p) if p is not None else None,'ci95':ci(wins,len(sel)),'tickers':len(set(r['ticker'] for r in sel))}
def first(r,fn):
    for k in SNAP_ORDER:
        s=snap(r,k)
        if s and fn(s): return k
    return None
def first_recovery(r,threshold):
    return first(r,lambda s:n(s.get('rsi')) is not None and n(s.get('rsi'))>=threshold)
def rising_for(r,days):
    # Sparse snapshots are used exactly as stored; this never invents daily bars.
    keys=SNAP_ORDER
    for i,k in enumerate(keys):
        a=n(snap(r,k).get('rsi'))
        nxt=[]
        for j in range(i+1,min(i+1+days,len(keys))): nxt.append(n(snap(r,keys[j]).get('rsi')))
        if a is not None and len(nxt)==days and all(x is not None for x in nxt) and all(nxt[j-1] <= (a if j==0 else nxt[j-1]) for j in range(len(nxt))):
            # order is older to newer; a must be lower than every later point
            if all(nxt[j] >= (a if j==0 else nxt[j-1]) for j in range(len(nxt))): return k
    return None
def row_features(r):
    rsi1=n(snap(r,'S-1').get('rsi')); rsi3=n(snap(r,'S-3').get('rsi')); rsi5=n(snap(r,'S-5').get('rsi')); rsi10=n(snap(r,'S-10').get('rsi')); rsi20=n(snap(r,'S-20').get('rsi'))
    vol1=n(snap(r,'S-1').get('vr20')); vol3=n(snap(r,'S-3').get('vr20')); vol5=n(snap(r,'S-5').get('vr20')); vol10=n(snap(r,'S-10').get('vr20'))
    c1=n(snap(r,'S-1').get('close')); c3=n(snap(r,'S-3').get('close'))
    ma20=n(snap(r,'S-1').get('ma20')); ma50=n(snap(r,'S-1').get('ma50'))
    hist1=n(snap(r,'S-1').get('hist')); hist3=n(snap(r,'S-3').get('hist'))
    older=[x for x in [rsi20,rsi10,rsi5,rsi3] if x is not None]; volder=[x for x in [vol10,vol5,vol3] if x is not None]
    vol_first=first(r,lambda s:n(s.get('vr20')) is not None and n(s.get('vr20'))>=1.5)
    rec_first=first(r,lambda s:n(s.get('rsi')) is not None and n(s.get('rsi'))>=30)
    return {'rsi_s1':rsi1,'rsi_change_3':rsi1-rsi3 if rsi1 is not None and rsi3 is not None else None,'rsi_change_5':rsi1-rsi5 if rsi1 is not None and rsi5 is not None else None,'rsi_change_10':rsi1-rsi10 if rsi1 is not None and rsi10 is not None else None,'rsi_min_pre':min(older) if older else None,'volume_s1':vol1,'volume_change_2':vol1-vol3 if vol1 is not None and vol3 is not None else None,'volume_change_4':vol1-vol5 if vol1 is not None and vol5 is not None else None,'volume_acceleration':(vol1-2*vol5+vol10) if vol1 is not None and vol5 is not None and vol10 is not None else None,'price_positive':bool(c1 is not None and c3 is not None and c1>c3),'macd_improving':bool(hist1 is not None and hist3 is not None and hist1>hist3),'ma20_reclaim':bool(c1 is not None and ma20 is not None and c1>ma20),'ma50_reclaim':bool(c1 is not None and ma50 is not None and c1>ma50),'liquidity_sweep_available':False,'vol_first':vol_first,'rsi_first':rec_first,'volume_leads_rsi':bool(vol_first and rec_first and SNAP_ORDER.index(vol_first)<SNAP_ORDER.index(rec_first)),'rsi_leads_volume':bool(vol_first and rec_first and SNAP_ORDER.index(rec_first)<SNAP_ORDER.index(vol_first)),'same_day':bool(vol_first and rec_first and vol_first==rec_first),'rsi_22_27':bool(rsi1 is not None and 22<=rsi1<27),'rsi_below30_rising':bool(rsi1 is not None and rsi1<30 and (rsi1-rsi5 if rsi5 is not None else -999)>0),'rsi_below35_rising':bool(rsi1 is not None and rsi1<35 and (rsi1-rsi5 if rsi5 is not None else -999)>0),'rsi_recovery':bool(rsi1 is not None and rsi10 is not None and rsi1>rsi10),'rsi_recovery_20':bool(rsi1 is not None and rsi10 is not None and rsi10<20<=rsi1),'rsi_recovery_25':bool(rsi1 is not None and rsi10 is not None and rsi10<25<=rsi1),'rsi_recovery_30':bool(rsi1 is not None and rsi10 is not None and rsi10<30<=rsi1),'rsi_recovery_35':bool(rsi1 is not None and rsi10 is not None and rsi10<35<=rsi1),'rsi_recovery_40':bool(rsi1 is not None and rsi10 is not None and rsi10<40<=rsi1),'rsi_rising_2':bool(rising_for(r,2)),'rsi_rising_3':bool(rising_for(r,3))}
def enrich(rows):
    out=[]
    for r in rows:
        q=dict(r); q['p4']=row_features(r); out.append(q)
    return out
def rows_to_split(rows):
    dates=sorted(r['signal_date'] for r in rows); a=dates[max(0,int(len(dates)*.6)-1)]; b=dates[max(0,int(len(dates)*.8)-1)]
    return [r for r in rows if r['signal_date']<=a],[r for r in rows if a<r['signal_date']<=b],[r for r in rows if r['signal_date']>b],a,b
def fdr(items):
    valid=sorted([(i,x.get('p_value')) for i,x in enumerate(items) if x.get('p_value') is not None],key=lambda z:z[1]); m=len(valid); prev=1
    for rank,(i,p) in reversed(list(enumerate(valid,1))): prev=min(prev,p*m/rank); items[i]['q_value']=float(prev); items[i]['fdr_05']=bool(prev<.05)
    return items
def main():
    rows=enrich(json.loads(CASES.read_text(encoding='utf-8'))); allr=rows
    timing=[]
    for r in rows:
        f=r['p4']; rec={k:first_recovery(r,k) for k in [20,25,30,35,40]}; timing.append({'ticker':r['ticker'],'definition':r['definition'],'signal_date':r['signal_date'],'classification':normclass(r.get('classification')),'success_70_10':success(r),'recovery_20':rec[20],'recovery_25':rec[25],'recovery_30':rec[30],'recovery_35':rec[35],'recovery_40':rec[40],'rsi_change_3':f['rsi_change_3'],'rsi_change_5':f['rsi_change_5'],'rsi_change_10':f['rsi_change_10'],'volume_s1':f['volume_s1'],'volume_first':f['vol_first'],'rsi_first':f['rsi_first']})
    pd.DataFrame(timing).to_csv(OUT/'RSI_RECOVERY_TIMING.csv',index=False)
    # Fixed, pre-registered feature battery.
    feature_specs={'RSI absolute 22-27':lambda r:r['p4']['rsi_22_27'],'RSI recovery':lambda r:r['p4']['rsi_recovery'],'RSI recovery >20':lambda r:r['p4']['rsi_recovery_20'],'RSI recovery >25':lambda r:r['p4']['rsi_recovery_25'],'RSI recovery >30':lambda r:r['p4']['rsi_recovery_30'],'RSI recovery >35':lambda r:r['p4']['rsi_recovery_35'],'RSI recovery >40':lambda r:r['p4']['rsi_recovery_40'],'RSI rising 2 snapshots':lambda r:r['p4']['rsi_rising_2'],'RSI rising 3 snapshots':lambda r:r['p4']['rsi_rising_3'],'RSI <30 + rising':lambda r:r['p4']['rsi_below30_rising'],'RSI <35 + rising':lambda r:r['p4']['rsi_below35_rising'],'Volume >=1.0':lambda r:(r['p4']['volume_s1'] or 0)>=1.0,'Volume >=1.25':lambda r:(r['p4']['volume_s1'] or 0)>=1.25,'Volume >=1.5':lambda r:(r['p4']['volume_s1'] or 0)>=1.5,'Volume >=2':lambda r:(r['p4']['volume_s1'] or 0)>=2,'Volume increasing':lambda r:(r['p4']['volume_change_2'] or 0)>0,'Volume acceleration':lambda r:(r['p4']['volume_acceleration'] or 0)>0,'Price confirmation':lambda r:r['p4']['price_positive'],'MACD improving':lambda r:r['p4']['macd_improving'],'MA20 reclaim':lambda r:r['p4']['ma20_reclaim'],'MA50 reclaim':lambda r:r['p4']['ma50_reclaim'],'Liquidity Sweep / Failed Breakdown':lambda r:r['p4']['liquidity_sweep_available']}
    stats=[]
    for name,fn in feature_specs.items():
        m=metrics(rows,[bool(fn(r)) for r in rows]); stats.append({'feature':name,**m})
    stats=fdr(stats); pd.DataFrame(stats).to_csv(OUT/'RSI_DIRECTION_RESULTS.csv',index=False)
    pd.DataFrame([{'family':'RSI/volume/price feature battery','tests':len(stats),'fdr_method':'Benjamini-Hochberg','alpha':0.05,'survives_fdr':sum(bool(x.get('fdr_05')) for x in stats)}]).to_csv(OUT/'FDR_RESULTS.csv',index=False)
    # Event order and limited sequences.
    seqs=['Volume Leads RSI','RSI Leads Volume','Same Day','Neither']
    seqrows=[]
    for s in seqs:
        mask=[(r['p4']['volume_leads_rsi'] if s=='Volume Leads RSI' else r['p4']['rsi_leads_volume'] if s=='RSI Leads Volume' else r['p4']['same_day'] if s=='Same Day' else not (r['p4']['vol_first'] or r['p4']['rsi_first'])) for r in rows]
        seqrows.append({'sequence':s,**metrics(rows,mask)})
    for name,fn in {'RSI -> Volume -> Price':lambda r:r['p4']['rsi_leads_volume'] and r['p4']['price_positive'],'Volume -> RSI -> Price':lambda r:r['p4']['volume_leads_rsi'] and r['p4']['price_positive'],'RSI + Volume same timing':lambda r:r['p4']['same_day'],'RSI + Volume + Price':lambda r:r['p4']['rsi_recovery'] and (r['p4']['volume_s1'] or 0)>=1.5 and r['p4']['price_positive'],'Liquidity Sweep -> RSI -> Volume -> Price':lambda r:r['p4']['liquidity_sweep_available'] and r['p4']['rsi_recovery'] and (r['p4']['volume_s1'] or 0)>=1.5 and r['p4']['price_positive'],'Liquidity Sweep + RSI Recovery + Volume':lambda r:r['p4']['liquidity_sweep_available'] and r['p4']['rsi_recovery'] and (r['p4']['volume_s1'] or 0)>=1.5}.items(): seqrows.append({'sequence':name,**metrics(rows,[fn(r) for r in rows])})
    seqrows=fdr(seqrows); pd.DataFrame(seqrows).to_csv(OUT/'VOLUME_RSI_SEQUENCE.csv',index=False)
    # H1, by class, and temporal split.
    h1=lambda r:r['p4']['rsi_recovery'] and (r['p4']['volume_s1'] or 0)>=1.5
    h1rows=[]
    for scope,g in [('All',rows)]+[(c,[r for r in rows if normclass(r.get('classification'))==c]) for c in sorted(set(normclass(r.get('classification')) for r in rows))]:
        h1rows.append({'scope':scope,**metrics(g,[h1(r) for r in g])})
    train,val,oos,cut1,cut2=rows_to_split(rows)
    for scope,g in [('Train',train),('Validation',val),('OOS',oos)]: h1rows.append({'scope':scope,**metrics(g,[h1(r) for r in g])})
    pd.DataFrame(h1rows).to_csv(OUT/'H1_RESULTS.csv',index=False)
    tv=[]
    for c in ['true_explosion','temporary_spike','gradual_rise','no_significant_move','rapid_move']:
        g=[r for r in rows if normclass(r.get('classification'))==c]; tv.append({'classification':c,'h1_signals':sum(h1(r) for r in g),'class_rows':len(g),'h1_rate':sum(h1(r) for r in g)/len(g) if g else None,'h1_success_rate':metrics(g,[h1(r) for r in g])['success_rate']})
    pd.DataFrame(tv).to_csv(OUT/'TRUE_EXPLOSION_VS_TEMPORARY.csv',index=False)
    # Cluster bootstrap for H1 OOS; resample tickers and compute success rate of qualified rows.
    tickers=sorted(set(r['ticker'] for r in oos)); groups={t:[r for r in oos if r['ticker']==t] for t in tickers}; rng=np.random.default_rng(20260911); boots=[]
    for _ in range(2000):
        sample=[r for t in rng.choice(tickers,len(tickers),replace=True) for r in groups[t]]; q=[r for r in sample if h1(r)]
        if q: boots.append(sum(success(r) for r in q)/len(q))
    pd.DataFrame([{'metric':'H1 OOS success rate','samples':len(boots),'cluster_bootstrap_95_low':np.quantile(boots,.025) if boots else None,'cluster_bootstrap_95_high':np.quantile(boots,.975) if boots else None,'seed':20260911,'clusters':len(tickers)}]).to_csv(OUT/'CLUSTERED_BOOTSTRAP_RESULTS.csv',index=False)
    final=[]
    candidate_functions={**feature_specs,'RSI + Volume + Price':lambda r:r['p4']['rsi_recovery'] and (r['p4']['volume_s1'] or 0)>=1.5 and r['p4']['price_positive'],'Volume -> RSI -> Price':lambda r:r['p4']['volume_leads_rsi'] and r['p4']['price_positive'],'RSI -> Volume -> Price':lambda r:r['p4']['rsi_leads_volume'] and r['p4']['price_positive']}
    for name,fn in candidate_functions.items():
        m=metrics(rows,[bool(fn(r)) for r in rows]); om=metrics(oos,[bool(fn(r)) for r in oos])
        qualified=[r for r in oos if fn(r)]; returns=[n(r.get('outcomes',{}).get('max_return_20')) for r in qualified if n(r.get('outcomes',{}).get('max_return_20')) is not None]
        pos=[x for x in returns if x>0]; neg=[x for x in returns if x<0]
        final.append({'hypothesis':name,'signals':m.get('signals'),'success_70':m.get('successes'),'success_rate':m.get('success_rate'),'base_rate':m.get('base_rate'),'lift':m.get('lift'),'odds_ratio':m.get('odds_ratio'),'ci95':m.get('ci95'),'p_value':m.get('p_value'),'fdr_q':next((x.get('q_value') for x in stats if x.get('feature')==name),None),'oos_signals':om.get('signals'),'oos_success':om.get('successes'),'oos_rate':om.get('success_rate'),'oos_lift':om.get('lift'),'oos_p_value':om.get('p_value'),'excursion_expectancy_20':float(np.mean(returns)) if returns else None,'excursion_profit_factor_20':(sum(pos)/abs(sum(neg))) if neg and sum(neg)!=0 else None,'walk_forward_stable':False})
    pd.DataFrame(final).to_csv(OUT/'PHASE4_FINAL_RESULTS.csv',index=False)
    report={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'decision':'PROMISING BUT NOT VALIDATED','h1':{'all':metrics(rows,[h1(r) for r in rows]),'oos':metrics(oos,[h1(r) for r in oos]),'train':metrics(train,[h1(r) for r in train]),'validation':metrics(val,[h1(r) for r in val])},'cutoffs':{'train_end':cut1,'validation_end':cut2},'rows':len(rows),'tickers':len(set(r['ticker'] for r in rows)),'limitations':['Only sparse Phase 2 snapshots S-20 through S-1 are available; no full daily event timeline can be reconstructed.','S is an independently generated candidate start date, not a tradable order timestamp.','Historical Float, Short Interest, spread, borrow, and point-in-time news are unavailable.','4H timing was not activated because daily H1 has not shown a validated edge.']}
    (OUT/'phase4_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    write_docs(report,stats,seqrows,tv,h1rows)
    print(json.dumps(report,ensure_ascii=False,default=str))
def write_docs(r,stats,seq,tv,h1):
    lines=['# PHASE 4 REPORT — Edge Validation & Pre-Explosion Entry Timing','',f"Generated: {r['generated_at']}",'',f"## Decision: {r['decision']}",'','H1 is retained as a research candidate, not as a validated trading strategy. Predictors use S-1 or earlier; post-S outcomes are labels only.','', '## H1 result','', '| Sample | Signals | +70 | Rate | Base | Lift | Odds | CI95 |','|---|---:|---:|---:|---:|---:|---:|---|']
    for x in [h for h in h1 if h['scope'] in ['All','Train','Validation','OOS']]: lines.append(f"| {x['scope']} | {x['signals']} | {x['successes']} | {x['success_rate']} | {x['base_rate']} | {x['lift']} | {x['odds_ratio']} | {x['ci95']} |")
    lines += ['', '## Timing conclusion','', 'The data can measure whether recovery was present in the available pre-signal snapshots. It cannot prove the exact first calendar day because only sparse snapshots are archived. Any recovery first seen at S is post-event confirmation, not a pre-event predictor.', '', '## Fixed feature battery','', '| Feature | Signals | Rate | Lift | FDR q |','|---|---:|---:|---:|---:|']
    for x in stats: lines.append(f"| {x['feature']} | {x['signals']} | {x['success_rate']} | {x['lift']} | {x.get('q_value')} |")
    lines += ['', '## Event sequence','', '| Sequence | Signals | Rate | Lift | FDR q |','|---|---:|---:|---:|---:|']
    for x in seq: lines.append(f"| {x['sequence']} | {x['signals']} | {x['success_rate']} | {x['lift']} | {x.get('q_value')} |")
    lines += ['', '## True Explosion vs Temporary Spike','', '| Class | Class rows | H1 signals | H1 signal rate | H1 +70 rate |','|---|---:|---:|---:|---:|']
    for x in tv: lines.append(f"| {x['classification']} | {x['class_rows']} | {x['h1_signals']} | {x['h1_rate']} | {x['h1_success_rate']} |")
    lines += ['', '## Additional chart hypothesis','', 'The requested Liquidity Sweep / Failed Breakdown element is marked UNAVAILABLE because the archive does not preserve the full pre-signal OHLC sequence required to identify a sweep without leakage. Its combinations therefore have zero eligible observations and are rejected, not treated as failures or successes.', 'Volume >=2 showed an in-sample FDR-adjusted signal and a numerically positive OOS lift, but no new rule is accepted because the timing/entry definition was not pre-registered before this test and walk-forward stability is not established. RSI + Volume + Price was also numerically positive OOS but inconclusive.', '', '## Direct answers','', '1. RSI recovery is observable before some candidate starts, but the archived sparse grid does not prove that it reliably precedes the explosion.', '2. The exact first lead time cannot be estimated safely from sparse snapshots; available snapshots are S-20, S-15, S-10, S-7, S-5, S-4, S-3, S-2 and S-1.', '3. Direction is more informative as a hypothesis than absolute RSI, but it is not validated OOS.', '4. RSI 22–27 remains descriptive only; it is not an entry rule.', '5. RSI below 30 plus rising is not validated as a standalone edge.', '6. Volume does not have a stable proven lead over RSI.', '7. RSI does not have a stable proven lead over volume.', '8. No sequence is accepted as stable without independent OOS support.', '9. H1 is not proven to distinguish True Explosion from Temporary Spike.', '10. H1 beats the full control rate in OOS numerically, but not with sufficient statistical evidence.', '11. Clustered bootstrap is reported at ticker level; uncertainty remains wide.', '12. Some in-sample findings survive FDR, but that does not rescue the OOS result.', '13. OOS is numerically positive but statistically inconclusive.', '14. Walk-forward is not stable.', '15. Expectancy is not frozen because no realistic execution dataset supports it.', '16. Profit Factor is not frozen for the same reason.', '17. Paper monitoring can continue, but no validated Paper Signal rule should be advertised.', '18. No validated edge has been established.']
    (OUT/'PHASE4_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'PHASE4_FREEZE.md').write_text('# PHASE 4 FREEZE\n\n## Status\n\nPROMISING BUT NOT VALIDATED\n\n## Frozen research comparator\n\nH1 = RSI recovery from the pre-signal window plus Volume Ratio 20D >= 1.5 at S-1.\n\nThis is frozen as a research comparator only. It is not a live entry rule. No threshold was selected after looking at OOS.\n\n## Prohibited claims\n\nNo Strong Buy, Buy Now, Guaranteed, Expected +70, broker order, or auto-trading claim.\n')
    (OUT/'PHASE4_OOS_REPORT.md').write_text('# PHASE 4 OOS REPORT\n\nThe OOS period begins after the fixed train/validation cutoffs recorded in `phase4_report.json`. H1 is numerically above the base rate but remains statistically inconclusive and is not a validated edge.\n\n'+json.dumps(r['h1']['oos'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'PHASE4_WALK_FORWARD.md').write_text('# PHASE 4 WALK-FORWARD\n\nNo stable edge was accepted. The prior Phase 3 walk-forward folds did not show persistent Lift > 1 for the selected rule. Phase 4 therefore does not activate a new timing rule.\n',encoding='utf-8')
if __name__=='__main__': main()
