#!/usr/bin/env python
from __future__ import annotations
import argparse, json, re, shutil, uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_311_ROOT = PROJECT_ROOT / 'data' / 'raw' / 'complaints_311' / 'year=2025'
SILVER_311_ROOT = PROJECT_ROOT / 'data' / 'silver' / 'complaints_311' / 'year=2025'
PROFILE_SUMMARY = PROJECT_ROOT / 'reports' / 'profiling' / '311_profile_summary.json'
RECONCILIATION_REPORT = PROJECT_ROOT / 'reports' / 'reconciliation' / '311_silver_reconciliation.csv'
RUN_LOG = PROJECT_ROOT / 'logs' / 'pipeline_runs.jsonl'
EXPECTED_FULL_YEAR_RAW_ROWS = 3_655_040
EXPECTED_FULL_YEAR_REJECTED_ROWS = 50_979
EXPECTED_FULL_YEAR_SILVER_ROWS = 3_604_061
SOURCE_FIELDS = ['unique_key','created_date','closed_date','complaint_type','agency','borough','latitude','longitude','incident_address','status','resolution_description']
BOROUGH_MAP = {'BRONX':'Bronx','BROOKLYN':'Brooklyn','MANHATTAN':'Manhattan','QUEENS':'Queens','STATEN ISLAND':'Staten Island','UNSPECIFIED':'Unspecified'}
COMPLAINT_CANONICAL = {'plumbing':'Plumbing','elevator':'Elevator','asbestos':'Asbestos'}
SILVER_SCHEMA = pa.schema([
    pa.field('unique_key', pa.string()),
    pa.field('created_at', pa.timestamp('us')),
    pa.field('created_date', pa.date32()),
    pa.field('created_time', pa.string()),
    pa.field('closed_at', pa.timestamp('us')),
    pa.field('closed_date', pa.date32()),
    pa.field('complaint_type', pa.string()),
    pa.field('agency', pa.string()),
    pa.field('borough', pa.string()),
    pa.field('latitude', pa.float64()),
    pa.field('longitude', pa.float64()),
    pa.field('address', pa.string()),
    pa.field('status', pa.string()),
    pa.field('resolution_description', pa.string()),
    pa.field('is_long_resolution', pa.bool_(), nullable=False),
    pa.field('_source', pa.string(), nullable=False),
    pa.field('_source_file', pa.string(), nullable=False),
    pa.field('_run_id', pa.string(), nullable=False),
    pa.field('_processed_at', pa.timestamp('us'), nullable=False),
    pa.field('_processing_year', pa.int32(), nullable=False),
    pa.field('_processing_month', pa.int32(), nullable=False),
])

def clean_text(value):
    if value is None: return None
    text = re.sub(r'\s+', ' ', str(value)).strip()
    return text or None

def normalize_borough(value):
    text = clean_text(value)
    return None if text is None else BOROUGH_MAP.get(text.upper(), text)

def normalize_agency(value):
    text = clean_text(value)
    return None if text is None else text.upper()

def normalize_complaint(value):
    text = clean_text(value)
    return None if text is None else COMPLAINT_CANONICAL.get(text.casefold(), text)

def load_profile_contract():
    with PROFILE_SUMMARY.open('r', encoding='utf-8') as f: profile = json.load(f)
    if profile.get('row_count') != EXPECTED_FULL_YEAR_RAW_ROWS:
        raise RuntimeError(f"PROFILE_CONTRACT_FAILURE: expected {EXPECTED_FULL_YEAR_RAW_ROWS:,}, found {profile.get('row_count')!r}")
    if profile.get('duplicate_unique_key_rows') != 0:
        raise RuntimeError('DUPLICATE_CONTRACT_CHANGED: Phase 6 no longer reports zero duplicate unique_key rows.')
    return profile

def load_json_rows(path):
    with path.open('r', encoding='utf-8') as f: payload = json.load(f)
    if isinstance(payload, list): return payload
    if isinstance(payload, dict) and isinstance(payload.get('data'), list): return payload['data']
    raise RuntimeError(f'Unsupported 311 JSON payload structure: {path}')

def standardize_and_filter(df, source_file, run_id, processed_at, month):
    created_at = pd.to_datetime(df['created_date'], errors='coerce')
    closed_at = pd.to_datetime(df['closed_date'], errors='coerce')
    latitude = pd.to_numeric(df['latitude'], errors='coerce')
    longitude = pd.to_numeric(df['longitude'], errors='coerce')
    r1 = created_at.isna()
    r2 = created_at.notna() & ((created_at < pd.Timestamp('2025-01-01')) | (created_at >= pd.Timestamp('2026-01-01')))
    r3 = closed_at.notna() & created_at.notna() & (closed_at < created_at)
    r5 = latitude.isna() | longitude.isna()
    r6 = (latitude.notna() & ~latitude.between(-90,90)) | (longitude.notna() & ~longitude.between(-180,180))
    reject = r1 | r2 | r3 | r5 | r6
    reasons = {'dq_311_001_created_invalid':int(r1.sum()),'dq_311_002_created_outside_2025':int(r2.sum()),'dq_311_003_closed_before_created':int(r3.sum()),'dq_311_005_missing_coordinates':int(r5.sum()),'dq_311_006_invalid_coordinate_range':int(r6.sum())}
    valid = df.loc[~reject].copy(); vc = created_at.loc[~reject]; vcl = closed_at.loc[~reject]
    vlat = latitude.loc[~reject].astype('float64'); vlon = longitude.loc[~reject].astype('float64')
    duration_days = (vcl - vc).dt.total_seconds()/86400.0
    long_flag = (vcl.notna() & (duration_days > 365.0)).astype(bool)
    out = pd.DataFrame({
        'unique_key':valid['unique_key'].map(clean_text),
        'created_at':vc,
        'created_date':vc.dt.date,
        'created_time':vc.dt.strftime('%H:%M:%S'),
        'closed_at':vcl,
        'closed_date':vcl.dt.date,
        'complaint_type':valid['complaint_type'].map(normalize_complaint),
        'agency':valid['agency'].map(normalize_agency),
        'borough':valid['borough'].map(normalize_borough),
        'latitude':vlat,'longitude':vlon,
        'address':valid['incident_address'].map(clean_text),
        'status':valid['status'].map(clean_text),
        'resolution_description':valid['resolution_description'].map(clean_text),
        'is_long_resolution':long_flag,
        '_source':'nyc_311','_source_file':source_file.resolve().as_uri(),
        '_run_id':run_id,'_processed_at':processed_at,
        '_processing_year':2025,'_processing_month':month,
    })
    if out['created_at'].isna().any() or out['latitude'].isna().any() or out['longitude'].isna().any():
        raise RuntimeError('SILVER_CONTRACT_FAILURE: required fields invalid after filtering')
    table = pa.Table.from_pandas(out, schema=SILVER_SCHEMA, preserve_index=False, safe=False)
    return table, reasons, int(reject.sum()), int(long_flag.sum())

def write_run_log(record):
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open('a', encoding='utf-8') as f: f.write(json.dumps(record, default=str)+'\n')

def update_report(rows):
    RECONCILIATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    if RECONCILIATION_REPORT.exists():
        old = pd.read_csv(RECONCILIATION_REPORT, dtype={'processing_month':str})
        old = old[~old['processing_month'].astype(str).isin(set(new['processing_month'].astype(str)))]
        new = pd.concat([old,new], ignore_index=True)
    new.sort_values('processing_month').to_csv(RECONCILIATION_REPORT, index=False)

def process_month(month):
    mt=f'{month:02d}'; src=RAW_311_ROOT/f'month={mt}'; outdir=SILVER_311_ROOT/f'month={mt}'
    files=sorted(src.glob('*.json'))
    if not files: raise FileNotFoundError(f'No Raw 311 JSON files found: {src}')
    run_id=str(uuid.uuid4()); processed_at=datetime.now(timezone.utc).replace(tzinfo=None); started=datetime.now(timezone.utc)
    print('\n'+'='*78); print(f'PHASE 10 - NYC 311 SILVER - 2025-{mt}'); print('='*78); print(f'Raw JSON files: {len(files)}'); print(f'Output: {outdir}'); print(f'Run ID: {run_id}')
    if outdir.exists(): shutil.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    raw=silver=rejected=longs=0; reason_totals={k:0 for k in ['dq_311_001_created_invalid','dq_311_002_created_outside_2025','dq_311_003_closed_before_created','dq_311_005_missing_coordinates','dq_311_006_invalid_coordinate_range']}; written=0
    try:
        for i,p in enumerate(files):
            rows=load_json_rows(p); raw+=len(rows); df=pd.DataFrame.from_records(rows, columns=SOURCE_FIELDS)
            table,reasons,rej,long_count=standardize_and_filter(df,p,run_id,processed_at,month)
            for k,v in reasons.items(): reason_totals[k]+=v
            rejected+=rej; longs+=long_count; silver+=table.num_rows
            if table.num_rows:
                op=outdir/f"part-{i:05d}-{run_id.replace('-','')}.parquet"; pq.write_table(table,op,compression='snappy'); written+=1
            print(f'[{i+1}/{len(files)}] {p.name}: raw={len(rows):,}, rejected={rej:,}, silver={table.num_rows:,}')
        verified=sum(pq.ParquetFile(p).metadata.num_rows for p in sorted(outdir.glob('*.parquet')))
        if raw-rejected!=silver: raise RuntimeError(f'ROW_RECONCILIATION_FAILURE: Raw={raw:,}, Rejected={rejected:,}, Silver={silver:,}')
        if verified!=silver: raise RuntimeError(f'PARQUET_RECONCILIATION_FAILURE: expected {silver:,}, verified {verified:,}')
        result={'run_id':run_id,'processing_month':f'2025-{mt}','raw_rows':raw,'silver_rows':silver,'rows_rejected':rejected,**reason_totals,'flag_long_resolution_rows':longs,'status':'SUCCESS'}
        write_run_log({'phase':10,'pipeline':'311_silver',**result,'started_at':started.isoformat(),'finished_at':datetime.now(timezone.utc).isoformat(),'output_file_count':written})
        print(f'Raw rows: {raw:,}'); print(f'Rejected distinct rows: {rejected:,}'); print(f'Silver rows: {silver:,}'); print(f'Long-resolution rows flagged: {longs:,}'); print(f'Verified Silver rows: {verified:,}'); print(f'Silver Parquet files: {written}'); print('Reconciliation: SUCCESS'); print(f'2025-{mt}: SILVER SUCCESS')
        return result
    except Exception as exc:
        write_run_log({'phase':10,'pipeline':'311_silver','run_id':run_id,'processing_month':f'2025-{mt}','started_at':started.isoformat(),'finished_at':datetime.now(timezone.utc).isoformat(),'status':'FAILED','error_message':str(exc)})
        print(f'2025-{mt}: SILVER FAILED'); print(f'Error: {exc}'); raise

def main():
    ap=argparse.ArgumentParser(description='Prepare analysis-ready NYC 311 Silver data for Phase 10.')
    ap.add_argument('--months',nargs='+',type=int,default=list(range(1,13)))
    args=ap.parse_args()
    if any(m<1 or m>12 for m in args.months): raise ValueError(f'Invalid months: {args.months}')
    profile=load_profile_contract()
    print('='*78); print('PHASE 10 - NYC 311 DATA PREPARATION'); print('='*78); print(f"Phase 6 Raw rows: {profile['row_count']:,}"); print('Proven-invalid records: EXCLUDED FROM SILVER'); print('DQ_311_007 long resolution: FLAG AND RETAIN'); print('Complaint normalization: only evidenced case-only collisions are merged'); print('Agency normalization: trim + uppercase'); print('Borough normalization: canonical NYC borough labels')
    results=[process_month(m) for m in args.months]; update_report(results)
    raw=sum(r['raw_rows'] for r in results); rej=sum(r['rows_rejected'] for r in results); silver=sum(r['silver_rows'] for r in results)
    print('\n'+'='*78); print('PHASE 10 RUN SUMMARY'); print('='*78); print('Months processed:',', '.join(f'{m:02d}' for m in args.months)); print(f'Raw rows: {raw:,}'); print(f'Rejected rows: {rej:,}'); print(f'Silver rows: {silver:,}'); print(f'Reconciliation report: {RECONCILIATION_REPORT}')
    if sorted(set(args.months))==list(range(1,13)):
        if raw!=EXPECTED_FULL_YEAR_RAW_ROWS: raise RuntimeError(f'FULL_YEAR_RAW_FAILURE: expected {EXPECTED_FULL_YEAR_RAW_ROWS:,}, found {raw:,}')
        if rej!=EXPECTED_FULL_YEAR_REJECTED_ROWS: raise RuntimeError(f'FULL_YEAR_REJECTION_FAILURE: expected {EXPECTED_FULL_YEAR_REJECTED_ROWS:,}, found {rej:,}')
        if silver!=EXPECTED_FULL_YEAR_SILVER_ROWS: raise RuntimeError(f'FULL_YEAR_SILVER_FAILURE: expected {EXPECTED_FULL_YEAR_SILVER_ROWS:,}, found {silver:,}')
        print('Full-year reconciliation target: PASS')
    print('\nPHASE 10 NYC 311 SILVER BUILD: SUCCESS')

if __name__=='__main__': main()
