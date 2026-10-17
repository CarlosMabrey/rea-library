import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipeline,registry

class PipelineTests(unittest.TestCase):
    def setUp(self):
        pipeline._STOP.clear()
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old_data=registry.DATA;self.old_root=registry.ROOT
        registry.DATA=self.root/'data';registry.ROOT=self.root/'library';registry.ROOT.mkdir()
        self.project=self.root/'project';self.project.mkdir();(self.project/'index.html').write_text('<h1>Actual app</h1>')
        self.manifest={'id':'demo','name':'Demo','path':str(self.project)}
    def tearDown(self):
        pipeline.stop();registry.DATA=self.old_data;registry.ROOT=self.old_root;self.tmp.cleanup()
    def test_offline_registration_enqueues_without_running_agent(self):
        with patch.object(pipeline,'capture') as capture:
            registry.register(self.manifest)
            self.assertEqual(pipeline.status()['jobs'][0]['state'],'queued');capture.assert_not_called()
            self.assertFalse(pipeline.status()['enabled'])
    def test_identical_registration_and_reads_do_not_enqueue(self):
        registry.register(self.manifest);registry.apps();registry.register(self.manifest)
        self.assertEqual(len(pipeline._jobs()),1)
    def test_artifact_change_enqueues_and_ignores_dependencies(self):
        registry.register(self.manifest)
        deps=self.project/'node_modules';deps.mkdir();(deps/'index.js').write_text('dependency')
        registry.register(self.manifest);self.assertEqual(len(pipeline._jobs()),1)
        (self.project/'index.html').write_text('<h1>Rebuilt</h1>');registry.register(self.manifest)
        self.assertEqual(len(pipeline._jobs()),2)
    def test_internal_artwork_update_does_not_enqueue(self):
        item=registry.register(self.manifest);registry.register({**item,'artworkProvenance':'reviewed'},enqueue=False)
        self.assertEqual(len(pipeline._jobs()),1)
    def test_metadata_update_reuses_completed_capture(self):
        item=registry.register(self.manifest);job=pipeline._jobs()[0];pipeline.save(job,captureState='ready',state='complete')
        registry.register({**self.manifest,'description':'New description'})
        self.assertTrue(pipeline._jobs()[-1]['reuseArtwork'])
    def test_retry_preserves_id_and_creates_new_attempt(self):
        registry.register(self.manifest);first=pipeline._jobs()[0];pipeline.save(first,state='needs_attention')
        result=pipeline.retry('demo');self.assertEqual(result['appId'],'demo');self.assertNotEqual(result['id'],first['id'])
        self.assertEqual(len(registry.apps()),1)
    def test_url_only_registration_without_revision_refreshes_capture(self):
        manifest={'id':'remote','name':'Remote demo','url':'http://localhost:3000'}
        registry.register(manifest);first=pipeline._jobs()[0];pipeline.save(first,captureState='ready',state='complete')
        registry.apps();self.assertEqual(len(pipeline._jobs()),1)
        registry.register(manifest);self.assertEqual(len(pipeline._jobs()),2)
        self.assertFalse(pipeline._jobs()[-1]['reuseArtwork']);self.assertEqual(len(registry.apps()),1)
    def test_url_revision_deduplicates_and_changes_trigger_capture(self):
        manifest={'id':'remote','name':'Remote demo','url':'http://localhost:3000','revision':'build-1'}
        registry.register(manifest);registry.register(manifest);self.assertEqual(len(pipeline._jobs()),1)
        registry.register({**manifest,'revision':'build-2'});self.assertEqual(len(pipeline._jobs()),2)
        self.assertNotEqual(pipeline._jobs()[0]['artifactDigest'],pipeline._jobs()[1]['artifactDigest'])
    def test_manual_retry_does_not_reuse_old_capture(self):
        registry.register(self.manifest);first=pipeline._jobs()[0];pipeline.save(first,captureState='ready',state='complete')
        retry=pipeline.retry('demo');self.assertFalse(retry['reuseArtwork'])
    def test_asset_paths_cannot_escape_workspace(self):
        registry.register(self.manifest);job=pipeline._jobs()[0];workspace=self.root/'workspace';workspace.mkdir()
        outside=self.root/'private.png';outside.write_bytes(b'\x89PNG\r\n\x1a\nactual')
        (workspace/'escape.png').symlink_to(outside)
        with self.assertRaises(ValueError):pipeline.apply_artwork(job,{'screenshots':[str(workspace/'escape.png')],'provenance':'Actual screen reviewed.'},workspace)
        self.assertEqual(registry.apps()[0]['screenshots'],[])
    def test_new_screenshots_do_not_inherit_public_safety(self):
        assets=registry.ROOT/'assets';assets.mkdir();(assets/'old.png').write_bytes(b'old')
        registry.register({**self.manifest,'screenshots':['assets/old.png'],'artworkPublicSafe':True})
        job=pipeline._jobs()[0];workspace=self.root/'workspace';workspace.mkdir();shot=workspace/'actual.png';shot.write_bytes(b'\x89PNG\r\n\x1a\nactual')
        pipeline.apply_artwork(job,{'screenshots':[str(shot)],'provenance':'Actual customer notes shown; local only.'},workspace)
        app=registry.apps()[0];self.assertFalse(app['artworkPublicSafe']);self.assertEqual(app['publicScreenshots'],[])
        self.assertEqual(len(pipeline._jobs()),1)
    def test_failure_preserves_artwork_and_still_publishes_catalog(self):
        registry.register(self.manifest);job=pipeline._jobs()[0]
        fake=type('FakePublisher',(),{'publish_library':staticmethod(lambda:{'state':'published'})})
        with patch.object(pipeline,'config',return_value={'enabled':True,'capture':True,'publish':True}),patch.object(pipeline,'capture',side_effect=RuntimeError('Permission prompt blocked capture')),patch.dict(sys.modules,{'publisher':fake}):
            pipeline.process(job)
        self.assertEqual(job['state'],'needs_attention');self.assertEqual(job['publishState'],'published');self.assertEqual(len(registry.apps()),1)
    def test_status_does_not_expose_paths_or_private_logs(self):
        registry.register(self.manifest);encoded=json.dumps(pipeline.status())
        self.assertNotIn(str(self.project),encoded);self.assertNotIn('item',pipeline.status()['jobs'][0])
if __name__=='__main__':unittest.main()
