"""Refresh progress, streamed output, error recovery and Parquet dependency checks."""
import io,json,sys,unittest
from unittest.mock import patch
import serve

class RefreshProgressTests(unittest.TestCase):
    def setUp(self):
        serve.refresh_progress(state='idle',percent=0,stage='',request_id='')

    def handler(self,path='/api/refresh',request_id='test-refresh'):
        handler=object.__new__(serve.Handler)
        handler.path=path;handler.headers={'Content-Length':'0','X-Refresh-ID':request_id};handler.rfile=io.BytesIO()
        handler.reply=lambda status,payload:(status,payload)
        return handler

    def test_source_progress_counts_actual_completed_sources(self):
        from fetch_current import sources
        serve.refresh_progress(state='running',percent=5,request_id='sources')
        callback=serve.source_progress('sources')
        seen=[]
        for name in sources(serve.YEAR):
            callback('preseason odds page not published; expectations will be blank' if name=='preseason_odds' else 'fetched '+name)
            seen.append(serve.refresh_progress()['percent'])
        self.assertEqual(seen,sorted(seen));self.assertEqual(seen[-1],65)
        callback('fetched per_game');self.assertEqual(serve.refresh_progress()['percent'],65)
        self.assertEqual(serve.refresh_progress()['request_id'],'sources')

    def test_team_progress_counts_completed_attempts(self):
        callback=serve.team_progress('teams')
        for index,code in enumerate(sorted(serve.CODES),1):
            callback(('warning: '+code+': unavailable') if index%2 else code+' 45.5 (line 45.5, 2 books)')
            self.assertEqual(serve.refresh_progress()['percent'],68+round(12*index/len(serve.CODES)))
        self.assertEqual(serve.refresh_progress()['percent'],80)
        callback('warning: no standings available')
        self.assertEqual(serve.refresh_progress()['percent'],80)

    def test_refresh_stages_and_completion(self):
        observed=[]
        def fake_run(*args,on_output=None):
            observed.append((args[0],serve.refresh_progress()['percent']))
            if on_output:on_output('fetched per_game')
        def fake_project():
            self.assertEqual(serve.refresh_progress()['percent'],92)
            return {'awards':{}}
        with patch.object(serve,'run',side_effect=fake_run),patch.object(serve,'project',side_effect=fake_project):
            status,payload=self.handler().do_POST()
        self.assertEqual(status,200);self.assertTrue(payload['ok'])
        self.assertEqual(observed,[('fetch_current.py',5),('fetch_team_wins.py',68),('fetch_odds.py',82)])
        state=serve.refresh_progress();self.assertEqual(state['percent'],100);self.assertEqual(state['state'],'complete')
        self.assertEqual(state['request_id'],'test-refresh');self.assertFalse(serve.LOCK.locked())

    def test_failure_does_not_show_complete_and_can_retry(self):
        with patch.object(serve,'run',side_effect=RuntimeError('source unavailable')):
            status,payload=self.handler().do_POST()
        self.assertEqual(status,500);self.assertEqual(payload['error'],'source unavailable')
        self.assertEqual(serve.refresh_progress()['state'],'failed');self.assertLess(serve.refresh_progress()['percent'],100)
        self.assertFalse(serve.LOCK.locked())
        with patch.object(serve,'run',return_value=''),patch.object(serve,'project',return_value={}):
            status,_=self.handler(request_id='retry').do_POST()
        self.assertEqual(status,200);self.assertEqual(serve.refresh_progress()['request_id'],'retry')

    def test_optional_market_failure_still_completes(self):
        def fake_run(*args,**kwargs):
            if args[0]=='fetch_odds.py':raise RuntimeError('odds unavailable')
        with patch.object(serve,'run',side_effect=fake_run),patch.object(serve,'project',return_value={}):
            status,payload=self.handler().do_POST()
        self.assertEqual(status,200);self.assertIn('odds unavailable',payload['message'])
        self.assertEqual(serve.refresh_progress()['state'],'complete')

    def test_status_is_a_snapshot(self):
        serve.refresh_progress(state='running',percent=40,stage='Sources',request_id='status-test')
        status,payload=self.handler('/api/status').do_GET()
        self.assertEqual(status,200);self.assertEqual(payload['refresh']['percent'],40)
        payload['refresh']['percent']=99;self.assertEqual(serve.refresh_progress()['percent'],40)

    def test_subprocess_streaming_and_failures(self):
        lines=[]
        with patch.object(serve,'PYTHON',sys.executable):
            output=serve.run('-c','print("fetched advanced", flush=True)',on_output=lines.append)
            self.assertIn('fetched advanced',output);self.assertEqual(lines,['fetched advanced'])
            with self.assertRaisesRegex(RuntimeError,'read failed'):
                serve.run('-c','import sys; print("read failed"); sys.exit(2)')

    def test_declared_parquet_reader_handles_cached_data(self):
        import pandas as pd
        frame=pd.read_parquet(serve.ROOT/'data/current/2027/raw/team_advanced.parquet')
        self.assertGreater(len(frame),0);self.assertIn('def_rating',frame.columns)

if __name__=='__main__':unittest.main()
