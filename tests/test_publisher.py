import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import publisher,registry,pipeline

class PublisherTests(unittest.TestCase):
    def item(self,**changes):
        item={'id':'demo','name':'Demo','kind':'component','source':'custom','createdAt':'2026-01-01','updatedAt':'2026-01-02','path':'/Users/private/customer-project','entry':'secret.html','description':'Private customer notes','evidence':['ev_private'],'artworkProvenance':'Private raw process/customer evidence','icon':'assets/private-icon.png','screenshots':['assets/customer.png'],'cover':'assets/customer.png'}
        item.update(changes);return item
    def test_catalog_does_not_publish_private_metadata(self):
        rows=publisher.catalog([self.item()],[],lambda x:self.fail('Private artwork must not be copied'))
        row=rows[0];encoded=json.dumps(rows)
        for secret in ['/Users/private','secret.html','customer notes','ev_private','raw process','private-icon','customer.png']:
            self.assertNotIn(secret,encoded)
        self.assertEqual(row['evidence'],[]);self.assertNotIn('path',row);self.assertEqual(row['screenshots'],[])
    def test_explicit_public_description_and_icon_are_selected(self):
        copy=Mock(side_effect=lambda ref:'published/'+Path(ref).name)
        rows=publisher.catalog([self.item(iconPublicSafe=True,publication={'description':'A reusable navigation component.'})],[],copy)
        self.assertEqual(rows[0]['description'],'A reusable navigation component.')
        self.assertEqual(rows[0]['icon'],'published/private-icon.png');copy.assert_called_once_with('assets/private-icon.png')
    def test_public_screenshots_override_local_originals(self):
        copy=Mock(side_effect=lambda ref:ref)
        row=publisher.catalog([self.item(publicScreenshots=['assets/reviewed.png'])],[],copy)[0]
        self.assertEqual(row['screenshots'],['assets/reviewed.png']);self.assertEqual(row['cover'],'assets/reviewed.png');copy.assert_called_once_with('assets/reviewed.png')
    def test_review_flag_allows_originals_but_not_unreviewed_icon(self):
        copy=Mock(side_effect=lambda ref:ref)
        row=publisher.catalog([self.item(artworkPublicSafe=True)],[],copy)[0]
        self.assertEqual(row['screenshots'],['assets/customer.png']);self.assertEqual(row['icon'],'');copy.assert_called_once_with('assets/customer.png')
    def test_publication_opt_out_is_absolute(self):
        self.assertEqual(publisher.catalog([self.item(publication={'enabled':False},artworkPublicSafe=True,iconPublicSafe=True)],[],lambda x:self.fail('Must not copy opted-out artwork')),[])
    def test_unsafe_launch_urls_are_not_published(self):
        for value in ['http://example.com','javascript:alert(1)','https://username:password@example.com','https://example.com/?secret=value','https://example.com/#private','https://localhost/app','https://127.0.0.1/app']:
            with self.subTest(url=value):self.assertEqual(publisher.catalog([self.item(publication={'url':value})],[],lambda x:x)[0]['url'],'')
        self.assertEqual(publisher.catalog([self.item(publication={'url':'https://example.com/app'})],[],lambda x:x)[0]['url'],'https://example.com/app')
    def test_public_text_rejects_obvious_paths_and_tokens(self):
        for value in ['Private /Users/name/file','Private /home/name/file','sk-proj-secret','ghp_secret','github_pat_secret']:
            self.assertEqual(publisher.public_text(value,'Fallback'),'Fallback')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir();(self.repo/'.git').mkdir();(self.repo/'public-catalog.json').write_text('[]')
        self.old_data=registry.DATA;self.old_root=registry.ROOT;registry.DATA=self.root/'private-data';registry.ROOT=self.root/'library';(registry.ROOT/'assets').mkdir(parents=True)
        self.cfg={'githubEnabled':True,'repoPath':str(self.repo),'repository':publisher.REPOSITORY}
    def tearDown(self):registry.DATA=self.old_data;registry.ROOT=self.old_root;self.tmp.cleanup()
    def git_response(self,repo,*args):
        if args[:2]==('remote','get-url'):return 'https://github.com/CarlosMabrey/rea-library.git'
        if args==('branch','--show-current'):return 'main'
        if args[0]=='rev-parse':return 'abc123'
        return ''
    def test_publication_refuses_wrong_remote_before_copy_or_network(self):
        with patch.object(pipeline,'config',return_value=self.cfg),patch.object(publisher,'git',return_value='https://github.com/other/repository.git') as git,patch.object(publisher.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'remote'):publisher.publish_library()
            self.assertEqual(git.call_count,1);run.assert_not_called()
    def test_publication_refuses_existing_staged_changes(self):
        def git(repo,*args):
            if args==('diff','--cached','--name-only'):return 'private.txt'
            return self.git_response(repo,*args)
        with patch.object(pipeline,'config',return_value=self.cfg),patch.object(publisher,'git',side_effect=git) as calls,patch.object(publisher.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'unstage'):publisher.publish_library()
            self.assertFalse(any(c.args[1]=='fetch' for c in calls.call_args_list));run.assert_not_called()
    def test_asset_escape_rejected_before_static_export(self):
        (self.root/'secret.png').write_bytes(b'private')
        item=self.item(icon='../../secret.png',iconPublicSafe=True)
        with patch.object(pipeline,'config',return_value=self.cfg),patch.object(publisher,'git',side_effect=self.git_response),patch.object(registry,'apps',return_value=[item]),patch.object(publisher.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'inside'):publisher.publish_library()
            run.assert_not_called()
    def test_symlink_asset_escape_rejected(self):
        (self.root/'secret.png').write_bytes(b'private');(registry.ROOT/'assets'/'leak.png').symlink_to(self.root/'secret.png')
        with patch.object(pipeline,'config',return_value=self.cfg),patch.object(publisher,'git',side_effect=self.git_response),patch.object(registry,'apps',return_value=[self.item(icon='assets/leak.png',iconPublicSafe=True)]),patch.object(publisher.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'inside'):publisher.publish_library()
            run.assert_not_called()
    def test_mismatched_local_head_refused(self):
        def git(repo,*args):
            if args==('rev-parse','origin/main'):return 'remote123'
            return self.git_response(repo,*args)
        with patch.object(pipeline,'config',return_value=self.cfg),patch.object(publisher,'git',side_effect=git),patch.object(publisher.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'differs'):publisher.publish_library()
            run.assert_not_called()
if __name__=='__main__':unittest.main()
