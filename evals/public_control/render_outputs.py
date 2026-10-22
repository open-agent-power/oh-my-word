"""Render untouched generated writing with the repository backend.

Only structural IDs are added; no generated prose or table cells are corrected.
This is a formatter experiment, not the production build/review/finalize gate.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from word_skills.render import render
from word_skills.inspect import inspect_docx, inspect_pdf, preview
from score import run_records

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--soffice',required=True)
    p.add_argument('--repeat',type=int,default=1)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    for record in run_records(a.run):
        metadata=json.loads(record.read_text(encoding='utf-8'))
        if metadata['kind'] not in {'technical-report','design-spec'} or metadata.get('repeat',1)!=a.repeat:
            continue
        response=record.parent/'response.txt'
        target=a.out/metadata['task_id']/metadata['condition']
        if target.exists():
            manifest=target/'manifest.json'
            if a.resume and manifest.is_file() and json.loads(manifest.read_text(encoding='utf-8'))['source_response_sha256']==digest(response):
                continue
            raise ValueError(f'Refusing to overwrite {target}')
        target.mkdir(parents=True)
        result={'task_id':metadata['task_id'],'condition':metadata['condition'],
                'scope':'formatter_only_not_production_build_or_finalized',
                'source_response':str(response),'source_response_sha256':digest(response),
                'adaptation':'structural_ids_only','human_review':'not_performed',
                'visual_review':'pending'}
        try:
            value=json.loads(response.read_text(encoding='utf-8'))
            (target/'generated-evidence.json').write_text(json.dumps({'scope':'raw_generated_evidence_not_production_validated','evidence':value.get('evidence',[]),'limitations':value.get('limitations',[])},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            draft=copy.deepcopy(value['draft'])
            for i,section in enumerate(draft['sections'],1):
                section.setdefault('id',f's{i}')
                for j,block in enumerate(section['blocks'],1):
                    block.setdefault('id',f's{i}-b{j}')
            (target/'draft.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            render(draft,target/'output.docx')
            result['docx_issues']=inspect_docx(target/'output.docx',draft)
            preview(target/'output.docx',target/'preview',soffice=a.soffice)
            result['pdf_checks']=inspect_pdf(target/'preview/preview.pdf',draft)
            result['render_state']='complete'
        except Exception as error:
            result['render_state']='failed'
            result['error']=f'{type(error).__name__}: {error}'
        result['artifacts']={str(f.relative_to(target)):digest(f) for f in target.rglob('*') if f.is_file()}
        (target/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'task':metadata['task_id'],'condition':metadata['condition'],'render_state':result['render_state']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
