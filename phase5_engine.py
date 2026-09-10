# -*- coding: utf-8 -*-
"""Phase 5 blind validation gate.

This phase intentionally refuses to relabel Phase 3/4 OOS as blind data. It
freezes exactly three candidates and reports insufficient new OOS when the
current archive has no signal dates after the freeze boundary.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import pandas as pd
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'research'; CASES=OUT/'explosion_start_cases.json'

def success(r,t,h): return bool(r.get('outcomes',{}).get('targets',{}).get(str(h),{}).get(str(t),False))
def snap(r,k): return r.get('features',{}).get('snapshots',{}).get(k,{}) or {}
def feat(r):
    s1=snap(r,'S-1'); s10=snap(r,'S-10'); s3=snap(r,'S-3')
    r1=s1.get('rsi'); r10=s10.get('rsi'); v=s1.get('vr20'); c1=s1.get('close'); c3=s3.get('close')
    def f(x):
        try:return float(x)
        except:return None
    r1,r10,v,c1,c3=map(f,[r1,r10,v,c1,c3])
    return {'rsi_recovery':r1 is not None and r10 is not None and r1>r10,'volume_15':v is not None and v>=1.5,'volume_20':v is not None and v>=2,'price_confirmation':c1 is not None and c3 is not None and c1>c3}
def candidates(r):
    f=feat(r)
    return {'A_Volume_Ratio_20D_ge_2':f['volume_20'],'B_RSI_Recovery_plus_Volume_Expansion':f['rsi_recovery'] and f['volume_15'],'C_RSI_Volume_Price_Confirmation':f['rsi_recovery'] and f['volume_15'] and f['price_confirmation']}
def main():
    rows=json.loads(CASES.read_text(encoding='utf-8')); dataset_end=max(r['signal_date'] for r in rows if r.get('signal_date'))
    prior={}
    if (OUT/'phase5_report.json').exists():
        try: prior=json.loads((OUT/'phase5_report.json').read_text(encoding='utf-8'))
        except Exception: prior={}
    freeze_date=prior.get('freeze_date') or datetime.now(timezone.utc).date().isoformat(); requested_start=(datetime.strptime(dataset_end,'%Y-%m-%d').date()+timedelta(days=1)).isoformat()
    # A genuine blind period must be after the freeze, not merely after old Phase 4 validation.
    blind=[r for r in rows if r.get('signal_date','')>freeze_date]
    status='BLIND OOS READY' if blind else 'INSUFFICIENT NEW OOS DATA'
    names=['A_Volume_Ratio_20D_ge_2','B_RSI_Recovery_plus_Volume_Expansion','C_RSI_Volume_Price_Confirmation']
    result=[]
    for name in names:
        result.append({'candidate':name,'status':status,'signals':0,'plus20':0,'plus50':0,'plus70':0,'plus100':0,'plus200':0,'success_rate':None,'base_rate':None,'lift':None,'odds_ratio':None,'clustered_ci95':None,'p_value':None,'expectancy':None,'profit_factor':None,'walk_forward_stable':False})
    pd.DataFrame(result).to_csv(OUT/'PHASE5_RESULTS.csv',index=False)
    pd.DataFrame(result).to_csv(OUT/'PHASE5_FINAL_RESULTS.csv',index=False)
    pd.DataFrame([{'status':status,'clusters':0,'bootstrap_samples':0,'note':'No new post-freeze OOS rows; old OOS is not relabeled blind.'}]).to_csv(OUT/'PHASE5_CLUSTERED_BOOTSTRAP.csv',index=False)
    report={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'status':status,'freeze_date':freeze_date,'dataset_end_date':dataset_end,'requested_oos_start':requested_start,'blind_rows':len(blind),'candidates':names,'old_oos_not_reused':True,'reason':'The archived dataset ends before the Phase 5 freeze boundary; no new post-freeze signal/outcome rows are available.','next_step':'DATA COLLECTION PHASE — collect new US reverse-split OHLCV and outcomes after the freeze.'}
    (OUT/'phase5_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    write_docs(report)
    print(json.dumps(report,ensure_ascii=False))
def write_docs(r):
    freeze=f'''# PHASE 5 FREEZE\n\n## Status\n\nFROZEN — NO CONDITIONS MAY BE CHANGED AFTER THIS FILE.\n\n- Freeze Date: {r['freeze_date']}\n- Dataset End Date: {r['dataset_end_date']}\n- Requested Blind OOS Start: {r['requested_oos_start']}\n- Actual new post-freeze rows: {r['blind_rows']}\n\n## Candidates\n\n### Candidate A\nVolume Ratio 20D >= 2 at S-1.\n\n### Candidate B\nRSI at S-1 is higher than RSI at S-10, plus Volume Ratio 20D >= 1.5 at S-1.\n\n### Candidate C\nCandidate B plus Close(S-1) > Close(S-3).\n\n## Fixed definitions\n\n- Universe: US Reverse Split candidates only.\n- Start-of-Explosion: use the existing archived Phase 2 candidate event definitions; do not select a new definition during Phase 5.\n- Success: outcome reaches +20%, +50%, +70%, +100%, or +200% at 1, 3, 5, 10, or 20 sessions.\n- Look-ahead rule: predictors use S-1 or earlier only.\n- No new Support, MACD, MA, Float, Short, News, or Liquidity Sweep conditions.\n- No stop, target, or holding period is selected from this OOS.\n\n## Blind gate\n\n{r['status']}. The old Phase 3/4 OOS is not reused as blind data.\n'''
    (OUT/'PHASE5_FREEZE.md').write_text(freeze,encoding='utf-8')
    report=f'''# PHASE 5 REPORT — Blind OOS Validation\n\n## Decision\n\n**{r['status']}**\n\nPhase 5 froze Candidates A, B, and C before checking for new post-freeze outcomes. The archive ends on **{r['dataset_end_date']}**, while the freeze boundary is **{r['freeze_date']}**. There are **{r['blind_rows']}** new post-freeze rows.\n\nThe prior Phase 3/4 OOS is deliberately not relabeled as Blind OOS. No candidate is accepted or rejected from the absence of new data.\n\n## Correct next step\n\n**DATA COLLECTION PHASE.** Collect a new US Reverse Split universe after the freeze, preserve full daily OHLCV before and after each signal, and rerun the three frozen candidates without changing their definitions.\n\n## Interpretation\n\nThere is no evidence of Look-ahead in this gate because no new result was calculated. There is also no claim of validation. Candidate A remains the best prior research candidate, but it is still **NOT VALIDATED** until it survives genuinely new blind data.\n'''
    (OUT/'PHASE5_REPORT.md').write_text(report,encoding='utf-8')
    (OUT/'PHASE5_OOS_RESULTS.md').write_text('# PHASE 5 OOS RESULTS\n\nStatus: **'+r['status']+'**\n\nNo post-freeze OOS rows are available. Previous OOS results are excluded from this report because they were visible during hypothesis development.\n',encoding='utf-8')
    (OUT/'PHASE5_WALK_FORWARD.md').write_text('# PHASE 5 WALK-FORWARD\n\nNot run. A blind OOS period with new post-freeze data is required before a fixed walk-forward assessment can be made.\n',encoding='utf-8')
if __name__=='__main__': main()
