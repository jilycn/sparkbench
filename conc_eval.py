#!/usr/bin/env python3
"""Concurrency CORRECTNESS test: 4 parallel workers x 5 sequential exact-answer questions.
Usage: conc_eval.py <label> <out_dir>"""
import json, os, random, re, sys, threading, time, urllib.request, urllib.error

BASE="http://localhost:8000/v1/chat/completions"
MODEL=os.environ.get("SPARKBENCH_MODEL", "local-ai")
random.seed(20260712)

# 20 unique arithmetic tasks with exact integer answers
TASKS=[]
for i in range(20):
    a=random.randint(120,999); b=random.randint(12,99); c=random.randint(100,999)
    TASKS.append({"q":f"Compute {a}*{b}+{c}. Think if needed, then reply with ONLY the final integer on the last line.",
                  "answer":a*b+c})

def post(question):
    body=json.dumps({"model":MODEL,"messages":[{"role":"user","content":question}],
                     "temperature":0.6,"top_p":0.95,"top_k":20,"max_tokens":8000}).encode()
    req=urllib.request.Request(BASE,data=body,headers={"Content-Type":"application/json","Authorization":"Bearer dummy"})
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=600) as r:
            d=json.loads(r.read()); return d,time.time()-t,None
    except urllib.error.HTTPError as e:
        return None,time.time()-t,f"HTTP {e.code}"
    except Exception as e:
        return None,time.time()-t,f"ERR {e}"

results=[None]*20
def worker(w):
    for k in range(5):
        idx=w*5+k
        d,dt,err=post(TASKS[idx]["q"])
        rec={"idx":idx,"worker":w,"seconds":round(dt,1),"error":err,"correct":False}
        if not err:
            content=(d["choices"][0]["message"].get("content") or "")
            nums=re.findall(r"-?\d+",content.replace(",",""))
            rec["got"]=int(nums[-1]) if nums else None
            rec["correct"]=(rec["got"]==TASKS[idx]["answer"])
            rec["finish_reason"]=d["choices"][0].get("finish_reason")
        results[idx]=rec

def main():
    label=sys.argv[1]; out=sys.argv[2]
    os.makedirs(out,exist_ok=True)
    t0=time.time()
    threads=[threading.Thread(target=worker,args=(w,)) for w in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    wall=round(time.time()-t0,1)
    correct=sum(1 for r in results if r and r["correct"])
    errors=sum(1 for r in results if r and r["error"])
    lat=[r["seconds"] for r in results if r]
    summary={"label":label,"correct":correct,"total":20,"http_errors":errors,
             "wall_seconds":wall,"lat_min":min(lat),"lat_max":max(lat),
             "lat_avg":round(sum(lat)/len(lat),1),"results":results}
    json.dump(summary,open(os.path.join(out,"conc_results.json"),"w"),indent=2)
    print(f"conc done: {label} correct={correct}/20 errors={errors} wall={wall}s avg_lat={summary['lat_avg']}s")

if __name__=="__main__":
    main()
