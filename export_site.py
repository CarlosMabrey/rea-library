#!/usr/bin/env python3
"""Build the Pages catalog from explicitly curated metadata and safe artwork."""
import argparse,json,shutil,re,tempfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FILES=['index.html','app.js','style.css']
def build(output):
    output=Path(output).resolve()
    if output==ROOT or output in ROOT.parents:raise ValueError('Output must be a separate child directory.')
    if not output.is_relative_to(ROOT):raise ValueError('Export output must stay inside the repository.')
    if output.exists() and not (output/'.rea-library-export').exists():
        if output!=ROOT/'docs' or not (output/'.nojekyll').exists():raise ValueError('Refusing to replace an unmarked directory.')
    final_output=output
    output=Path(tempfile.mkdtemp(prefix='.pages-export-',dir=ROOT))
    catalog=json.loads((ROOT/'public-catalog.json').read_text())
    asset_paths=set()
    for item in catalog:
        if any(k in item for k in ['path','jobId','target','workspace','events']):raise ValueError('Private runtime fields are not exportable.')
        for ref in [item.get('icon',''),item.get('cover',''),*item.get('screenshots',[])]:
            if not ref:continue
            path=(ROOT/ref).resolve()
            if not path.is_relative_to((ROOT/'assets').resolve()) or not path.is_file():raise ValueError('Artwork must be an existing safe asset.')
            asset_paths.add(ref)
        if item.get('artworkPublicSafe') is not True and (item.get('screenshots') or item.get('cover')):raise ValueError('Private screenshots cannot be exported.')
    for filename in FILES:
        text=(ROOT/filename).read_text()
        if filename=='style.css':text=re.sub(r'@font-face\{[^}]*\}','',text)
        (output/filename).write_text(text)
    for ref in asset_paths:
        dest=output/ref;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/ref,dest)
    (output/'catalog.json').write_text(json.dumps(catalog,indent=2))
    (output/'site-config.js').write_text("window.REA_LIBRARY_CONFIG = {mode:'pages',githubUser:'CarlosMabrey',companion:'http://127.0.0.1:8765/'};\n")
    (output/'.nojekyll').write_text('')
    (output/'WORKFLOW.md').write_text((ROOT/'WORKFLOW.md').read_text())
    (output/'.rea-library-export').write_text('Generated REA Library Pages catalog.\n')
    if final_output.exists():shutil.rmtree(final_output)
    os.replace(output,final_output)
    output=final_output
    print(f'Built {len(catalog)} catalog entries with {len(asset_paths)} allowlisted assets at {output}')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'docs'));args=p.parse_args();build(args.output)
