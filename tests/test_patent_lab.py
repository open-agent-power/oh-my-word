"""Negative boundaries for private case intake and evidence-bound experiments."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

from oh_my_patent.casework import compare_revisions, read_revision, validate_case, validate_corpus, validate_needs
from oh_my_patent.lab_common import digest, relative_file, write_json
from oh_my_patent.skill_registry import load_registry
from oh_my_patent.skill_eval import ExecutionInterrupted, execution_env, generic_entrypoint, prepare_suite, run_suite, summarize, verify_task

ROOT = Path(__file__).resolve().parents[1]


class ProxyEnvTests(unittest.TestCase):
    def test_windows_inherits_system_proxy_without_mutating_parent(self):
        parent = {'KEEP': 'value', 'NO_PROXY': 'localhost'}
        with patch.dict('os.environ', parent, clear=True), patch('oh_my_patent.skill_eval.os.name', 'nt'), \
             patch('oh_my_patent.skill_eval.getproxies', return_value={'http': 'http://127.0.0.1:12345', 'https': 'http://127.0.0.1:12345', 'no': 'other'}):
            env = execution_env()
            self.assertEqual(env['HTTPS_PROXY'], 'http://127.0.0.1:12345')
            self.assertEqual(env['HTTP_PROXY'], env['HTTPS_PROXY'])
            self.assertEqual(env['NO_PROXY'], 'localhost')
            import os
            self.assertNotIn('HTTPS_PROXY', os.environ)

    def test_explicit_proxy_takes_priority_case_insensitively(self):
        with patch.dict('os.environ', {'https_proxy': 'http://explicit'}, clear=True), \
             patch('oh_my_patent.skill_eval.os.name', 'nt'), patch('oh_my_patent.skill_eval.getproxies') as proxies:
            self.assertEqual({key.lower(): value for key, value in execution_env().items()}, {'https_proxy': 'http://explicit'})
            proxies.assert_not_called()

    def test_explicit_empty_proxy_does_not_enable_system_proxy(self):
        with patch.dict('os.environ', {'HTTPS_PROXY': ''}, clear=True), \
             patch('oh_my_patent.skill_eval.os.name', 'nt'), patch('oh_my_patent.skill_eval.getproxies') as proxies:
            self.assertEqual(execution_env(), {'HTTPS_PROXY': ''})
            proxies.assert_not_called()

    def test_other_platform_keeps_environment(self):
        with patch.dict('os.environ', {'KEEP': 'value'}, clear=True), \
             patch('oh_my_patent.skill_eval.os.name', 'posix'), patch('oh_my_patent.skill_eval.getproxies') as proxies:
            self.assertEqual(execution_env(), {'KEEP': 'value'})
            proxies.assert_not_called()


class GenericEntrypointTests(unittest.TestCase):
    def test_legacy_and_optional_boundaries_preserve_shared_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'evals').mkdir()
            (root/'evals/generic-entrypoint.md').write_text('GENERIC\n', encoding='utf-8')
            for heading in ('## 必走链路', '## 可选工具交付链路'):
                with self.subTest(heading=heading):
                    (root/'SKILL.md').write_text(
                        f'BEFORE\n## 总览与领域路由\nDOMAIN\n{heading}\nAFTER\n', encoding='utf-8')
                    self.assertEqual(generic_entrypoint(root), f'BEFORE\nGENERIC\n\n{heading}\nAFTER\n')

    def test_invalid_or_ambiguous_boundaries_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for text in (
                '## 总览与领域路由\nNO TOOL BOUNDARY\n',
                '## 总览与领域路由\n## 必走链路\n## 可选工具交付链路\n',
                '## 总览与领域路由\n## 必走链路\n## 必走链路\n',
                '## 总览与领域路由\n## 总览与领域路由\n## 必走链路\n',
                '## 必走链路\n## 总览与领域路由\n',
                '## 总览与领域路由\nquoted ## 必走链路\n',
            ):
                with self.subTest(text=text):
                    (root/'SKILL.md').write_text(text, encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'routing boundaries'):
                        generic_entrypoint(root)


class LabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.root = self.folder/'bundle'
        self.root.mkdir()
        shutil.copytree(ROOT/'skills', self.root/'skills', ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('docs', 'oh_my_patent', 'tools', 'evals'):
            shutil.copytree(ROOT/name, self.root/name, ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('requirements.txt', 'requirements-ingest.txt'):
            shutil.copy2(ROOT/name, self.root/name)

    def card(self, name='case1', split='development', family='fam1', project='proj1', permission='local_only'):
        folder = self.folder/name
        folder.mkdir()
        for f, text in [('input.md', '本案结构'+name), ('answer.md', '专家答案'+name)]:
            (folder/f).write_text(text, encoding='utf-8')
        card = {'schema_version': 1, 'case_id': name, 'family_id': family, 'project_id': project,
                'split': split, 'use_permission': permission, 'documents': [
                    {'id': 'D1', 'path': 'input.md', 'kind': 'disclosure', 'role': 'input', 'version': 'v1', 'sha256': digest(folder/'input.md')},
                    {'id': 'D2', 'path': 'answer.md', 'kind': 'expert_draft', 'role': 'answer', 'version': 'v2', 'sha256': digest(folder/'answer.md')}]}
        write_json(folder/'case.json', card)
        return folder/'case.json'

    def suite(self, card=None, modes=('generic', 'domain')):
        cases = {'schema_version': 1, 'cases': [{'id': 'one', 'request': '请依据真实连杆关系起草',
                 'expected': {'required': ['patent-mechanical'], 'avoid': [], 'behavior': 'PRIVATE_EXPECTATION_DO_NOT_LEAK'}}]}
        if card:
            cases['cases'][0]['manifest'] = card.relative_to(self.folder).as_posix()
        path = self.folder/'cases.yaml'
        path.write_text(yaml.safe_dump(cases, allow_unicode=True), encoding='utf-8')
        out = self.folder/'run'
        suite = prepare_suite(self.root, path, out, modes=modes)
        for task in suite['tasks']:
            self.addCleanup(shutil.rmtree, task['workspace'], ignore_errors=True)
        return out, suite

    def fake_run(self, out, failed=False):
        events = [
            {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'Read bundle/skills/oh-my-patent/domains/patent-mechanical/SKILL.md', 'exit_code': 0}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '材料不足，需确认连接关系。'}},
            {'type': 'turn.failed' if failed else 'turn.completed', 'usage': {'input_tokens': 11, 'output_tokens': 7}}]
        raw = ('\n'.join(json.dumps(e, ensure_ascii=False) for e in events)+'\n').encode('utf-8')
        with patch('oh_my_patent.skill_eval.shutil.which', return_value='codex'), \
             patch('oh_my_patent.skill_eval.subprocess.run', return_value=subprocess.CompletedProcess([], 0, b'test-cli', b'')), \
             patch('oh_my_patent.skill_eval._execute', return_value=(1 if failed else 0, raw, b'', False)):
            return run_suite(out)

    def test_registry_integrity(self):
        self.assertEqual(len(load_registry(self.root)), 6)

    def test_validated_without_quality_evidence_rejected(self):
        p = self.root/'skills/oh-my-patent/domains/registry.yaml'
        data = yaml.safe_load(p.read_text(encoding='utf-8'))
        data['modules'][0]['status'] = 'validated'
        p.write_text(yaml.safe_dump(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'quality_evidence'):
            load_registry(self.root)

    def test_registry_version_drift_rejected(self):
        p = self.root/'skills/oh-my-patent/domains/registry.yaml'
        p.write_text(p.read_text(encoding='utf-8').replace("version: '1.0'", "version: '9.0'", 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            load_registry(self.root)

    def test_case_hash_change_rejected(self):
        p = self.card()
        self.assertEqual(validate_case(p)['case_id'], 'case1')
        (p.parent/'input.md').write_text('新内容', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'hash'):
            validate_case(p)

    def test_path_escape_rejected(self):
        (self.folder/'secret.txt').write_text('secret', encoding='utf-8')
        with self.assertRaises(ValueError):
            relative_file(self.root, '../secret.txt')
        with self.assertRaises(ValueError):
            relative_file(self.root, 'C:/secret.txt')

    def test_family_split_leakage_rejected(self):
        a = self.card()
        b = self.card('case2', 'test', project='proj2')
        with self.assertRaisesRegex(ValueError, 'family_id crosses'):
            validate_corpus([a, b])

    def test_project_split_leakage_rejected(self):
        a = self.card()
        b = self.card('case2', 'test', family='fam2')
        with self.assertRaisesRegex(ValueError, 'project_id crosses'):
            validate_corpus([a, b])

    def test_duplicate_input_across_groups_rejected(self):
        a = self.card()
        b = self.card('case2', 'test', family='fam2', project='proj2')
        shutil.copy2(a.parent/'input.md', b.parent/'input.md')
        data = json.loads(b.read_text(encoding='utf-8'))
        data['documents'][0]['sha256'] = digest(b.parent/'input.md')
        write_json(b, data)
        with self.assertRaisesRegex(ValueError, 'duplicate input'):
            validate_corpus([a, b])

    def test_revision_read_preserves_edits_and_comments(self):
        path = self.folder/'edited.docx'
        ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        document = f'<w:document xmlns:w="{ns}"><w:body><w:p><w:r><w:t>连接</w:t></w:r><w:del w:id="1" w:author="Reviewer"><w:r><w:delText>旧杆</w:delText></w:r></w:del><w:ins w:id="2"><w:r><w:t>新杆</w:t></w:r></w:ins><w:commentRangeStart w:id="7"/><w:r><w:t>。</w:t></w:r><w:commentRangeEnd w:id="7"/></w:p></w:body></w:document>'
        comments = f'<w:comments xmlns:w="{ns}"><w:comment w:id="7" w:author="Reviewer"><w:p><w:r><w:t>需核对连接关系</w:t></w:r></w:p></w:comment></w:comments>'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', document)
            z.writestr('word/comments.xml', comments)
        original = digest(path)
        result = read_revision(path)
        self.assertEqual(result['before'], '连接旧杆。')
        self.assertEqual(result['after'], '连接新杆。')
        self.assertEqual([r['kind'] for r in result['revisions']], ['del', 'ins'])
        self.assertEqual(result['comments'][0]['locators'], ['word/document.xml:p1'])
        self.assertIn('需核对', result['comments'][0]['text'])
        self.assertEqual(digest(path), original)

    def test_reference_role_cannot_hide_heldout_answer(self):
        a = self.card()
        b = self.card('case2', 'test', family='fam2', project='proj2')
        shutil.copy2(a.parent/'answer.md', b.parent/'borrowed.md')
        data = json.loads(b.read_text(encoding='utf-8'))
        data['documents'].append({'id': 'D3', 'path': 'borrowed.md', 'role': 'reference', 'kind': 'writing_case',
                                  'version': 'v1', 'sha256': digest(b.parent/'borrowed.md')})
        write_json(b, data)
        with self.assertRaisesRegex(ValueError, 'reference reuse'):
            validate_corpus([a, b])

    def test_revision_diff_does_not_invent_reasons(self):
        a, b = self.folder/'a.md', self.folder/'b.md'
        a.write_text('通过旧连接', encoding='utf-8')
        b.write_text('通过新连接', encoding='utf-8')
        result = compare_revisions(a, b)
        self.assertIn('-通过旧连接', result['diff'])
        self.assertEqual(result['modification_reasons'], [])
        self.assertEqual(result['review_status'], 'pending')

    def test_found_need_requires_located_evidence(self):
        p = self.folder/'needs.json'
        row = {'id': 'N1', 'question': '指标定义', 'query': '测试方法', 'version_or_date_scope': 'unknown',
               'delivery': '原文和页码', 'role': 'standard', 'status': 'found'}
        write_json(p, {'schema_version': 1, 'needs': [row]})
        with self.assertRaisesRegex(ValueError, 'evidence'):
            validate_needs(p)

    def test_prepare_hides_answers_and_expectations(self):
        card = self.card()
        out, suite = self.suite(card)
        self.assertEqual(len(suite['tasks']), 2)
        self.assertNotEqual(suite['tasks'][0]['workspace'], suite['tasks'][1]['workspace'])
        for task in suite['tasks']:
            work = Path(task['workspace'])
            self.assertFalse((work/'materials/answer.md').exists())
            self.assertTrue((work/'materials/input.md').exists())
            self.assertFalse((work/'bundle/evals').exists())
            self.assertFalse((work/'bundle/.agent').exists())
            for p in work.rglob('*'):
                if p.is_file() and p.suffix in ('.md', '.json', '.yaml', '.txt'):
                    self.assertNotIn('PRIVATE_EXPECTATION_DO_NOT_LEAK', p.read_text(encoding='utf-8'))
                    self.assertNotIn('专家答案case1', p.read_text(encoding='utf-8'))
            self.assertEqual((work/'bundle/skills/oh-my-patent/domains').exists(), task['mode'] == 'domain')

    def test_task_drift_rejected(self):
        _, suite = self.suite()
        task = suite['tasks'][0]
        (Path(task['workspace'])/'task.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            verify_task(task)

    def test_answer_in_shared_reference_rejected(self):
        card = self.card()
        shutil.copy2(card.parent/'answer.md', self.root/'skills/oh-my-patent/references/existing-writing-example.md')
        with self.assertRaisesRegex(ValueError, 'shared bundle'):
            self.suite(card)

    def test_baseline_preserves_shared_orchestration(self):
        _, suite = self.suite()
        source = (self.root/'skills/oh-my-patent/SKILL.md').read_text(encoding='utf-8')
        for task in suite['tasks']:
            entry = (Path(task['workspace'])/'bundle/skills/oh-my-patent/SKILL.md').read_text(encoding='utf-8')
            self.assertEqual(entry.split('## 可选工具交付链路', 1)[1], source.split('## 可选工具交付链路', 1)[1])
            self.assertTrue(entry.startswith(source.split('## 总览与领域路由', 1)[0]))
            if task['mode'] == 'generic':
                self.assertNotIn('先读 [领域目录]', entry)

    def test_failure_stops_queue(self):
        out, suite = self.suite()
        results = self.fake_run(out, failed=True)
        self.assertEqual(len(results), 1)
        report = summarize(out)
        self.assertEqual(report['modes']['generic']['error'], 1)
        self.assertEqual(report['modes']['domain']['not_run'], 1)

    def test_incomplete_folder_is_interrupted(self):
        out, suite = self.suite()
        (out/suite['tasks'][0]['id']).mkdir()
        report = summarize(out)
        self.assertEqual(report['runs'][0]['execution'], 'interrupted')
        self.assertEqual(report['runs'][1]['execution'], 'not_run')

    def test_interrupt_preserves_run_and_stops(self):
        out, _ = self.suite()
        with patch('oh_my_patent.skill_eval.shutil.which', return_value='codex'), \
             patch('oh_my_patent.skill_eval.subprocess.run', return_value=subprocess.CompletedProcess([], 0, b'test-cli', b'')), \
             patch('oh_my_patent.skill_eval._execute', side_effect=ExecutionInterrupted(-1, b'partial trace', b'cancelled')):
            results = run_suite(out)
        self.assertEqual(len(results), 1)
        self.assertEqual(summarize(out)['runs'][0]['execution'], 'interrupted')

    def test_existing_output_preserved(self):
        out, _ = self.suite()
        with self.assertRaisesRegex(ValueError, 'preserved'):
            prepare_suite(self.root, self.folder/'cases.yaml', out)

    def test_local_only_never_calls_model(self):
        out, _ = self.suite(self.card())
        with patch('oh_my_patent.skill_eval.shutil.which', return_value='codex'), patch('oh_my_patent.skill_eval._execute') as execute:
            with self.assertRaisesRegex(ValueError, 'local_only'):
                run_suite(out)
            execute.assert_not_called()

    def test_unexecuted_is_unknown_not_pass(self):
        out, _ = self.suite()
        report = summarize(out)
        self.assertEqual(report['modes']['domain']['pass'], 0)
        self.assertEqual(report['modes']['domain']['unknown'], 3)
        self.assertEqual(report['quality_gain'], 'not_established')

    def test_executed_still_ungraded(self):
        out, _ = self.suite()
        self.fake_run(out)
        report = summarize(out)
        self.assertEqual(report['modes']['domain']['succeeded'], 1)
        self.assertEqual(report['modes']['domain']['unknown'], 3)

    def test_failed_run_cannot_be_graded_pass(self):
        out, suite = self.suite()
        self.fake_run(out, failed=True)
        folder = out/suite['tasks'][0]['id']
        grade = json.loads((folder/'grade.json').read_text(encoding='utf-8'))
        grade['reviewer'] = 'reviewer'
        grade['criteria'][1].update(status='pass', reason='核对', evidence=[{'file': 'response.md', 'quote': '材料不足'}])
        write_json(folder/'grade.json', grade)
        with self.assertRaisesRegex(ValueError, 'failed'):
            summarize(out)

    def test_changed_artifact_rejects_stale_grading(self):
        out, suite = self.suite()
        self.fake_run(out)
        (out/suite['tasks'][0]['id']/'response.md').write_text('不同输出', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            summarize(out)

    def test_routing_self_report_is_not_evidence(self):
        out, suite = self.suite()
        self.fake_run(out)
        folder = out/suite['tasks'][0]['id']
        grade = json.loads((folder/'grade.json').read_text(encoding='utf-8'))
        grade['reviewer'] = 'reviewer'
        grade['criteria'][0].update(status='pass', reason='模块加载', evidence=[{'file': 'response.md', 'quote': '材料不足'}])
        write_json(folder/'grade.json', grade)
        with self.assertRaisesRegex(ValueError, 'actual trace'):
            summarize(out)

    def test_located_manual_grade_counted_without_claiming_gain(self):
        out, suite = self.suite(modes=('domain',))
        self.fake_run(out)
        folder = out/suite['tasks'][0]['id']
        grade = json.loads((folder/'grade.json').read_text(encoding='utf-8'))
        grade['reviewer'] = 'reviewer'
        grade['criteria'][0].update(status='pass', reason='独立复核命令记录', evidence=[{'file': 'trace.jsonl', 'quote': 'bundle/skills/oh-my-patent/domains/patent-mechanical/SKILL.md'}])
        write_json(folder/'grade.json', grade)
        report = summarize(out)
        self.assertEqual(report['modes']['domain']['pass'], 1)
        self.assertEqual(report['modes']['domain']['unknown'], 2)
        self.assertEqual(report['quality_gain'], 'not_established')

    def test_outcome_without_evidence_rejected(self):
        out, suite = self.suite(modes=('domain',))
        self.fake_run(out)
        folder = out/suite['tasks'][0]['id']
        grade = json.loads((folder/'grade.json').read_text(encoding='utf-8'))
        grade.update(reviewer='reviewer', task_outcome='completed', severe_failure='none')
        write_json(folder/'grade.json', grade)
        with self.assertRaisesRegex(ValueError, 'located evidence'):
            summarize(out)

    def test_editing_time_requires_record(self):
        out, suite = self.suite(modes=('domain',))
        self.fake_run(out)
        folder = out/suite['tasks'][0]['id']
        grade = json.loads((folder/'grade.json').read_text(encoding='utf-8'))
        grade.update(reviewer='reviewer', editing_minutes=0)
        write_json(folder/'grade.json', grade)
        with self.assertRaisesRegex(ValueError, 'timing record'):
            summarize(out)
        grade['editing_record'] = {'started_at': '2026-10-13T12:00:00+08:00', 'ended_at': '2026-10-13T12:00:00+08:00', 'activity': '人工核对：无需修改'}
        write_json(folder/'grade.json', grade)
        self.assertEqual(summarize(out)['runs'][0]['editing_minutes'], 0)


if __name__ == '__main__':
    unittest.main()
