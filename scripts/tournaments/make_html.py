#!/usr/bin/env python3
"""Build a self-contained, filterable tournaments.html from tournaments.json (no network, no deps).
Usage: python3 make_html.py [path/to/tournaments.json] [path/to/tournaments.html]"""
import json, os, re, sys, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))

def map_query(t):
    st = t.get("state") or "TX"; city = (t.get("city") or "").strip(); venue = (t.get("venue") or "").strip()
    if venue:
        q = venue
        if city and city.lower() not in venue.lower(): q += ", " + city
        if not re.search(r"\b" + st + r"\b", q): q += ", " + st
        return q
    return f"{city}, {st}" if city else ""

def div_keys(t):
    """Normalized age-division buckets (e.g. 8U, 10U, 14U, HS) from non-girls divisions, for the multi-select."""
    src = t.get("open_divisions")
    if src is None: src = [d for d in (t.get("divisions") or "").split(";") if d.strip()]
    keys = set()
    for d in src:
        for m in re.finditer(r"\b(\d{1,2})\s*-?\s*u\b", d, re.I): keys.add(f"{int(m.group(1))}U")
        if re.search(r"high school|\bhs\b|\b18u\b|senior", d, re.I): keys.add("HS")
        if re.search(r"middle school|\bms\b", d, re.I): keys.add("MS")
        if re.search(r"adult|\bmen'?s\b|open", d, re.I): keys.add("Adult/Open")
        g = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s*grade", d, re.I)
        if g: keys.add(f"Grade {g.group(1)}")
    if not keys and t.get("age_groups"):
        for m in re.finditer(r"\b(\d{1,2})u\b", t["age_groups"], re.I): keys.add(f"{int(m.group(1))}U")
    return sorted(keys)

def build(json_path=None, html_path=None):
    json_path = json_path or os.path.join(HERE, "tournaments.json")
    html_path = html_path or os.path.join(HERE, "tournaments.html")
    data = json.load(open(json_path))
    rows = []
    for t in data["tournaments"]:
        m = re.search(r"\$([\d,]+(?:\.\d+)?)", t.get("entry_fee") or "")
        rows.append({**t, "category": t.get("category") or "7v7", "fee": float(m.group(1).replace(",", "")) if m else None,
                     "clone": "(clone)" in (t.get("name") or "").lower(),
                     "has_girls_divisions": bool(t.get("has_girls_divisions")),
                     "divs": div_keys(t), "mapq": map_query(t)})
    gen = data.get("generated", "")
    try: gen_h = dt.datetime.fromisoformat(gen).strftime("%b %-d, %Y %-I:%M %p") + " CT"
    except Exception: gen_h = gen
    payload = json.dumps({"generated": gen_h, "window": data.get("window"), "rows": rows})
    payload = payload.replace("</", "<\\/").replace("<!--", "<\\!--")
    html = TEMPLATE.replace("__DATA__", payload).replace("__COUNT__", str(len(rows)))
    open(html_path, "w").write(html)
    return html_path, len(rows)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Texas 7v7 &amp; Flag Football Tournaments</title>
<style>
:root{--bg:#f5f7fb;--card:#fff;--ink:#1c2433;--mute:#667085;--line:#e4e7ec;--acc:#1e3a8a;--acc2:#2563eb;--tag:#eef2ff}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#1e3a8a,#2563eb);color:#fff;padding:18px 20px}
header h1{margin:0;font-size:22px}header p{margin:4px 0 0;opacity:.85;font-size:13px}
main{max-width:1250px;margin:0 auto;padding:16px}
.filters{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.filters label{display:flex;flex-direction:column;font-size:12px;font-weight:600;color:var(--mute);gap:4px}
.filters input,.filters select{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink)}
.fl{display:flex;flex-direction:column;gap:4px;position:relative}.lab{font-size:12px;font-weight:600;color:var(--mute)}
.ms{position:relative}.msb{width:100%;display:flex;justify-content:space-between;align-items:center;text-align:left;padding:7px 9px;color:var(--ink)}
.msb.act{border-color:var(--acc2);background:#eff6ff;font-weight:600}.car{opacity:.6;margin-left:6px}
.msp{position:absolute;z-index:20;top:calc(100% + 4px);left:0;min-width:100%;width:max-content;max-width:min(320px,92vw);background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);padding:8px}
.mss{width:100%;margin-bottom:6px}.msa{display:flex;gap:6px;margin-bottom:6px}.msa button{padding:4px 9px;font-size:12.5px}
.msl{max-height:260px;overflow:auto}.msi{display:flex!important;flex-direction:row!important;align-items:center;gap:8px;padding:5px 4px;font-size:14px!important;font-weight:500!important;color:var(--ink)!important;cursor:pointer;border-radius:6px}
.msi:hover{background:#f3f4f6}.msi[hidden]{display:none!important}.msn{color:var(--mute);font-size:12px;margin-left:auto}
.tag.girl{background:#fce7f3;color:#9d174d}a.dir{font-size:12px;font-weight:500;margin-left:6px}
.checks{display:flex;flex-direction:column;gap:6px;justify-content:center}
.checks label{flex-direction:row;align-items:center;gap:8px;font-weight:500;color:var(--ink);font-size:14px}
.bar{display:flex;justify-content:space-between;align-items:center;margin:14px 2px 8px;gap:10px;flex-wrap:wrap}
#count{font-weight:700}button{font:inherit;padding:7px 12px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer}
button:hover{border-color:var(--acc2)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f9fafb;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--mute);white-space:nowrap}
th.sort{cursor:pointer;user-select:none}th.sort:hover{color:var(--acc2)}th .ar{opacity:.7}
tr:hover td{background:#fafbff}a{color:var(--acc2);text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.sub{color:var(--mute);font-size:12.5px}.tag{display:inline-block;background:var(--tag);color:var(--acc);border-radius:999px;padding:1px 8px;font-size:11.5px;margin:2px 4px 0 0}
.fmt{display:flex;flex-wrap:wrap;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:12px}
.fmtl{font-weight:700;margin-right:4px}.seg{font-weight:600;border-radius:999px;padding:8px 16px}.seg .n{opacity:.7;font-weight:500}
.seg.on{background:var(--acc);color:#fff;border-color:var(--acc)}.ex{display:flex;align-items:center;gap:6px;font-size:14px;margin-left:auto}
.badge{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11.5px;font-weight:700;margin-right:6px;vertical-align:1px}
.b7v7{background:#dbeafe;color:#1e40af}.bflag{background:#dcfce7;color:#166534}.bboth{background:#f3e8ff;color:#6b21a8}
.tag.warn{background:#fff4e5;color:#9a5b00}.nowrap{white-space:nowrap}.empty{padding:30px;text-align:center;color:var(--mute)}
@media(max-width:760px){thead{display:none}table,tbody,tr,td{display:block;width:100%}tr{border-bottom:8px solid var(--bg)}td{border:0;padding:4px 12px}
td:first-child{padding-top:12px}td:last-child{padding-bottom:12px}td[data-l]:before{content:attr(data-l)": ";font-weight:600;color:var(--mute);font-size:12px}}
</style></head><body>
<header><h1>Texas 7v7 &amp; Flag Youth Football Tournaments</h1>
<p>Sources: Zorts Sports + Flag50 &middot; <span id="upd"></span> &middot; <span id="win"></span></p></header>
<main>
<section class="fmt" role="group" aria-label="Format">
 <span class="fmtl">Format</span>
 <button type="button" class="seg" data-f="all">Both (all) <span class="n"></span></button>
 <button type="button" class="seg" data-f="7v7">7v7 / 7on7 <span class="n"></span></button>
 <button type="button" class="seg" data-f="flag">Flag <span class="n"></span></button>
 <label class="ex"><input id="excl" type="checkbox"> Exclude events that have both formats</label>
</section>
<section class="filters">
 <label>Search<input id="q" type="search" placeholder="Name, organizer, venue"></label>
 <div class="fl"><span class="lab">Divisions</span><div class="ms" id="ms-div"></div></div>
 <div class="fl"><span class="lab">Cities</span><div class="ms" id="ms-city"></div></div>
 <div class="fl"><span class="lab">Months</span><div class="ms" id="ms-month"></div></div>
 <label>From<input id="from" type="date"></label>
 <label>To<input id="to" type="date"></label>
 <label>Max entry fee ($)<input id="fee" type="number" min="0" step="25" placeholder="Any"></label>
 <div class="checks">
  <label><input id="nogirls" type="checkbox"> Hide tournaments with girls divisions</label>
  <label><input id="noclone" type="checkbox" checked> Hide “(clone)” duplicates</label>
 </div>
</section>
<div class="bar"><div><span id="count"></span></div><button id="reset" type="button">Reset filters</button></div>
<table><thead><tr>
 <th class="sort" data-k="start_date">Date <span class="ar"></span></th>
 <th class="sort" data-k="name">Tournament <span class="ar"></span></th>
 <th class="sort" data-k="city">City / Venue <span class="ar"></span></th>
 <th>Divisions</th>
 <th class="sort" data-k="fee">Fee <span class="ar"></span></th>
 <th>Contact</th>
</tr></thead><tbody id="tb"></tbody></table>
<p class="sub" style="margin-top:10px">Girls-only tournaments are excluded. Tap a city to open it in Google Maps (distance from your location); “Directions” opens a route.</p>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
"use strict";
var D=JSON.parse(document.getElementById("data").textContent),R=D.rows;
var $=function(id){return document.getElementById(id)};
var MN=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function fd(s){var p=s.split("-");return MN[+p[1]-1]+" "+(+p[2])+", "+p[0]}
function dr(a,b){if(!b||a===b)return fd(a);var pa=a.split("-"),pb=b.split("-");
 if(pa[0]===pb[0]&&pa[1]===pb[1])return MN[+pa[1]-1]+" "+(+pa[2])+"–"+(+pb[2])+", "+pa[0];return fd(a)+" – "+fd(b)}
$("upd").textContent="Last updated "+(D.generated||"unknown");
if(D.window)$("win").textContent="Events starting "+fd(D.window[0])+" – "+fd(D.window[1]);
function cityOf(r){return r.city||"(unspecified)"}
function divOrder(a){var m=/^(\d+)U$/.exec(a);if(m)return +m[1];if(a==="MS")return 14.5;if(a==="HS")return 19;var g=/Grade (\d+)/.exec(a);if(g)return 30+(+g[1]);return 99}
/* multi-select dropdown */
var openMS=null;
function MS(el,label,items,fmtLbl,search){
 var sel=new Set(),self={sel:sel};
 el.innerHTML='<button type="button" class="msb"><span class="mst"></span><span class="car">▾</span></button>'+
  '<div class="msp" hidden>'+(search?'<input type="search" class="mss" placeholder="Search '+label.toLowerCase()+'…">':'')+
  '<div class="msa"><button type="button" data-a="all">Select all</button><button type="button" data-a="none">Clear</button></div><div class="msl"></div></div>';
 var btn=el.querySelector(".msb"),pan=el.querySelector(".msp"),lst=el.querySelector(".msl"),ss=el.querySelector(".mss");
 lst.innerHTML=items.map(function(v){return '<label class="msi"><input type="checkbox" value="'+esc(v)+'"> <span>'+esc(fmtLbl(v))+'</span> <span class="msn" data-v="'+esc(v)+'"></span></label>'}).join("");
 function txt(){var n=sel.size;el.querySelector(".mst").textContent=n===0?"All "+label.toLowerCase():n===1?fmtLbl(Array.from(sel)[0]):n+" "+label.toLowerCase()+" selected";btn.classList.toggle("act",n>0)}
 function vis(){return Array.from(lst.querySelectorAll(".msi")).filter(function(l){return !l.hidden})}
 btn.addEventListener("click",function(e){e.stopPropagation();var o=pan.hidden;if(openMS&&openMS!==self)openMS.close();pan.hidden=!o;openMS=o?self:null;if(o&&ss)ss.focus()});
 pan.addEventListener("click",function(e){e.stopPropagation()});
 lst.addEventListener("change",function(e){var v=e.target.value;if(e.target.checked)sel.add(v);else sel.delete(v);txt();render()});
 el.querySelector('[data-a="all"]').addEventListener("click",function(){vis().forEach(function(l){var c=l.querySelector("input");c.checked=true;sel.add(c.value)});txt();render()});
 el.querySelector('[data-a="none"]').addEventListener("click",function(){self.clear();render()});
 if(ss)ss.addEventListener("input",function(){var q=ss.value.trim().toLowerCase();lst.querySelectorAll(".msi").forEach(function(l){l.hidden=q&&l.textContent.toLowerCase().indexOf(q)<0})});
 self.close=function(){pan.hidden=true;if(openMS===self)openMS=null};
 self.clear=function(){sel.clear();lst.querySelectorAll("input").forEach(function(c){c.checked=false});if(ss){ss.value="";lst.querySelectorAll(".msi").forEach(function(l){l.hidden=false})}txt()};
 self.counts=function(fn){lst.querySelectorAll(".msn").forEach(function(s){s.textContent="("+fn(s.dataset.v)+")"})};
 txt();return self}
document.addEventListener("click",function(){if(openMS)openMS.close()});
document.addEventListener("keydown",function(e){if(e.key==="Escape"&&openMS)openMS.close()});
var divs=Array.from(new Set([].concat.apply([],R.map(function(r){return r.divs||[]})))).sort(function(a,b){return divOrder(a)-divOrder(b)||(a<b?-1:1)});
var cities=Array.from(new Set(R.map(cityOf))).sort();
var months=Array.from(new Set(R.map(function(r){return r.start_date.slice(0,7)}))).sort();
var mDiv=MS($("ms-div"),"Divisions",divs,function(v){return v},false);
var mCity=MS($("ms-city"),"Cities",cities,function(v){return v},true);
var mMon=MS($("ms-month"),"Months",months,function(m){return MN[+m.slice(5)-1]+" "+m.slice(0,4)},false);
var sk="start_date",sd=1,fmt="all";
var BADGE={"7v7":'<span class="badge b7v7">7v7</span>',"flag":'<span class="badge bflag">FLAG</span>',"both":'<span class="badge bboth">7v7 + FLAG</span>'};
document.querySelectorAll(".seg").forEach(function(b){b.addEventListener("click",function(){fmt=b.dataset.f;render()})});
function mapU(r){return "https://www.google.com/maps/search/?api=1&query="+encodeURIComponent(r.mapq)}
function dirU(r){return "https://www.google.com/maps/dir/?api=1&destination="+encodeURIComponent(r.mapq)}
function pass(r,skip){
 var q=$("q").value.trim().toLowerCase(),f=$("from").value,t=$("to").value,fee=$("fee").value===""?null:+$("fee").value;
 if(q&&(r.name+" "+r.organizer+" "+r.venue+" "+r.city).toLowerCase().indexOf(q)<0)return false;
 if(skip!=="div"&&mDiv.sel.size&&!(r.divs||[]).some(function(d){return mDiv.sel.has(d)}))return false;
 if(skip!=="city"&&mCity.sel.size&&!mCity.sel.has(cityOf(r)))return false;
 if(skip!=="mon"&&mMon.sel.size&&!mMon.sel.has(r.start_date.slice(0,7)))return false;
 if(f&&(r.end_date||r.start_date)<f)return false;
 if(t&&r.start_date>t)return false;
 if(fee!==null&&(r.fee==null||r.fee>fee))return false;
 if($("nogirls").checked&&r.has_girls_divisions)return false;
 if($("noclone").checked&&r.clone)return false;
 if(skip!=="fmt"){var ex=$("excl").checked;
  if(fmt==="7v7"&&r.category==="flag")return false;
  if(fmt==="flag"&&r.category==="7v7")return false;
  if(ex&&fmt!=="all"&&r.category==="both")return false}
 return true}
function render(){
 var out=R.filter(function(r){return pass(r)}),ex=$("excl").checked;
 var base=R.filter(function(r){return pass(r,"fmt")});
 document.querySelectorAll(".seg").forEach(function(b){b.classList.toggle("on",b.dataset.f===fmt);b.setAttribute("aria-pressed",b.dataset.f===fmt);
  var f=b.dataset.f;b.querySelector(".n").textContent="("+base.filter(function(r){return f==="all"||r.category===f||(r.category==="both"&&!(ex&&f!=="all"))}).length+")"});
 var bd=R.filter(function(r){return pass(r,"div")}),bc=R.filter(function(r){return pass(r,"city")}),bm=R.filter(function(r){return pass(r,"mon")});
 mDiv.counts(function(v){return bd.filter(function(r){return (r.divs||[]).indexOf(v)>=0}).length});
 mCity.counts(function(v){return bc.filter(function(r){return cityOf(r)===v}).length});
 mMon.counts(function(v){return bm.filter(function(r){return r.start_date.slice(0,7)===v}).length});
 out.sort(function(a,b){var x=a[sk],y=b[sk];
  if(x==null&&y==null)return 0;if(x==null)return 1;if(y==null)return -1;
  if(typeof x==="string"){x=x.toLowerCase();y=y.toLowerCase()}
  return (x<y?-1:x>y?1:(a.start_date<b.start_date?-1:a.start_date>b.start_date?1:0))*sd});
 document.querySelectorAll("th.sort").forEach(function(th){th.querySelector(".ar").textContent=th.dataset.k===sk?(sd>0?"▲":"▼"):""});
 $("count").textContent=out.length+" of "+R.length+" tournaments";
 $("tb").innerHTML=out.length?out.map(function(r){
  var tags="";if(r.verified)tags+='<span class="tag">✓ on Zorts + Flag50</span>';
  if(r.has_girls_divisions)tags+='<span class="tag girl" title="'+esc((r.girls_divisions||[]).join("; "))+'">+ girls divisions</span>';
  if(r.flag50_url&&r.flag50_url!==r.event_url)tags+='<a class="tag" href="'+esc(r.flag50_url)+'" target="_blank" rel="noopener">Flag50 page</a>';
  if(r.conflicts)tags+='<span class="tag warn" title="'+esc(r.conflicts)+'">sources differ</span>';
  if(r.clone)tags+='<span class="tag warn">clone</span>';
  var regs=r.registration_ends?'<div class="sub">Reg. ends '+esc(r.registration_ends)+'</div>':"";
  var where=r.mapq?'<a href="'+esc(mapU(r))+'" target="_blank" rel="noopener" title="Open in Google Maps">📍 '+esc(r.city||"Map")+'</a> <a class="dir" href="'+esc(dirU(r))+'" target="_blank" rel="noopener">Directions</a>':'<strong>'+esc(r.city||"—")+'</strong>';
  var dv=(r.open_divisions?r.open_divisions.join("; "):r.divisions)||r.age_groups||"";
  return "<tr>"+
  '<td class="nowrap" data-l="Date">'+esc(dr(r.start_date,r.end_date))+"</td>"+
  '<td>'+BADGE[r.category]+'<a href="'+esc(r.event_url)+'" target="_blank" rel="noopener">'+esc(r.name)+'</a><div class="sub">'+esc(r.organizer)+"</div>"+tags+"</td>"+
  '<td data-l="Where">'+where+'<div class="sub">'+esc(r.venue)+"</div></td>"+
  '<td data-l="Divisions"><div class="sub">'+esc(dv)+'</div><div class="sub">'+esc(r.sport)+"</div></td>"+
  '<td class="nowrap" data-l="Fee">'+(r.fee!=null?"$"+r.fee.toFixed(0):"—")+regs+"</td>"+
  '<td data-l="Contact"><div class="sub">'+esc(r.contact_email)+"</div><div class=\"sub\">"+esc(r.contact_phone)+"</div></td></tr>"}).join("")
  :'<tr><td colspan="6" class="empty">No tournaments match these filters.</td></tr>';
}
document.querySelectorAll("th.sort").forEach(function(th){th.addEventListener("click",function(){
 if(sk===th.dataset.k)sd=-sd;else{sk=th.dataset.k;sd=1}render()})});
["q","fee","from","to"].forEach(function(id){$(id).addEventListener("input",render)});
["excl","noclone","nogirls"].forEach(function(id){$(id).addEventListener("change",render)});
$("reset").addEventListener("click",function(){["q","fee","from","to"].forEach(function(id){$(id).value=""});
 mDiv.clear();mCity.clear();mMon.clear();$("excl").checked=false;$("nogirls").checked=false;fmt="all";$("noclone").checked=true;sk="start_date";sd=1;render()});
render();
})();
</script></body></html>
"""

if __name__ == "__main__":
    p, n = build(*(sys.argv[1:3]))
    print(f"wrote {p} ({n} tournaments)")
