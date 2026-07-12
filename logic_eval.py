#!/usr/bin/env python3
"""Round-2 Part B: 10 logic puzzles, one isolated request each. Answers parsed as JSON."""
import json, os, re, sys, time, urllib.request, urllib.error

BASE="http://localhost:8000/v1/chat/completions"
MODEL=os.environ.get("SPARKBENCH_MODEL", "local-ai")

SYS=("You are solving a logic puzzle. Reason carefully, then output your final answer as a single JSON "
     "object EXACTLY in the format requested by the puzzle, on the last line of your reply. "
     "Output nothing after the JSON object.")

def post(question):
    body=json.dumps({"model":MODEL,
                     "messages":[{"role":"system","content":SYS},{"role":"user","content":question}],
                     "temperature":0.6,"top_p":0.95,"top_k":20,"max_tokens":120000}).encode()
    req=urllib.request.Request(BASE,data=body,headers={"Content-Type":"application/json","Authorization":"Bearer dummy"})
    t=time.time()
    try:
        with urllib.request.urlopen(req,timeout=2700) as r:
            d=json.loads(r.read()); return d,time.time()-t,None
    except urllib.error.HTTPError as e:
        return None,time.time()-t,f"HTTP {e.code}: {e.read()[:200]}"
    except Exception as e:
        return None,time.time()-t,f"ERR {e}"

def extract_json(text):
    # balanced {...} block that parses; prefer the one ending LATEST, outermost on ties
    best=None; best_key=(-1,10**9)
    for m in re.finditer(r"\{",text):
        depth=0
        for j in range(m.start(),len(text)):
            if text[j]=="{": depth+=1
            elif text[j]=="}":
                depth-=1
                if depth==0:
                    try:
                        cand=json.loads(text[m.start():j+1])
                        key=(j,-m.start())
                        if key>best_key: best_key=key; best=cand
                    except Exception: pass
                    break
    return best

def main():
    LABEL=sys.argv[1]; SUITE=sys.argv[2]; OUT=sys.argv[3]
    os.makedirs(OUT,exist_ok=True)
    puzzles=json.load(open(SUITE))
    answers={}
    for p in puzzles:
        d,dt,err=post(p["q"])
        rec={"seconds":round(dt,1),"error":err,"parsed":None,"finish_reason":None,
             "completion_tokens":None,"reasoning_chars":None}
        if not err:
            ch=d["choices"][0]; msg=ch["message"]
            content=(msg.get("content") or "")
            rec["finish_reason"]=ch.get("finish_reason")
            rec["completion_tokens"]=(d.get("usage") or {}).get("completion_tokens")
            rec["reasoning_chars"]=len(msg.get("reasoning_content") or "")
            rec["parsed"]=extract_json(content)
            rec["content_tail"]=content[-400:]
        answers[p["id"]]=rec
        print(p["id"],"->",json.dumps(rec["parsed"])[:100],f"({rec['seconds']}s, fr={rec['finish_reason']})",flush=True)

    json.dump(answers,open(os.path.join(OUT,"logic_answers.json"),"w"),indent=2)
    print("logic done:",LABEL)

if __name__=="__main__":
    main()
