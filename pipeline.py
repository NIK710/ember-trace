from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
SUPPORTED_SATELLITES = {
    'Aqua': 'MODIS',
    'Terra': 'MODIS',
    'SNPP': 'VIIRS',
}

def load_data():
    frames=[]
    for p in sorted((ROOT/'data/raw').glob('*.csv')):
        d=pd.read_csv(p)
        d['source_file']=p.name
        unknown=sorted(set(d.satellite.dropna())-set(SUPPORTED_SATELLITES))
        if d.satellite.isna().any() or unknown:
            values=unknown+(['<missing>'] if d.satellite.isna().any() else [])
            raise ValueError(f'Unsupported satellite value(s) in {p.name}: {values}')
        d['sensor']=d.satellite.map(SUPPORTED_SATELLITES)
        d['date']=pd.to_datetime(d.acq_date)
        frames.append(d)
    if not frames: raise ValueError('No CSV files found in data/raw')
    return pd.concat(frames,ignore_index=True).drop_duplicates(subset=['source_file','latitude','longitude','acq_date','acq_time','satellite'])

def filter_data(raw, quality=True):
    d=raw[raw.longitude.between(73.7,77.8)&raw.latitude.between(27.5,32.7)&raw.date.dt.month.between(9,11)].copy()
    if quality:
        # Deliberate prototype filters; these are NOT equivalent confidence thresholds.
        good=np.where(d.sensor.eq('MODIS'),pd.to_numeric(d.confidence,errors='coerce').ge(30),d.confidence.astype(str).isin(['n','h']))
        d=d[good & d.type.eq(0)]
    return d

def sensor_diagnostics(d):
    """Detection-based composition and acquisition-time summaries, not coverage."""
    x=d.copy()
    x['year']=x.date.dt.year
    composition=(x.groupby(['year','sensor','satellite']).size().rename('detections').reset_index())
    totals=composition.groupby(['year','sensor']).detections.transform('sum')
    composition['sensor_share_pct']=(100*composition.detections/totals).round(1)

    daytime=x[x.daynight.eq('D')].copy()
    hh=pd.to_numeric(daytime.acq_time,errors='coerce')//100
    mm=pd.to_numeric(daytime.acq_time,errors='coerce')%100
    daytime['acq_minute_utc']=hh*60+mm
    timing=(daytime.groupby(['year','satellite']).agg(
        detections=('date','size'),median_minute_utc=('acq_minute_utc','median')
    ).reset_index())

    def clock(minutes):
        minutes=int(round(minutes))%1440
        return f'{minutes//60:02d}:{minutes%60:02d}'
    timing['median_utc']=timing.median_minute_utc.map(clock)
    timing['approx_median_ist']=(timing.median_minute_utc+330).map(clock)
    return composition,timing.drop(columns='median_minute_utc')

def weekly(d,years=(2023,2024,2025)):
    # Fixed seven-day bins anchored on September 1, not shifting ISO weeks.
    rows=[]
    for year in years:
        base=pd.Timestamp(year,9,1)
        for sensor in ['MODIS','VIIRS']:
            s=d[(d.date.dt.year==year)&(d.sensor==sensor)].copy()
            counts=((s.date-base).dt.days//7).value_counts()
            for w in range(13):
                rows.append({'year':year,'week':w+1,'week_start':base+pd.Timedelta(int(w)*7,unit='D'),'sensor':sensor,'count':int(counts.get(w,0))})
    return pd.DataFrame(rows)

def fit_evaluate(w):
    pairs=w.pivot(index=['year','week'],columns='sensor',values='count').reset_index()
    train=pairs[pairs.year.isin([2023,2024])]
    test=pairs[pairs.year.eq(2025)].copy()
    x=train.VIIRS.to_numpy(float);y=train.MODIS.to_numpy(float)
    # Non-negative least-squares scale through the origin; no holdout fitting.
    factor=float(np.dot(x,y)/np.dot(x,x)) if np.dot(x,x)>0 else 0.0
    test['experimental_modis_reference_activity_estimate']=test.VIIRS*factor
    mae=lambda a,b:float(np.abs(np.asarray(a)-np.asarray(b)).mean())
    ratio=float(y.sum()/x.sum()) if x.sum() else 0.0
    metrics={'fit_years':[2023,2024],'evaluation_year':2025,'factor':factor,'raw_mae':mae(test.VIIRS,test.MODIS),'adjusted_mae':mae(test.experimental_modis_reference_activity_estimate,test.MODIS),'training_total_ratio_mae':mae(test.VIIRS*ratio,test.MODIS),'training_mean_mae':mae(np.full(len(test),y.mean()),test.MODIS),'units':'MODIS-reference detections per seven-day bin; not unique fires'}
    return factor,metrics,test

if __name__=='__main__':
    out=ROOT/'data/processed';out.mkdir(parents=True,exist_ok=True)
    raw=load_data();d=filter_data(raw);w=weekly(d)
    f,m,t=fit_evaluate(w)
    w.to_csv(out/'weekly.csv',index=False);t.to_csv(out/'evaluation_2025.csv',index=False)
    (out/'evaluation.json').write_text(json.dumps(m,indent=2))
    raw.groupby([raw.date.dt.year,'sensor']).size().to_csv(out/'raw_counts.csv')
    print(json.dumps(m,indent=2))
