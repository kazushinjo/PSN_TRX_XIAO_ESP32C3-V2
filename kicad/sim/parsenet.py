import re,sys,json
s=open(sys.argv[1]).read()
tok=re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+',s)
def parse(i):
    out=[]
    while i<len(tok):
        t=tok[i]
        if t=='(':
            sub,i=parse(i+1); out.append(sub)
        elif t==')': return out,i+1
        else: out.append(t.strip('"') if t.startswith('"') else t); i+=1
    return out,i
tree,_=parse(0); root=tree[0]
def find(n,key): return [c for c in n if isinstance(c,list) and c and c[0]==key]
comps={}; desc={}
for c in find(find(root,'components')[0],'comp'):
    ref=find(c,'ref')[0][1]; comps[ref]=find(c,'value')[0][1]
    d=find(c,'description'); desc[ref]=d[0][1] if d and len(d[0])>1 else ''
pins={}
for n in find(find(root,'nets')[0],'net'):
    name=find(n,'name')[0][1]
    for nd in find(n,'node'):
        ref=find(nd,'ref')[0][1]; pin=find(nd,'pin')[0][1]; pf=find(nd,'pinfunction'); 
        pins.setdefault(ref,[]).append((pin,pf[0][1] if pf and len(pf[0])>1 else '',name))
json.dump({'comps':comps,'pins':pins,'desc':desc},open(sys.argv[2],'w'),ensure_ascii=False)
def key(r): return (re.sub(r'\d','',r),int(re.sub(r'\D','',r) or 0))
for r in sorted(comps,key=key):
    print(r,comps[r],' '.join(f"{p}{('/'+f) if f else ''}={n}" for p,f,n in sorted(pins.get(r,[]))))
