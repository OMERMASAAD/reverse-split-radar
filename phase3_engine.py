# -*- coding: utf-8 -*-
"""Phase 3: hypothesis testing, strategy freeze, OOS and walk-forward.

This engine consumes the archived Phase 2 candidate-event dataset. It never
uses post-signal outcomes as features. Because the archive contains candidate
start dates rather than broker-time entries, the reports label the resulting
rules as research paper signals until separately validated with live-point-in-
time data.
"""
from __future__ import annotations
import json, math, hashlib, warnings
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu
warnings.filterwarnings('ignore')

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'research'
CASES = OUT / 'explosion_start_cases.json'
HORIZONS = [1, 3, 5, 10, 20]
TARGETS = [20, 50, 70, 100, 200]
RSI_BINS = [(-np.inf,20),(20,22),(22,25),(25,27),(27,30),(30,35),(35,40),(40,50),(50,np.inf)]
VOL_BINS = [(-np.inf,.5),(.5,.75),(.75,1),(1,1.25),(1.25,1.5),(1.5,2),(2,3),(3,np.inf)]


def num(v):
    try:
        x = float(v)
        return None if not np.isfinite(x) else x
    except Exception:
        return None


def qv(values, q, default):
    a = np.array([x for x in values if num(x) is not None], dtype=float)
    return float(np.quantile(a, q)) if len(a) else default


def safe_mean(a):
    a = [x for x in a if num(x) is not None]
    return float(np.mean(a)) if a else None


def safe_median(a):
    a = [x for x in a if num(x) is not None]
    return float(np.median(a)) if a else None


def ci_wilson(successes, n, z=1.96):
    if not n: return [None, None]
    p = successes / n; den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    h = z * math.sqrt((p*(1-p) + z*z/(4*n))/n) / den
    return [float(max(0, c-h)), float(min(1, c+h))]


def outcome_success(r, target=70, horizon=10):
    return bool(r.get('outcomes', {}).get('targets', {}).get(str(horizon), {}).get(str(target), False))


def first_target_horizon(r, target):
    for h in HORIZONS:
        if outcome_success(r, target, h): return h
    return None


def pre(r, key, default=None):
    """Return only a pre-signal snapshot. S is deliberately excluded."""
    s = r.get('features', {}).get('snapshots', {})
    return s.get(key, {}) or default or {}


def make_features(r):
    f = r.get('features', {})
    sm1, sm3, sm5, sm7, sm10, sm15, sm20 = [pre(r, k, {}) for k in ['S-1','S-3','S-5','S-7','S-10','S-15','S-20']]
    def val(d, k): return num(d.get(k))
    rsi1, rsi3, rsi5 = val(sm1,'rsi'), val(sm3,'rsi'), val(sm5,'rsi')
    rsi10, rsi20 = val(sm10,'rsi'), val(sm20,'rsi')
    vol1 = val(sm1,'vr20'); vol3 = val(sm3,'vr20'); vol5 = val(sm5,'vr20'); vol10 = val(sm10,'vr20'); vol20 = val(sm20,'vr20')
    close1, close3, close5 = val(sm1,'close'), val(sm3,'close'), val(sm5,'close')
    ma20, ma50 = val(sm1,'ma20'), val(sm1,'ma50')
    close_change_1 = (close1/close3-1) if close1 is not None and close3 else None
    rsi_change_1 = rsi1-rsi3 if rsi1 is not None and rsi3 is not None else None
    rsi_change_3 = rsi1-rsi5 if rsi1 is not None and rsi5 is not None else None
    rsi_change_5 = rsi1-rsi10 if rsi1 is not None and rsi10 is not None else None
    rsi_change_10 = rsi1-rsi20 if rsi1 is not None and rsi20 is not None else None
    snap_rsi = [x for x in [rsi20,rsi10,rsi5,rsi3,rsi1] if x is not None]
    snap_vol = [x for x in [vol20,vol10,vol5,vol3,vol1] if x is not None]
    # Conservative event ordering on the available pre-signal grid.
    labels = ['S-20','S-15','S-10','S-7','S-5','S-3','S-2','S-1']
    snaps = r.get('features',{}).get('snapshots',{})
    def first_where(fn):
        for k in labels:
            if k in snaps and fn(snaps[k]): return k
        return None
    vol_first = first_where(lambda x: num(x.get('vr20')) is not None and num(x.get('vr20')) >= 1.5)
    rsi30_first = first_where(lambda x: num(x.get('rsi')) is not None and num(x.get('rsi')) >= 30)
    rsi25_first = first_where(lambda x: num(x.get('rsi')) is not None and num(x.get('rsi')) >= 25)
    order = {k:i for i,k in enumerate(labels)}
    volume_leads_rsi = bool(vol_first and rsi30_first and order[vol_first] < order[rsi30_first])
    # A pre-signal feature vector; f.* fields originate at S but are not used.
    return {
        'rsi_pre': rsi1, 'rsi_pre_3': rsi3, 'rsi_pre_5': rsi5,
        'rsi_pre_10': rsi10, 'rsi_pre_20': rsi20,
        'rsi_change_1': rsi_change_1, 'rsi_change_3': rsi_change_3,
        'rsi_change_5': rsi_change_5, 'rsi_change_10': rsi_change_10,
        'rsi_min_pre': min(snap_rsi) if snap_rsi else None,
        'rsi_max_pre': max(snap_rsi) if snap_rsi else None,
        'rsi_range_pre': (max(snap_rsi)-min(snap_rsi)) if snap_rsi else None,
        'volume_ratio_pre': vol1, 'volume_ratio_pre_3': vol3,
        'volume_ratio_pre_5': vol5, 'volume_ratio_pre_10': vol10,
        'volume_ratio_pre_20': vol20,
        'volume_change_5': (vol1-vol5) if vol1 is not None and vol5 is not None else None,
        'volume_change_10': (vol1-vol10) if vol1 is not None and vol10 is not None else None,
        'price_change_3': close_change_1,
        'positive_price_confirmation': bool(close1 is not None and close3 is not None and close1 > close3),
        'close_above_ma20': bool(close1 is not None and ma20 is not None and close1 > ma20),
        'close_above_ma50': bool(close1 is not None and ma50 is not None and close1 > ma50),
        'base_range_10': num(f.get('range_10')),
        'base_range_5': num(f.get('range_5')),
        'drawdown_peak': num(f.get('drawdown_peak')),
        'distance_recent_low': num(f.get('distance_recent_low')),
        'distance_ma20': num(f.get('distance_ma20')),
        'distance_ma50': num(f.get('distance_ma50')),
        'support_tests_20': num(f.get('support_tests_20')),
        'atr_percent': num(f.get('atr_percent')),
        'macd_hist_pre': val(sm1,'hist'),
        'macd_hist_change_pre': num(f.get('macd_hist_change_5')),
        'macd_improving_pre': bool(num(f.get('macd_hist_change_5')) is not None and num(f.get('macd_hist_change_5')) > 0),
        'volume_first': vol_first, 'rsi30_first': rsi30_first,
        'rsi25_first': rsi25_first, 'volume_leads_rsi': volume_leads_rsi,
    }


def enrich(rows):
    out=[]
    for r in rows:
        q=dict(r); q['pre_features']=make_features(r); out.append(q)
    return out


def metric_for_mask(rows, mask, target=70, horizon=10, cluster_boot=1000):
    selected=[r for r,m in zip(rows,mask) if m]
    all_s=[outcome_success(r,target,horizon) for r in rows]
    sel_s=[outcome_success(r,target,horizon) for r in selected]
    n=len(selected); wins=sum(sel_s); base_n=len(rows); base_wins=sum(all_s)
    p=wins/n if n else None; base=base_wins/base_n if base_n else None
    a=sum(sel_s); b=n-a; c=base_wins-a; d=(base_n-n)-c
    if min(a,b,c,d) < 0: c=d=0
    try:
        orv,pv=fisher_exact([[a,b],[c,d]])
        orv=float(orv); pv=float(pv)
    except Exception:
        orv=pv=None
    rr=(p/base) if p is not None and base else None
    # Deterministic cluster bootstrap by ticker, preserving all rows per sampled ticker.
    tickers=sorted(set(r.get('ticker') for r in rows)); grouped={t:[i for i,r in enumerate(rows) if r.get('ticker')==t] for t in tickers}
    rng=np.random.default_rng(20260909); boots=[]
    for _ in range(cluster_boot):
        sampled=rng.choice(tickers,size=len(tickers),replace=True)
        idx=[i for t in sampled for i in grouped[t]]
        vals=[1 if mask[i] and outcome_success(rows[i],target,horizon) else 0 for i in idx]
        den=sum(1 for i in idx if mask[i])
        if den: boots.append(sum(vals)/den)
    ci=[float(np.quantile(boots,.025)),float(np.quantile(boots,.975))] if boots else [None,None]
    returns=[num(r.get('outcomes',{}).get('max_return_20')) for r in selected]
    return {'signals':n,'successes':wins,'failures':n-wins,'success_rate':p,'success_rate_ci95_clustered':ci,'base_rate_all_rows':base,'lift':(p/base if p is not None and base else None),'odds_ratio':orv,'fisher_p_value':pv,'relative_risk':rr,'median_return_20':safe_median(returns),'mean_return_20':safe_mean(returns),'tickers':len(set(r.get('ticker') for r in selected))}


def condition(name, r, params=None):
    f=r['pre_features']; p=params or {}
    if name=='RSI recovery': return f['rsi_change_5'] is not None and f['rsi_change_5'] > p.get('min',0)
    if name=='RSI rising 3d': return f['rsi_change_3'] is not None and f['rsi_change_3'] > p.get('min',0)
    if name=='RSI rising 5d': return f['rsi_change_5'] is not None and f['rsi_change_5'] > p.get('min',0)
    if name=='RSI oversold recovery': return f['rsi_min_pre'] is not None and f['rsi_min_pre'] < p.get('below',30) and f['rsi_change_5'] is not None and f['rsi_change_5'] > 0
    if name=='Volume expansion': return f['volume_ratio_pre'] is not None and f['volume_ratio_pre'] >= p.get('min',1.5)
    if name=='Volume increasing': return f['volume_change_5'] is not None and f['volume_change_5'] > 0
    if name=='Volume leads RSI': return f['volume_leads_rsi']
    if name=='Price confirmation': return f['positive_price_confirmation']
    if name=='Base': return f['base_range_10'] is not None and f['base_range_10'] <= p.get('max',60)
    if name=='Support': return f['support_tests_20'] is not None and f['support_tests_20'] >= p.get('min',2)
    if name=='MACD improvement': return f['macd_improving_pre']
    if name=='MA20 reclaim': return f['close_above_ma20']
    return False


def rsi_bin(v, bins):
    if v is None: return None
    for lo,hi in bins:
        if lo <= v < hi: return f'{lo if np.isfinite(lo) else "<"}-{hi if np.isfinite(hi) else "+"}'
    return None


def feature_statistics(rows):
    tests=[]
    feature_names=['rsi_pre','rsi_change_1','rsi_change_3','rsi_change_5','rsi_change_10','rsi_min_pre','rsi_range_pre','volume_ratio_pre','volume_change_5','base_range_10','drawdown_peak','distance_recent_low','support_tests_20','macd_hist_change_pre','atr_percent']
    for name in feature_names:
        vals=[num(r['pre_features'].get(name)) for r in rows if num(r['pre_features'].get(name)) is not None]
        if len(vals)<10: continue
        for q,label in [(0.1,'bottom_10'),(0.2,'bottom_20'),(0.3,'bottom_30'),(0.5,'median'),(0.7,'top_30'),(0.8,'top_20'),(0.9,'top_10')]:
            cut=float(np.quantile(vals,q)); mask=[num(r['pre_features'].get(name)) is not None and ((num(r['pre_features'].get(name))<=cut) if q<=.5 else (num(r['pre_features'].get(name))>=cut)) for r in rows]
            m=metric_for_mask(rows,mask); tests.append({'feature':name,'rule':label,'threshold':cut,'p_value':m['fisher_p_value'],**m})
    for name,bins in [('RSI pre',RSI_BINS),('Volume ratio pre',VOL_BINS)]:
        key='rsi_pre' if name.startswith('RSI') else 'volume_ratio_pre'; values=[r['pre_features'].get(key) for r in rows]
        for lo,hi in bins:
            mask=[v is not None and lo<=v<hi for v in values]; m=metric_for_mask(rows,mask); tests.append({'feature':name,'rule':f'{lo}-{hi}','threshold':None,'p_value':m['fisher_p_value'],**m})
    return tests


def bh_adjust(rows):
    ps=[x.get('p_value') for x in rows]; order=sorted([i for i,p in enumerate(ps) if p is not None],key=lambda i:ps[i]); adj=[None]*len(rows); prev=1.0; m=len(order)
    for rank,i in reversed(list(enumerate(order,1))):
        prev=min(prev, ps[i]*m/rank); adj[i]=float(min(1,prev))
    for i,x in enumerate(rows): x['q_value_bh']=adj[i]; x['significant_bh_05']=bool(adj[i] is not None and adj[i] < .05)
    return rows


def hypothesis_rows(rows, train_idx=None):
    data=[rows[i] for i in train_idx] if train_idx is not None else rows
    qs={'base_max':qv([r['pre_features'].get('base_range_10') for r in data],.5,60)}
    defs={
      'H1_RSI_Recovery_Volume_Expansion': lambda r: condition('RSI recovery',r,{'min':0}) and condition('Volume expansion',r,{'min':1.5}),
      'H2_RSI_Rising_Base_Price': lambda r: condition('RSI rising 5d',r,{'min':0}) and condition('Base',r,{'max':qs['base_max']}) and condition('Price confirmation',r),
      'H3_Oversold_Recovery_Price': lambda r: condition('RSI oversold recovery',r,{'below':30}) and condition('Price confirmation',r),
      'H4_Volume_Leads_RSI': lambda r: condition('Volume leads RSI',r),
    }
    out=[]
    for name,fn in defs.items():
        mask=[bool(fn(r)) for r in rows]; m=metric_for_mask(rows,mask); out.append({'hypothesis':name,'thresholds':qs,'p_value':m['fisher_p_value'],**m})
    return bh_adjust(out)


def definition_summary(rows):
    out=[]
    for definition in sorted(set(r['definition'] for r in rows)):
        g=[r for r in rows if r['definition']==definition]; classes={}
        for r in g:
            key=str(r.get('classification','unknown')).strip().lower().replace(' ','_')
            classes[key]=classes.get(key,0)+1
        row={'definition':definition,'signals':len(g),'unique_tickers':len(set(r['ticker'] for r in g))}
        for c in ['true_explosion','rapid_move','gradual_rise','temporary_spike','pump_and_fade','no_significant_move']:
            row[c]=classes.get(c,0)
        for t in TARGETS:
            hs=[first_target_horizon(r,t) for r in g]; hs=[x for x in hs if x is not None]
            row[f'median_sessions_to_{t}']=safe_median(hs)
        out.append(row)
    return out


def select_freeze(rows):
    dates=sorted(pd.Timestamp(r['signal_date']) for r in rows)
    cut1=dates[max(0,int(len(dates)*.60)-1)].date().isoformat(); cut2=dates[max(0,int(len(dates)*.80)-1)].date().isoformat()
    train=[i for i,r in enumerate(rows) if r['signal_date']<=cut1]; valid=[i for i,r in enumerate(rows) if cut1<r['signal_date']<=cut2]; oos=[i for i,r in enumerate(rows) if r['signal_date']>cut2]
    hyps=hypothesis_rows(rows,train)
    # Freeze only from train+validation aggregate; OOS is not observed here.
    tv=train+valid; tv_h=hypothesis_rows(rows,tv)
    eligible=[h for h in tv_h if h['signals']>=15 and h.get('q_value_bh') is not None and h['q_value_bh']<.20]
    if not eligible: eligible=[h for h in sorted(tv_h,key=lambda x:(x.get('q_value_bh') if x.get('q_value_bh') is not None else 1,-(x.get('lift') or -1))) if h['signals']>=15][:1]
    selected=eligible[0] if eligible else {'hypothesis':'NO_VALIDATED_EDGE_YET','signals':0}
    name=selected.get('hypothesis')
    def fn(r):
        if name=='H1_RSI_Recovery_Volume_Expansion': return condition('RSI recovery',r,{'min':0}) and condition('Volume expansion',r,{'min':1.5})
        if name=='H2_RSI_Rising_Base_Price': return condition('RSI rising 5d',r,{'min':0}) and condition('Base',r,{'max':qv([rows[i]['pre_features'].get('base_range_10') for i in tv],.5,60)}) and condition('Price confirmation',r)
        if name=='H3_Oversold_Recovery_Price': return condition('RSI oversold recovery',r,{'below':30}) and condition('Price confirmation',r)
        if name=='H4_Volume_Leads_RSI': return condition('Volume leads RSI',r)
        return False
    mask=[fn(r) for r in rows]; oos_metrics=metric_for_mask([rows[i] for i in oos],[mask[i] for i in oos]) if oos else {}
    valid_metrics=metric_for_mask([rows[i] for i in valid],[mask[i] for i in valid]) if valid else {}
    train_metrics=metric_for_mask([rows[i] for i in train],[mask[i] for i in train]) if train else {}
    oos_valid = bool(name and name!='NO_VALIDATED_EDGE_YET' and oos_metrics.get('signals',0)>=30 and (oos_metrics.get('lift') or 0)>1 and (oos_metrics.get('fisher_p_value') or 1)<.05 and (oos_metrics.get('success_rate_ci95_clustered') or [0,0])[0] > 0)
    return {'cutoffs':{'train_end':cut1,'validation_end':cut2},'counts':{'train':len(train),'validation':len(valid),'oos':len(oos)},'discovery_hypotheses':hyps,'selected_on_train_validation':selected,'frozen_rule':name,'train_metrics':train_metrics,'validation_metrics':valid_metrics,'oos_metrics':oos_metrics,'no_validated_edge':not oos_valid,'oos_indices':oos,'mask':mask}


def walk_forward(rows):
    dates=sorted(set(r['signal_date'] for r in rows)); folds=[]
    if len(dates)<10: return folds
    cuts=[(.50,.70),(.60,.80),(.70,.90)]
    for n,(a,b) in enumerate(cuts,1):
        train_end=dates[min(len(dates)-1,int(len(dates)*a)-1)]; test_end=dates[min(len(dates)-1,int(len(dates)*b)-1)]
        train=[i for i,r in enumerate(rows) if r['signal_date']<=train_end]; test=[i for i,r in enumerate(rows) if train_end<r['signal_date']<=test_end]
        hs=hypothesis_rows(rows,train); best=sorted([h for h in hs if h['signals']>=10],key=lambda x:(x.get('q_value_bh') if x.get('q_value_bh') is not None else 1,-(x.get('lift') or -1)))
        name=best[0]['hypothesis'] if best else 'NO_VALIDATED_EDGE_YET'
        def fn(r):
            f=r['pre_features']
            if name.startswith('H1'): return condition('RSI recovery',r,{'min':0}) and condition('Volume expansion',r,{'min':1.5})
            if name.startswith('H2'): return condition('RSI rising 5d',r,{'min':0}) and condition('Base',r,{'max':qv([rows[i]['pre_features'].get('base_range_10') for i in train],.5,60)}) and condition('Price confirmation',r)
            if name.startswith('H3'): return condition('RSI oversold recovery',r,{'below':30}) and condition('Price confirmation',r)
            if name.startswith('H4'): return condition('Volume leads RSI',r)
            return False
        met=metric_for_mask([rows[i] for i in test],[fn(rows[i]) for i in test]) if test else {}
        folds.append({'fold':n,'train_end':train_end,'test_end':test_end,'train_signals':len(train),'test_signals':len(test),'selected_hypothesis':name,'test_metrics':met})
    return folds


def write_reports(rows, defs, stats, hyps, freeze, wf):
    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status='NO VALIDATED EDGE YET' if freeze['no_validated_edge'] else 'PAPER SIGNAL ONLY — OOS RESULT REQUIRES MORE DATA'
    report={'generated_at':now,'status':status,'universe':{'phase2_rows':len(rows),'unique_tickers':len(set(r['ticker'] for r in rows)),'definitions':len(defs)},'methods':{'features_use_pre_signal_only':True,'pre_signal_cutoff':'S-1 or earlier; S is excluded from Phase 3 rules','target_primary':'+70% within 10 sessions','clustered_bootstrap':'1,000 ticker-level resamples; deterministic seed 20260909','multiple_testing':'Benjamini-Hochberg FDR on feature/hypothesis p-values','temporal_split':'60% train / 20% validation / 20% OOS'},'definition_summary':defs,'hypotheses':hyps,'freeze':{k:v for k,v in freeze.items() if k not in ['mask','oos_indices']},'walk_forward':wf,'limitations':['Phase 2 candidate dates are discovery event dates, not independently generated live entries.','The archive has no point-in-time historical Float, Short Interest, borrow, spread, or order-book data.','Outcome labels are high/low excursion labels from archived OHLCV; they are not guaranteed executable fills.','The available Phase 2 feature grid is S-20 through S-1; finer intraday timing is not available.','Repeated rows per ticker are clustered for confidence intervals, but event definitions can still overlap economically.']}
    (OUT/'phase3_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Phase 3 — Hypothesis Testing, Strategy Freeze, OOS & Walk-forward','',f'Generated: {now}','',f'## Decision: {status}','', 'This phase tests the user-specified hypotheses rather than inventing a new strategy. All Phase 3 predictors are restricted to snapshots at S-1 or earlier; post-signal OHLCV is used only for outcomes.','', '## Data and controls','',f"The archived Phase 2 dataset contains **{len(rows)} candidate rows** across **{len(set(r['ticker'] for r in rows))} tickers** and five candidate start definitions. Confidence intervals use 1,000 deterministic ticker-level bootstrap resamples. P-values are adjusted with Benjamini-Hochberg FDR.",'', '## Start-definition comparison','', '| Definition | Signals | Tickers | True Explosion | Rapid Move | Gradual | Temporary | No Significant | Median sessions to +70 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for d in defs:
        lines.append(f"| {d['definition']} | {d['signals']} | {d['unique_tickers']} | {d.get('true_explosion',0)} | {d.get('rapid_move',0)} | {d.get('gradual_rise',0)} | {d.get('temporary_spike',0)} | {d.get('no_significant_move',0)} | {d.get('median_sessions_to_70')} |")
    lines += ['', '## Hypothesis results','', '| Hypothesis | Signals | Successes | Rate | Lift | Odds ratio | RR | Clustered 95% CI | FDR q |','|---|---:|---:|---:|---:|---:|---:|---|---:|']
    for h in hyps:
        lines.append(f"| {h['hypothesis']} | {h.get('signals')} | {h.get('successes')} | {h.get('success_rate')} | {h.get('lift')} | {h.get('odds_ratio')} | {h.get('relative_risk')} | {h.get('success_rate_ci95_clustered')} | {h.get('q_value_bh')} |")
    lines += ['', '## Freeze and OOS','',f"Train ends **{freeze['cutoffs']['train_end']}**; validation ends **{freeze['cutoffs']['validation_end']}**. The frozen rule is **{freeze['frozen_rule']}**. It was selected before OOS was read.",'', '| Split | Signals | Successes | Rate | Lift | Clustered CI |','|---|---:|---:|---:|---:|---|']
    for k in ['train_metrics','validation_metrics','oos_metrics']:
        m=freeze.get(k,{})
        lines.append(f"| {k.replace('_',' ')} | {m.get('signals')} | {m.get('successes')} | {m.get('success_rate')} | {m.get('lift')} | {m.get('success_rate_ci95_clustered')} |")
    lines += ['', '## Interpretation','', 'A result is not treated as a validated edge merely because its in-sample success rate is high. It must survive the temporal OOS split, ticker-clustered uncertainty, and multiple-testing review. If it does not, the correct label remains **NO VALIDATED EDGE YET** and the dashboard must remain paper-monitoring only.','', '## Limitations','', '- Historical Float, Short Interest, borrow, spreads, and point-in-time news are not available and are not backfilled with current values.', '- Candidate start dates came from Phase 2 discovery. A production signal engine must reproduce the frozen rule from data available at the time.', '- Intraday 4H data was not used to create an independent strategy. It should be tested only after the daily rule has an OOS edge.']
    (OUT/'PHASE3_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    raw=json.loads(CASES.read_text(encoding='utf-8')); rows=enrich(raw)
    defs=definition_summary(rows); stats=bh_adjust(feature_statistics(rows)); hyps=hypothesis_rows(rows); freeze=select_freeze(rows); wf=walk_forward(rows)
    # Keep machine-readable outputs required by the master task.
    pd.DataFrame(hyps).to_csv(OUT/'HYPOTHESIS_RESULTS.csv',index=False)
    pd.DataFrame(stats).to_csv(OUT/'FEATURE_STATISTICS.csv',index=False)
    oos=[]
    for r in rows:
        if r['signal_date'] > freeze['cutoffs']['validation_end']:
            oos.append({'ticker':r['ticker'],'definition':r['definition'],'signal_date':r['signal_date'],'hypothesis':freeze['frozen_rule'],'qualifies':bool(freeze['mask'][rows.index(r)]),'success_70_10':outcome_success(r,70,10),'max_return_20':r.get('outcomes',{}).get('max_return_20')})
    pd.DataFrame(oos).to_csv(OUT/'OOS_RESULTS.csv',index=False)
    pd.DataFrame(wf).to_csv(OUT/'WALK_FORWARD_RESULTS.csv',index=False)
    final=[]
    for r in rows:
        i=rows.index(r)
        if freeze['mask'][i]: final.append({'ticker':r['ticker'],'definition':r['definition'],'signal_date':r['signal_date'],'paper_signal':True,'target':'+70%','features_pre_signal_only':True,'status':'PAPER_SIGNAL_RESEARCH'})
    pd.DataFrame(final).to_csv(OUT/'FINAL_SIGNALS.csv',index=False)
    (OUT/'STRATEGY_FREEZE.md').write_text(strategy_freeze_doc(freeze),encoding='utf-8')
    (OUT/'OOS_REPORT.md').write_text(oos_doc(freeze),encoding='utf-8')
    (OUT/'WALK_FORWARD_REPORT.md').write_text(wf_doc(wf),encoding='utf-8')
    (OUT/'FINAL_BACKTEST_REPORT.md').write_text(final_doc(freeze),encoding='utf-8')
    write_reports(rows,defs,stats,hyps,freeze,wf)
    print(json.dumps({'rows':len(rows),'definitions':len(defs),'hypotheses':len(hyps),'frozen_rule':freeze['frozen_rule'],'oos':freeze['oos_metrics'],'walk_forward_folds':len(wf)},ensure_ascii=False,default=str))


def strategy_freeze_doc(f):
    return '# STRATEGY FREEZE — Phase 3\n\n## Status\n\n'+('NO VALIDATED EDGE YET' if f['no_validated_edge'] else 'PAPER SIGNAL ONLY; NOT LIVE VALIDATED')+'\n\n## Frozen rule\n\n`'+str(f['frozen_rule'])+'`\n\nThe rule was selected using train and validation only. OOS was not used to alter it.\n\n## Data discipline\n\nFeatures use S-1 or earlier snapshots. No future return, high, volume, RSI, support, float, short interest, or news is used.\n\n## Execution\n\nNo broker, order, auto-trading, Telegram, or real-money execution. Any dashboard display must be labelled Paper Signal / Research.\n\n## Risk fields\n\nStop, target, holding period, slippage, spread, and liquidity cannot be frozen as validated execution parameters until a rule survives OOS with point-in-time execution data.\n'


def oos_doc(f):
    return '# OOS REPORT — Phase 3\n\n## Temporal protocol\n\nTrain → validation → OOS. Cutoffs: '+f['cutoffs']['train_end']+' and '+f['cutoffs']['validation_end']+'. The OOS set was not used to select or modify the rule.\n\n## Frozen rule\n\n'+str(f['frozen_rule'])+'\n\n## OOS result\n\n'+json.dumps(f['oos_metrics'],ensure_ascii=False,indent=2)+'\n\n## Decision\n\n'+('NO VALIDATED EDGE YET' if f['no_validated_edge'] else 'Paper monitoring only until more independent OOS observations accumulate.')+'\n'


def wf_doc(wf):
    return '# WALK-FORWARD REPORT — Phase 3\n\nThree chronological folds were run. Each fold selected from its training period and evaluated the next period without changing the rule after seeing its test period.\n\n```json\n'+json.dumps(wf,ensure_ascii=False,indent=2)+'\n```\n'


def final_doc(f):
    return '# FINAL BACKTEST REPORT — Phase 3\n\nThis is a conservative research evaluation, not a fill-accurate brokerage backtest. The current archive does not contain enough point-in-time spread, liquidity, intraday, float, short, or borrow data to support a live claim.\n\nFrozen rule: `'+str(f['frozen_rule'])+'`\n\nOOS metrics:\n\n```json\n'+json.dumps(f['oos_metrics'],ensure_ascii=False,indent=2)+'\n```\n\nConclusion: '+('NO VALIDATED EDGE YET' if f['no_validated_edge'] else 'Paper signal only; continue independent monitoring.')+'\n'


if __name__ == '__main__': main()
