from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from pipeline import load_data,filter_data,sensor_diagnostics,weekly,fit_evaluate

st.set_page_config(page_title='Burning Season Explorer',layout='wide')
st.title('Burning Season Explorer')
st.caption('NASA FIRMS · Punjab–Haryana study rectangle · September–November, 2023–2025')
st.info('Historical planning prototype. The rectangle includes neighboring areas. Hotspots are detections, not unique fires or confirmed crop-residue burning. No AQI or fire forecasts are produced.')
@st.cache_data
def get_data(): return load_data()
raw=get_data()
quality=st.sidebar.checkbox('Filter low-confidence and non-vegetation detections',value=True)
d=filter_data(raw,quality)
w=weekly(d)
factor,metrics,test=fit_evaluate(w)
view=st.sidebar.radio('Calendar measure',['Raw MODIS','Raw VIIRS','Experimental MODIS-reference activity estimate'])
year=st.sidebar.selectbox('Map year',[2025,2024,2023])
months=st.sidebar.multiselect('Map months',[9,10,11],default=[9,10,11])
st.sidebar.caption('The model is fitted only on 2023–2024. Its factor remains fixed when changing map filters.')
a,b,c=st.columns(3)
a.metric('MODIS detections after filters',f'{len(d[d.sensor=="MODIS"]):,}')
b.metric('VIIRS detections after filters',f'{len(d[d.sensor=="VIIRS"]):,}')
c.metric('Experimental reference-scale factor',f'{factor:.3f}')

cal=w[w.sensor.eq('MODIS' if view=='Raw MODIS' else 'VIIRS')].copy()
cal['activity']=cal['count']*(factor if view.startswith('Experimental') else 1)
heat=cal.pivot(index='year',columns='week',values='activity')
adjusted=view.startswith('Experimental')
measure_label=view if adjusted else f'{view} hotspot detections'
value_label='MODIS-reference estimate' if adjusted else 'Hotspot detections'
date_labels=[]
hover_data=[]
for week in heat.columns:
    example_start=pd.Timestamp(2023,9,1)+pd.Timedelta((int(week)-1)*7,unit='D')
    date_labels.append(f'{example_start:%b} {example_start.day}')
for year in heat.index:
    row=[]
    for week in heat.columns:
        start=pd.Timestamp(int(year),9,1)+pd.Timedelta((int(week)-1)*7,unit='D')
        end=start+pd.Timedelta(6,unit='D')
        date_range=f'{start:%b} {start.day}–{end:%b} {end.day}, {year}'
        row.append([str(year),date_range,measure_label])
    hover_data.append(row)
calendar_heading,calendar_note=st.columns([2,1])
calendar_heading.subheader(f'Burning calendar — {measure_label}')
if adjusted:
    calendar_note.caption('Experimental calibration; differences in satellite observation times affect comparability. See sensor diagnostics below.')
fig=px.imshow(heat,x=date_labels,y=[str(year) for year in heat.index],labels={'x':'Week starting','y':'Year','color':value_label},color_continuous_scale='Cividis',aspect='auto')
fig.update_traces(customdata=hover_data,hovertemplate=f'Year: %{{customdata[0]}}<br>Date range: %{{customdata[1]}}<br>Measure: %{{customdata[2]}}<br>{value_label}: %{{z:{".1f" if adjusted else ".0f"}}}<extra></extra>')
fig.update_yaxes(type='category')
st.plotly_chart(fig,width='stretch')
st.caption('13 consecutive seven-day bins cover September 1–November 30. Zero means no recorded detections in this export, not a confirmed observed zero. Experimental MODIS-reference activity estimates are not actual observed counts.')
st.subheader('Hotspot locations')
map_sensor=st.radio('Map sensor',['VIIRS','MODIS'],horizontal=True)
s=d[(d.date.dt.year==year)&d.date.dt.month.isin(months)&d.sensor.eq(map_sensor)]
if len(s):
    points=s.sample(min(15000,len(s)),random_state=42)
    st.map(points.rename(columns={'latitude':'lat','longitude':'lon'})[['lat','lon']],zoom=6)
    st.caption(f'{len(s):,} filtered detections; at most 15,000 displayed for performance.')
else: st.warning('No recorded detections for this selection.')
st.download_button('Download selected hotspot CSV',s.drop(columns=['date']).to_csv(index=False),'selected_hotspots.csv','text/csv')
st.subheader('Raw and experimental weekly comparison')
plot=w.copy();adj=w[w.sensor.eq('VIIRS')].copy();adj['count']*=factor;adj['sensor']='Experimental MODIS-reference activity estimate'
plot=pd.concat([plot,adj])
st.plotly_chart(px.line(plot,x='week',y='count',color='sensor',facet_row='year',labels={'week':'Season week','count':'Detections / reference-scale estimate'},height=650),width='stretch')
st.subheader('Held-out evaluation: 2025')
st.write('Non-negative least-squares scaling through the origin, trained on 26 weekly pairs from 2023–2024. MODIS is a reference sensor, not ground truth. A lower error demonstrates numerical agreement only.')
st.dataframe(pd.DataFrame({'Baseline':['Unadjusted VIIRS','Experimental MODIS-reference activity estimate','Training total-ratio scale','Training mean MODIS'],'2025 weekly MAE':[metrics['raw_mae'],metrics['adjusted_mae'],metrics['training_total_ratio_mae'],metrics['training_mean_mae']]}),hide_index=True)
st.caption('MAE measures absolute disagreement with MODIS. The simple scale does not correct spatial resolution, overpass time, missed small fires, clouds, or changing detection efficiency. It is an experimental baseline, not validated sensor-independent harmonization.')
st.download_button('Download weekly analytics CSV',w.assign(experimental_modis_reference_activity_estimate=lambda t:t['count'].where(t.sensor.eq('VIIRS'))*factor).to_csv(index=False),'weekly_analytics.csv','text/csv')

with st.expander('Sensor comparability diagnostics'):
    st.write('These are detection-based diagnostics from the selected quality-filter setting—not satellite observation coverage. They describe retained hotspot records only.')
    composition,timing=sensor_diagnostics(d)
    left,right=st.columns(2)
    left.caption('Satellite composition of retained detections')
    left.dataframe(composition.rename(columns={
        'year':'Year','sensor':'Sensor','satellite':'Satellite','detections':'Detections',
        'sensor_share_pct':'Share within sensor (%)'
    }),hide_index=True,width='stretch')
    right.caption('Detection-weighted daytime acquisition times')
    right.dataframe(timing.rename(columns={
        'year':'Year','satellite':'Satellite','detections':'Daytime detections',
        'median_utc':'Median UTC','approx_median_ist':'Approx. median IST'
    }),hide_index=True,width='stretch')
    st.warning('Aqua MODIS acquisition times shift later across these seasons while SNPP VIIRS times are more stable. Changing time separation confounds count comparisons because fire activity, cloud, and detectability can change between passes.')
    st.caption('The FIRMS hotspot exports do not supply observation opportunities or clear-sky masks. An unmatched or missing observation is therefore unknown and must remain distinct from a confirmed observed zero.')

with st.expander('Methodology and sources'):
    st.markdown('''**Use:** inspect repeated seasonal peaks to guide the timing of outreach and residue-management preparation. No operational prioritization or causal pollution attribution is inferred.

**Quality filters:** MODIS confidence ≥30; VIIRS nominal/high; type 0 for both. These thresholds are a prototype choice and are not equivalent between sensors. Type 0 does not establish agricultural burning. Disable the filter to inspect sensitivity.

**Geography:** 73.7–77.8° E, 27.5–32.7° N. No state-boundary clipping or cropland mask is applied.

**Sensor comparability:** the satellite and acquisition-time tables are detection-based diagnostics, not observation coverage. Changing acquisition times confound sensor comparison. Missing or unmatched observations remain unknown rather than confirmed zeros.

**Limits:** only three autumn seasons; predominantly Aqua MODIS detections; SNPP-only VIIRS; no non-detection, clear-sky, or observation masks; repeated observations may capture the same event. No multi-decade calendar, significance claim, or forecast.

**Next steps:** evaluate spatial aggregation and matched-overpass comparisons, obtain observation coverage, add longer historical records and land-cover masks, and validate the workflow with intended users.

**Source:** [NASA FIRMS Archive Download](https://firms.modaps.eosdis.nasa.gov/download/). Six original exports are included unchanged in data/raw/.''')
    st.dataframe(raw.groupby([raw.date.dt.year.rename('year'),'sensor','satellite']).size().rename('detections').reset_index(),hide_index=True)
