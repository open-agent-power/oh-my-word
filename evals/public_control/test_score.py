import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('public_score',Path(__file__).with_name('score.py'))
score=importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)

def test_output_protocol_and_no_label_inference():
    assert score.parse_output('```json\n{"answer":"SUPPORT"}\n```') == {"answer":"SUPPORT"}
    assert score.parse_output('not json') is None
    assert score.parse_output('["SUPPORT"]') is None
    assert score.predicted_label({"answer":"CONTRADICT: the condition differs."}) == 'CONTRADICT'
    assert score.predicted_label({"answer":"This does not SUPPORT the statement."}) is None
    assert score.predicted_label({"answer":"No answer available"}) is None

def test_retry_cannot_replace_observed_response(tmp_path):
    job=tmp_path/'attempts'/'one-job'
    for i,observed in [(1,False),(2,True),(3,True)]:
        path=job/f'attempt-{i:02d}'/'run.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'generation_observed':observed}),encoding='utf-8')
    assert list(score.run_records(tmp_path))==[job/'attempt-02'/'run.json']

def test_cmrc_uses_ordered_lcs_and_exact_reference():
    assert score.calc_em_score(['1963年'],'1963年')==1
    assert score.calc_em_score(['1963年'],'1963年被任命为主教')==0
    assert score.calc_f1_score(['甲乙丙'],'甲乙')==0.8
    assert score.calc_f1_score(['甲乙丙'],'丙乙甲')<1
