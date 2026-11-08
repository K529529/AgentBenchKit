/* Offline DOM contracts: no browser, network or live evaluation data. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(dataset={}) { this.dataset=dataset; this.value=''; this.checked=false; this.hidden=false; this.handlers={}; this.textContent=''; }
  addEventListener(type,fn){this.handlers[type]=fn;}
  setAttribute(){}
  fire(type){this.handlers[type]?.();}
}
const rows=Array.from({length:50},(_,i)=>new Element({search:`repo-task-${i}`,status:i%2?'pass':'fail',agent:'COMPLETED',execution:'FINISHED',verifier:i%2?'PASS':'FAIL',investigate:i%2?'0':'1',duration:String(i),tokens:String(50-i)}));
const parent={order:[],append(row){this.order=this.order.filter(x=>x!==row);this.order.push(row);}};rows.forEach(r=>r.parentNode=parent);
const input=new Element();const prev=new Element();const next=new Element();const label=new Element();const sort=new Element();const investigate=new Element();investigate.type='checkbox';const count=new Element();const empty=new Element();
const controls={'[data-search-input]':input,'[data-filter-count]':count,'[data-filter-empty]':empty,'[data-matrix-sort]':sort,'[data-matrix-investigate]':investigate,'[data-page-prev]':prev,'[data-page-next]':next,'[data-matrix-page]':label};
const panel=new Element();panel.querySelector=s=>controls[s]||null;panel.querySelectorAll=s=>s==='[data-result-row]'?rows:s.includes('.matrix-extra')?[sort,investigate]:[];
const listeners={};const memory={};const context={document:{querySelectorAll:s=>s==='[data-result-filter]'?[panel]:[],addEventListener:(t,fn)=>(listeners[t]??=[]).push(fn)},location:{pathname:'/runs/offline'},sessionStorage:{getItem:k=>memory[k],setItem:(k,v)=>memory[k]=v}};
vm.runInNewContext(fs.readFileSync('src/agentbenchkit/viewer/static/viewer.js','utf8'),context);
listeners.DOMContentLoaded.forEach(fn=>fn());
const visible=()=>rows.filter(r=>!r.hidden);
assert.equal(visible().length,25);assert.equal(visible()[0],rows[0]);
next.fire('click');assert.equal(visible()[0],rows[25]);assert.equal(next.disabled,true);
input.value='repo-task-49';input.fire('input');assert.deepEqual(visible(),[rows[49]]);
input.value='';input.fire('input');investigate.checked=true;investigate.fire('input');assert.equal(visible().length,25);assert.ok(visible().every(r=>r.dataset.verifier==='FAIL'));
investigate.checked=false;investigate.fire('input');sort.value='duration';sort.fire('input');assert.equal(parent.order[0],rows[49]);assert.equal(rows[49].hidden,false);assert.equal(rows[0].hidden,true);
assert.ok(Object.values(memory)[0].includes('duration'));
console.log('PASS: offline matrix pagination, keyword search, investigation filter, sort and persisted state');
