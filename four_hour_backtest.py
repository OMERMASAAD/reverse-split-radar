# -*- coding: utf-8 -*-
"""4-hour entry backtest for post-reverse-split +70% trades.

Signal uses only completed bars before entry: prior drawdown, base range,
breakout above the prior 3-bar high, and volume/range expansion. Entry is the
next 4h bar open. Target is +70% from that entry within 30 bars (~5 sessions).
"""
from __future__ import annotations
import json, time
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

CANDIDATES='reverse_split_candidates.json'
OUT='four_hour_backtest.json'


def get4h(ticker, split_date):
    try:
        start=pd.Timestamp(split_date)-pd.Timedelta(days=2)
        end=pd.Timestamp(split_date)+pd.Timedelta(days=65)
        x=yf.Ticker(ticker).history(start=start,end=end,interval='4h',auto_adjust=False,actions=False)
        if x is None or x.empty: return None
        if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
        x.index=pd.to_datetime(x.index).tz_localize(None)
        return x.sort_index()
    except Exception:
        return None


def signals(x, split, variant):
    x=x[x.index>=pd.Timestamp(split)].copy()
    if len(x)<40:return []
    x['range_pct']=(x.High/x.Low-1)*100
    x['ret']=x.Close.pct_change()*100
    x['vol_ratio']=x.Volume/x.Volume.rolling(12,min_periods=6).mean().shift(1)
    out=[]
    for i in range(12,len(x)-30):
        prior=x.iloc[i-6:i]
        bar=x.iloc[i]
        peak=float(prior.High.max()); low=float(prior.Low.min())
        drawdown=(low/peak-1)*100 if peak else 0
        base=(peak/low-1)*100 if low else 999
        breakout=float(bar.Close)>float(x.High.iloc[i-3:i].max())
        expansion=(float(bar.vol_ratio)>=variant['vol']) or (float(bar.range_pct)>=variant['range'])
        ok=(drawdown<=-variant['drawdown'] and base<=variant['base'] and breakout and expansion and float(bar.Close)>float(bar.Open))
        if not ok: continue
        entry=x.iloc[i+1]
        entry_price=float(entry.Open)
        # One trading day is represented conservatively by the next six
        # four-hour bars; this intentionally measures the fast spike target.
        future=x.iloc[i+1:i+7]
        target=entry_price*1.70
        hit=future.High>=target
        hit_i=int(np.argmax(hit.values)) if hit.any() else None
        max_high=float(future.High.max()) if not future.empty else None
        max_gain=(max_high/entry_price-1)*100 if entry_price else None
        min_low=float(future.Low.min()) if not future.empty else None
        max_dd=(min_low/entry_price-1)*100 if entry_price else None
        out.append({'signal_time':x.index[i].isoformat(),'entry_time':future.index[0].isoformat(),'entry_price':entry_price,'signal_close':float(bar.Close),'signal_volume_ratio':float(bar.vol_ratio),'signal_range_percent':float(bar.range_pct),'prior_drawdown_percent':drawdown,'prior_base_range_percent':base,'target_price':target,'target_hit':bool(hit.any()),'bars_to_target':hit_i+1 if hit_i is not None else None,'max_gain_percent':max_gain,'max_drawdown_percent':max_dd})
    return out


def main():
    c=json.loads(Path(CANDIDATES).read_text(encoding='utf-8'))
    variants={'moderate':{'drawdown':25,'base':35,'vol':1.0,'range':5},'balanced':{'drawdown':30,'base':30,'vol':1.15,'range':6},'strict':{'drawdown':35,'base':25,'vol':1.3,'range':8}}
    cases=[]; unavailable=[]
    for n,row in enumerate(c,1):
        ticker=row['ticker']; print(f'[{n}/{len(c)}] {ticker}',flush=True)
        x=get4h(ticker,row['split_date'])
        if x is None: unavailable.append({'ticker':ticker,'reason':'no_4h_data'}); continue
        for name,v in variants.items():
            for s in signals(x,row['split_date'],v):
                cases.append({'ticker':ticker,'split_date':row['split_date'],'variant':name,**s})
    summary={}
    for v in variants:
        z=[r for r in cases if r['variant']==v]
        summary[v]={'signals':len(z),'unique_tickers':len({r['ticker'] for r in z}),'wins_70':sum(r['target_hit'] for r in z),'win_rate_percent':round(sum(r['target_hit'] for r in z)/len(z)*100,2) if z else None,'median_bars_to_target':float(np.median([r['bars_to_target'] for r in z if r['bars_to_target'] is not None])) if any(r['bars_to_target'] is not None for r in z) else None,'median_max_gain_percent':float(np.median([r['max_gain_percent'] for r in z])) if z else None,'median_max_drawdown_percent':float(np.median([r['max_drawdown_percent'] for r in z])) if z else None}
    out={'generated_at':datetime.utcnow().isoformat()+'Z','methodology':{'entry':'next 4h candle open after completed signal candle','target':'+70% from actual entry','horizon':'6 four-hour bars (~1 trading day)','lookahead_control':'features use bars before signal; outcome uses only future bars','important_limit':'Yahoo 4h historical availability is limited; unavailable tickers are reported'},'universe':{'candidates':len(c),'with_4h_data':len(c)-len(unavailable),'unavailable':unavailable},'variants':summary,'trades':cases}
    Path(OUT).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'universe':out['universe'],'variants':summary},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
