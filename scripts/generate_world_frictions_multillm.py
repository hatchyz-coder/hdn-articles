#!/usr/bin/env python3
"""Provider-resilient World Frictions runner."""
from __future__ import annotations
import json, os, re, time
from typing import Any
import requests
import generate_world_frictions as core

def _json_from_text(text:str)->dict[str,Any]:
    cleaned=re.sub(r"^```(?:json)?\s*|\s*```$","",(text or "").strip(),flags=re.I|re.S)
    if not cleaned: raise RuntimeError("provider response did not contain output text")
    value=json.loads(cleaned)
    if not isinstance(value,dict): raise RuntimeError("provider JSON response must be an object")
    return value

def _synthetic_payload(text:str,urls:list[str])->dict[str,Any]:
    sources=[{"url":u} for u in sorted({u for u in urls if isinstance(u,str) and u.startswith("https://")})]
    return {"output_text":text,"output":[{"type":"web_search_call","action":{"sources":sources}}] if sources else []}

def _gemini_call(*,instructions:str,input_text:str,max_output_tokens:int,web_search:bool):
    key=os.getenv("GEMINI_API_KEY")
    if not key: raise RuntimeError("GEMINI_API_KEY is not configured")
    model=os.getenv("WORLD_FRICTIONS_GEMINI_MODEL","gemini-2.5-flash")
    body={"systemInstruction":{"parts":[{"text":instructions}]},"contents":[{"role":"user","parts":[{"text":input_text}]}],"generationConfig":{"responseMimeType":"application/json","maxOutputTokens":max_output_tokens}}
    if web_search: body["tools"]=[{"google_search":{}}]
    r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",timeout=600,headers={"x-goog-api-key":key,"Content-Type":"application/json"},json=body)
    if not r.ok: raise RuntimeError(f"Gemini API failed ({r.status_code}): {r.text[:1000]}")
    p=r.json(); c=p.get("candidates") or []
    if not c: raise RuntimeError("Gemini response did not contain candidates")
    text="\n".join(str(x.get("text","")) for x in ((c[0].get("content") or {}).get("parts") or []) if isinstance(x,dict) and x.get("text")).strip(); urls=[]
    for chunk in (c[0].get("groundingMetadata") or {}).get("groundingChunks") or []:
        uri=((chunk.get("web") or {}).get("uri")) if isinstance(chunk,dict) else None
        if isinstance(uri,str): urls.append(uri)
    return _json_from_text(text),_synthetic_payload(text,urls)

def _retry_wait(r:requests.Response,attempt:int)->float:
    try:
        if r.headers.get("retry-after"): return min(max(float(r.headers["retry-after"]),1),120)
    except Exception: pass
    try:
        msg=((r.json().get("error") or {}).get("message") or ""); m=re.search(r"try again in\s+([0-9.]+)s",msg,re.I)
        if m: return min(max(float(m.group(1))+2,1),120)
    except Exception: pass
    return min(20*(attempt+1),120)

def _groq_call(*,instructions:str,input_text:str,max_output_tokens:int,web_search:bool):
    key=os.getenv("GROQ_API_KEY")
    if not key: raise RuntimeError("GROQ_API_KEY is not configured")
    model=(
        os.getenv("WORLD_FRICTIONS_GROQ_RESEARCH_MODEL","groq/compound-mini")
        if web_search else
        os.getenv("WORLD_FRICTIONS_GROQ_WRITER_MODEL","openai/gpt-oss-20b")
    )
    request_text=("Use built-in web search. Return raw JSON only. Every source URL included in JSON must come from actual web research. Be concise while preserving required fields.\n\n"+input_text) if web_search else input_text
    token_cap=1800 if model.startswith("groq/compound") else 5000
    body={"model":model,"messages":[{"role":"system","content":instructions},{"role":"user","content":request_text}],"max_completion_tokens":min(max_output_tokens,token_cap)}
    if model.startswith("groq/compound"):
        # Compound already promises a synthesized response. Avoid response_format and
        # visit_website here: both inflate the internal agent request and previously
        # caused a 413 before the compact discovery response was returned.
        if web_search:
            body["compound_custom"]={"tools":{"enabled_tools":["web_search"]}}
            body["search_settings"]={"country":"japan"}
    else:
        body["response_format"]={"type":"json_object"}
    response=None
    for attempt in range(4):
        response=requests.post("https://api.groq.com/openai/v1/chat/completions",timeout=600,headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","Groq-Model-Version":"latest"},json=body)
        if response.ok: break
        if response.status_code!=429: raise RuntimeError(f"Groq API failed ({response.status_code}): {response.text[:1000]}")
        wait=_retry_wait(response,attempt); print(f"GROQ_RATE_LIMIT: waiting {wait:.1f}s before retry {attempt+2}/4"); time.sleep(wait)
    if response is None or not response.ok: raise RuntimeError(f"Groq API failed ({response.status_code if response else 'unknown'}): {response.text[:1000] if response else 'no response'}")
    payload=response.json(); choices=payload.get("choices") or []
    if not choices: raise RuntimeError("Groq response did not contain choices")
    message=choices[0].get("message") or {}; text=str(message.get("content") or "").strip(); urls=[]
    for tool in message.get("executed_tools") or []:
        if not isinstance(tool,dict): continue
        sr=tool.get("search_results") or {}; results=sr.get("results") if isinstance(sr,dict) else None
        if isinstance(results,list):
            for item in results:
                if isinstance(item,dict) and isinstance(item.get("url"),str): urls.append(item["url"])
    return _json_from_text(text),_synthetic_payload(text,urls)

def _openai_call(*,model:str,instructions:str,input_text:str,max_output_tokens:int,web_search:bool):
    return core._ORIGINAL_CALL_OPENAI(model=model,instructions=instructions,input_text=input_text,max_output_tokens=max_output_tokens,web_search=web_search)

def _provider_chain(): return [x.strip().lower() for x in os.getenv("WORLD_FRICTIONS_PROVIDER_CHAIN","groq").split(",") if x.strip()]

def provider_call_openai(*,model:str,instructions:str,input_text:str,max_output_tokens:int,web_search:bool):
    errors=[]
    for provider in _provider_chain():
        try:
            if provider=="gemini": return _gemini_call(instructions=instructions,input_text=input_text,max_output_tokens=max_output_tokens,web_search=web_search)
            if provider=="groq": return _groq_call(instructions=instructions,input_text=input_text,max_output_tokens=max_output_tokens,web_search=web_search)
            if provider=="openai": return _openai_call(model=model,instructions=instructions,input_text=input_text,max_output_tokens=max_output_tokens,web_search=web_search)
            errors.append(f"{provider}: unsupported provider")
        except Exception as exc: errors.append(f"{provider}: {exc}"); print(f"PROVIDER_FAIL: {provider}: {exc}")
    reason="All configured World Frictions providers failed: "+" | ".join(errors); core.write_github_output(publish="false",reason=reason,score=0); core.write_summary(["## World Frictions provider failure","",reason]); raise RuntimeError(reason)

def main()->int:
    core._ORIGINAL_CALL_OPENAI=core.call_openai; core.call_openai=provider_call_openai; return core.main()
if __name__=="__main__": raise SystemExit(main())
