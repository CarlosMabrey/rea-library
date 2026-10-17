import unittest,tempfile,os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import registry
class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.previous=registry.DATA;registry.DATA=self.root/'data'
        self.project=self.root/'project';self.project.mkdir();(self.project/'index.html').write_text('<h1>Demo</h1>')
        self.manifest={'name':'Demo','path':str(self.project),'kind':'component','source':'custom'}
    def tearDown(self):registry.DATA=self.previous;self.tmp.cleanup()
    def test_registration_is_persistent_and_idempotent(self):
        first=registry.register(self.manifest);again=registry.register({**self.manifest,'description':'Updated'})
        self.assertEqual(first['id'],again['id']);self.assertEqual(len(registry.apps()),1);self.assertEqual(registry.apps()[0]['description'],'Updated')
    def test_rejects_entry_traversal(self):
        (self.root/'outside.html').write_text('outside')
        with self.assertRaises(ValueError):registry.register({**self.manifest,'entry':'../outside.html'})
    def test_rejects_symlink_escape(self):
        (self.root/'outside.html').write_text('outside');(self.project/'escape.html').symlink_to(self.root/'outside.html')
        with self.assertRaises(ValueError):registry.register({**self.manifest,'entry':'escape.html'})
    def test_rejects_script_urls_and_credentials(self):
        for url in ['javascript:alert(1)','file:///etc/passwd','https://user:password@example.com']:
            with self.subTest(url=url),self.assertRaises(ValueError):registry.register({'name':'No','url':url})
    def test_accepts_http_launch_url(self):
        a=registry.register({'name':'Dev server','url':'http://localhost:3000','kind':'tool'});self.assertEqual(a['status'],'ready')
    def test_inbox_import_is_once_and_errors_retained(self):
        registry.prepare();registry.atomic(registry.DATA/'inbox/good.json',self.manifest);registry.atomic(registry.DATA/'inbox/bad.json',{'name':'Broken'})
        self.assertEqual(len(registry.consume_inbox()),1);self.assertEqual(registry.consume_inbox(),[]);self.assertEqual(len(registry.apps()),1)
        self.assertTrue((registry.DATA/'inbox/bad.error').exists());self.assertTrue((registry.DATA/'inbox/good.registered').exists())
    def test_native_app_registration(self):
        p=self.root/'Example.app';(p/'Contents').mkdir(parents=True);(p/'Contents/Info.plist').write_text('example')
        item=registry.register({'name':'Native example','path':str(p),'source':'custom'})
        self.assertEqual(item['launchType'],'native')
    def test_artwork_survives_manifest_updates(self):
        old_root=registry.ROOT;registry.ROOT=self.root
        try:
            assets=self.root/'assets';assets.mkdir();(assets/'icon.png').write_bytes(b'icon')
            first=registry.register({**self.manifest,'icon':'assets/icon.png','screenshots':['assets/icon.png']})
            again=registry.register({**self.manifest,'id':first['id'],'description':'Updated build'})
            self.assertEqual(again['icon'],'assets/icon.png');self.assertEqual(again['screenshots'],['assets/icon.png'])
        finally:registry.ROOT=old_root
    def test_artwork_cannot_escape_assets(self):
        with self.assertRaises(ValueError):registry.register({**self.manifest,'icon':'assets/../registry.py'})
    def test_missing_artifact_never_ready(self):
        with self.assertRaises(ValueError):registry.register({'name':'Missing','path':str(self.root/'not-present')})
    def test_invalid_evidence_rejected(self):
        with self.assertRaises(ValueError):registry.register({**self.manifest,'evidence':'not-a-list'})
if __name__=='__main__':unittest.main()
