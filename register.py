#!/usr/bin/env python3
"""Workflow hook: python3 /path/to/register.py /absolute/path/library-entry.json"""
import argparse,json,uuid
from pathlib import Path
from registry import DATA,prepare,normalize,atomic,register
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Queue an app for automatic REA Library registration.')
    p.add_argument('manifest',type=Path);a=p.parse_args()
    m=json.loads(a.manifest.read_text());item=register(m)
    print(json.dumps({'registered':True,'appId':item['id'],'automationQueued':True,'message':'Registered; artwork capture and publishing are durably queued, including while the library is offline.'}))
