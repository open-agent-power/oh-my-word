"""Score frozen public predictions without giving gold to the generator.

Label accuracy and literal quote matching are mechanical metrics; neither proves
professional quality or semantic entailment of every generated statement.
"""
from __future__ import annotations
import argparse,csv,json,re,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from evals.public_data.cmrc_metric import calc_em_score,calc_f1_score

LABELS = re.compile(r"\b(?:NOT_ENOUGH_INFO|CONTRADICT|SUPPORT)\b")
def parse_output(raw):
    text=raw.strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*','',text)
        text=re.sub(r'\s*```$','',text)
    try:
        value=json.loads(text)
    except (ValueError,TypeError):
        return None
    return value if isinstance(value,dict) else None

def predicted_label(value):
    if not value: return None
    answer=value.get('label',value.get('answer',''))
    if not isinstance(answer,str): return None
    match=re.match(r'^\s*(?:label\s*:\s*)?(NOT_ENOUGH_INFO|CONTRADICT|SUPPORT)\b',answer,re.I)
    return match[1].upper() if match else None

def normalize(text): return re.sub(r'\s+',' ',text).strip()

def run_records(root):
    """Never choose retries by quality. First observed response fixes a job."""
    if (root/'attempts').is_dir():
        for job in sorted((root/'attempts').iterdir()):
            records=sorted(job.glob('attempt-*/run.json'))
            observed=[p for p in records if json.loads(p.read_text(encoding='utf-8')).get('generation_observed')]
            if records: yield observed[0] if observed else records[-1]
    else:
        yield from sorted((root/'runs').rglob('run.json'))

def score(root,gold_path):
    tasks={t['id']:t for t in [json.loads(l) for l in (root/'tasks.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]}
    gold={t['id']:t for t in [json.loads(l) for l in gold_path.read_text(encoding='utf-8').splitlines() if l.strip()]}
    rows=[]
    for path in run_records(root):
        run=json.loads(path.read_text(encoding='utf-8'));task=tasks[run['task_id']]
        response_path=Path(run['raw_response']) if run.get('raw_response') else path.parent/'response.txt'
        raw=response_path.read_text(encoding='utf-8') if response_path.is_file() else ''
        value=parse_output(raw); expected=gold.get(task['id'],{})
        label=predicted_label(value)
        material_texts=[]
        for mat in task['materials']:
            material=path.parent/'workspace/materials'/mat['path']
            if material.is_file():
                raw_material=material.read_text(encoding='utf-8')
                material_texts.append(normalize(raw_material))
                # JSON decoding preserves source sentences containing escaped quotes.
                def strings(value):
                    if isinstance(value,str): yield value
                    elif isinstance(value,list):
                        for child in value: yield from strings(child)
                    elif isinstance(value,dict):
                        for child in value.values(): yield from strings(child)
                try: material_texts.extend(normalize(s) for s in strings(json.loads(raw_material)))
                except ValueError: pass
        evidence=value.get('evidence',[]) if value else []
        quotes=[e.get('quote','') for e in evidence if isinstance(e,dict)] if isinstance(evidence,list) else []
        literal_matches=sum(bool(isinstance(q,str) and len(q.strip())>=8 and any(normalize(q) in text for text in material_texts)) for q in quotes)
        draft=value.get('draft') if value else None
        row={'task_id':task['id'],'kind':task['kind'],'condition':run['condition'],'repeat':run.get('repeat',1),
             'execution_status':run.get('execution_state',run.get('status')),'json_object':value is not None,
             'shared_schema_pass':run.get('response_schema')=='pass',
             'predicted_label':label,'expected_label':expected.get('label'),
             'label_correct':label==expected['label'] if 'label' in expected else None,
             'cmrc_em':calc_em_score(expected['answers'],value.get('answer','')) if expected.get('answers') and value else (0 if expected.get('answers') else None),
             'cmrc_f1':calc_f1_score(expected['answers'],value.get('answer','')) if expected.get('answers') and value else (0 if expected.get('answers') else None),
             'evidence_quotes':len(quotes),'literal_quote_matches':literal_matches,
             'writing_sections':len(draft.get('sections',[])) if isinstance(draft,dict) else None,
             'elapsed_seconds':run.get('elapsed_seconds'),'token_usage':run.get('usage',run.get('token_usage')),
             'response_sha256':hashlib.sha256(raw.encode()).hexdigest() if raw else None,
             'semantic_quality':'not_scored_by_this_script'}
        rows.append(row)
    summary={}
    for condition in sorted({r['condition'] for r in rows}):
        selected=[r for r in rows if r['condition']==condition];qa=[r for r in selected if r['label_correct'] is not None]
        chinese=[r for r in selected if r['cmrc_em'] is not None]
        f1s=[]
        for label_name in sorted({r['expected_label'] for r in qa}):
            tp=sum(r['expected_label']==label_name and r['predicted_label']==label_name for r in qa)
            fp=sum(r['expected_label']!=label_name and r['predicted_label']==label_name for r in qa)
            fn=sum(r['expected_label']==label_name and r['predicted_label']!=label_name for r in qa)
            f1s.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
        summary[condition]={'runs':len(selected),'valid_json':sum(r['json_object'] for r in selected),
                            'shared_schema_pass':sum(r['shared_schema_pass'] for r in selected),
                            'qa_count':len(qa),'qa_correct':sum(r['label_correct'] for r in qa),
                            'label_accuracy':sum(r['label_correct'] for r in qa)/len(qa) if qa else None,
                            'macro_f1_over_present_gold_labels':sum(f1s)/len(f1s) if f1s else None,
                            'cmrc_count':len(chinese),
                            'cmrc_em':sum(r['cmrc_em'] for r in chinese)/len(chinese) if chinese else None,
                            'cmrc_lcs_f1_compat_port':sum(r['cmrc_f1'] for r in chinese)/len(chinese) if chinese else None,
                            'seconds':sum(r['elapsed_seconds'] or 0 for r in selected)}
    return {'scope':'mechanical_pilot_metrics_not_expert_or_semantic_quality','summary':summary,'rows':rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--gold',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=score(a.run,a.gold);a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if result['rows']:
        with (a.out/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(result['rows'][0]));w.writeheader();w.writerows(result['rows'])
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
