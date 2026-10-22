"""Predeclared host BM25 top-5 selection, with no scoring-side inputs."""
from __future__ import annotations
import argparse,collections,hashlib,json,math,re
from pathlib import Path

STOP=set('a an the of to in on for and or is are was were by with that this as from at be not using supplied scientific abstract candidate corpus assess claim return exactly one label support contradict not_enough_info concise rationale supporting document id exact sentence numbers if no supports contradicts use outside knowledge'.split())
def tokens(s):return [t for t in re.findall(r'[a-z0-9]+',s.lower()) if t not in STOP]
def ranking(query,records,k=5):
    terms=[tokens(r['title']+' '+' '.join(r['abstract'])) for r in records]
    df=collections.Counter(t for doc in terms for t in set(doc));avg=sum(map(len,terms))/len(terms)
    q=set(tokens(query));scores=[]
    for r,doc in zip(records,terms):
        counts=collections.Counter(doc);score=0
        for t in q:
            tf=counts[t]
            if tf:
                idf=math.log(1+(len(records)-df[t]+.5)/(df[t]+.5))
                score+=idf*tf*2.5/(tf+1.5*(.25+.75*len(doc)/avg))
        scores.append((score,str(r['doc_id']),r))
    return sorted(scores,key=lambda x:(-x[0],x[1]))[:k]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--tasks',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Use fresh retrieval output directory')
    a.out.mkdir(parents=True)
    selected=[];traces=[];unchanged=[]
    for line in a.tasks.read_text(encoding='utf-8').splitlines():
        task=json.loads(line)
        if task['split']!='development' or task['kind']!='factual-qa':continue
        if not task['id'].startswith('scifact-'):
            unchanged.append({'task_id':task['id'],'state':'not_applicable_single_short_context_no_selection','baseline_reused_without_new_call':True});continue
        material=task['materials'][0];source=a.data_root/material['path']
        if sha(source)!=material['sha256']:raise ValueError('Original corpus changed')
        records=[json.loads(s) for s in source.read_text(encoding='utf-8').splitlines() if s.strip()]
        query=task['request'].split('Claim:',1)[-1].strip()
        chosen=ranking(query,records)
        rel=Path('tasks')/task['id']/'retrieved-corpus.jsonl';dest=a.out/rel;dest.parent.mkdir(parents=True)
        dest.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for _,_,r in chosen),encoding='utf-8')
        outtask={key:task[key] for key in ['id','kind','split','request']}
        outtask['materials']=[{'path':rel.as_posix(),'sha256':sha(dest),'source_id':material['source_id']+'-host-bm25-top5'}]
        selected.append(outtask)
        traces.append({'task_id':task['id'],'query':query,'original_corpus_sha256':sha(source),'original_document_count':len(records),'k':5,'ranked_documents':[{'doc_id':r['doc_id'],'bm25':score} for score,_,r in chosen],'selected_sha256':sha(dest),'gold_used':False})
    (a.out/'tasks.jsonl').write_text(''.join(json.dumps(t,ensure_ascii=False)+'\n' for t in selected),encoding='utf-8')
    (a.out/'selection.json').write_text(json.dumps({'scope':'host_context_selection_not_autonomous_agent_search','parameters':{'k':5,'k1':1.5,'b':.75,'stop_words':sorted(STOP)},'traces':traces,'not_applicable':unchanged,'limitation':'Full source collection available to host in both systems; model receives selected subset only in retrieval condition. Measures selector plus context reduction, not pure retrieval hints or agent tool compliance.'},ensure_ascii=False,indent=2),encoding='utf-8')
    (a.out/'conditions.json').write_text(json.dumps({'conditions':[{'id':'C','base_condition':'current','prompt_append':'','extra_sources':[]}]},indent=2),encoding='utf-8')
    print(json.dumps({'selected_tasks':len(selected),'new_generations_with_3_repeats':len(selected)*3,'no_intervention_tasks':len(unchanged)}))
if __name__=='__main__':main()
