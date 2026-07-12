#!/usr/bin/env python3
"""Thinking forensics: does this serve stack ever emit reasoning_content?
Usage: think_probe.py <label> <out_dir>"""
import json, os, sys, time, urllib.request

BASE="http://localhost:8000/v1/chat/completions"
MODEL=os.environ.get("SPARKBENCH_MODEL", "local-ai")
HARD="How many positive integers n <= 200 are divisible by 3 or 5 but not both? Work it out."

CONFIGS=[
    ("default", {}),
    ("kwargs_think_true", {"chat_template_kwargs":{"enable_thinking":True}}),
    ("kwargs_think_false", {"chat_template_kwargs":{"enable_thinking":False}}),
    ("soft_switch_think", {"prefix":"/think "}),
    ("soft_switch_nothink", {"prefix":"/no_think "}),
]

def probe(extra):
    q=extra.pop("prefix","")+HARD
    body={"model":MODEL,"messages":[{"role":"user","content":q}],
          "temperature":0.6,"top_p":0.95,"top_k":20,"max_tokens":16000}
    body.update(extra)
    req=urllib.request.Request(BASE,data=json.dumps(body).encode(),
                               headers={"Content-Type":"application/json","Authorization":"Bearer dummy"})
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=900) as r:
            d=json.loads(r.read())
        ch=d["choices"][0]; msg=ch["message"]
        content=msg.get("content") or ""
        return {"seconds":round(time.time()-t,1),
                "completion_tokens":(d.get("usage") or {}).get("completion_tokens"),
                "reasoning_chars":len(msg.get("reasoning_content") or ""),
                "content_chars":len(content),
                "has_think_tag_in_content":"<think>" in content,
                "content_head":content[:150],
                "finish_reason":ch.get("finish_reason"),"error":None}
    except Exception as e:
        return {"error":str(e)[:200]}

def main():
    label=sys.argv[1]; out=sys.argv[2]
    os.makedirs(out,exist_ok=True)
    report={}
    for name,extra in CONFIGS:
        report[name]=probe(dict(extra))
        r=report[name]
        print(f"{name}: reasoning={r.get('reasoning_chars')} content={r.get('content_chars')} "
              f"tok={r.get('completion_tokens')} think_tag={r.get('has_think_tag_in_content')} err={r.get('error')}",flush=True)
    json.dump(report,open(os.path.join(out,"think_report.json"),"w"),indent=2)
    print("think probe done:",label)

if __name__=="__main__":
    main()
