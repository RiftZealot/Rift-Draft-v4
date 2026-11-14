const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/../site/index.html','utf8');const code=html.split('<script>')[1].split('</script>')[0];
const nodes=new Map();
function elm(){return {innerHTML:'',textContent:'',value:'',style:{},checked:false,files:[],querySelectorAll:()=>[],classList:{toggle(){}}};}
const ctx=vm.createContext({
 document:{getElementById:(id)=>{if(!nodes.has(id))nodes.set(id,elm());return nodes.get(id)},querySelectorAll:()=>[],addEventListener:()=>{},createElement:()=>elm(),visibilityState:'visible'},
 localStorage:{getItem:()=>null,setItem:()=>{}},setInterval:()=>{},clearInterval:()=>{},
 navigator:{clipboard:{writeText:async()=>{}}},console,
 fetch:async()=>({ok:false,status:404,json:async()=>({})}),
 alert:()=>{},confirm:()=>false,URL:{createObjectURL:()=>'',revokeObjectURL:()=>{}},Blob:class {},setTimeout:()=>{},
});
vm.runInContext(code,ctx);
vm.runInContext(`
manifest={riot_patch:'16.22',recent:{top:{available:true,patch:'16.22'}},history:{top:{available:true}},ranks:{diamond_plus:{top:{available:true,patch:'16.22',sample_matches:400}}}};
payload.recent.top={patch:'16.22',tierlist:{'122':{wr:53,pr:10,games:1000},'114':{wr:48,pr:7,games:900}},matchups:{'122':{top:{'114':{d2:4,games:200}}},'114':{top:{'122':{d2:-4,games:200}}}}};
payload.history.top={tierlist:{'122':{wr:53,pr:10,games:1000},'114':{wr:48,pr:7,games:900}},matchups:{}};
state.pools.top=['122','114'];state.rankBracket='default';render();`,ctx);
let baseline=nodes.get('rankings').innerHTML;
assert(baseline.includes('Darius')&&baseline.includes('Fiora')&&!baseline.includes('UNRATED'));
vm.runInContext(`state.rankBracket='master_plus';render();`,ctx);
assert(nodes.get('rankings').innerHTML.includes('UNRATED'));
assert(nodes.get('rankNotice').textContent.includes('Rankings are intentionally unavailable'));
vm.runInContext(`
rankPayload.diamond_plus={top:{patch:'16.22',rank_bracket:'diamond_plus',region:'NA1',sample_matches:400,tierlist:{'122':{wr:42,pr:10,games:400},'114':{wr:58,pr:15,games:400}},matchups:{'122':{top:{'114':{d2:-9,games:180}}},'114':{top:{'122':{d2:9,games:180}}}}}};
state.rankBracket='diamond_plus';render();`,ctx);
let diamond=nodes.get('rankings').innerHTML;
assert(diamond.includes('Rank-adjusted 56.4%'),diamond.slice(0,400));
assert(diamond.indexOf('Fiora')<diamond.indexOf('Darius'));
vm.runInContext(`state.enemies.top='122';render();`,ctx);
assert(!nodes.get('rankings').innerHTML.includes('Blind '),'Blind penalty should vanish when lane is known');
vm.runInContext(`state.rankBracket='master_plus';render();`,ctx);
assert(nodes.get('rankings').innerHTML.includes('UNRATED'));
vm.runInContext(`view='data';renderHealth();`,ctx);assert(nodes.get('dataSummary').innerHTML.includes('Rank-based datasets'));
console.log('JAVASCRIPT LOGIC: PASS (baseline, no-rank abstention, actual rank ranking, blind risk)');
