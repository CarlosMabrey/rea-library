#!/usr/bin/env python3
"""Workflow hook: python3 /path/to/register.py /absolute/path/library-entry.json"""
import argparse,json,uuid
from pathlib import Path
from registry import DATA,prepare,normalize,atomic
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Queue an app for automatic REA Library registration.')
    p.add_argument('manifest',type=Path);a=p.parse_args()
    m=json.loads(a.manifest.read_text());normalize(m);prepare()
    target=DATA/'inbox'/(str(uuid.uuid4())+'.json');atomic(target,m)
    print(json.dumps({'queued':True,'manifest':str(target),'message':'The running library will register this app automatically.'}))
