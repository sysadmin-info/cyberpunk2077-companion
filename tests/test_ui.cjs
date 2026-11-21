// Dependency-free DOM stub: tests rendering/filter/refresh logic, not browser layout.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const staticDir = path.join(__dirname, '../companion/static');
const html = fs.readFileSync(path.join(staticDir, 'index.html'), 'utf8');
function element(id, tagName='DIV', classes=[]) {
  const set = new Set(classes);
  return {id, tagName, value:'', innerHTML:'', textContent:'', options:[], dataset:{}, listeners:{},
    addEventListener(event, cb){this.listeners[event]=cb;},
    scrollIntoView(){this.scrollCalls=(this.scrollCalls || 0)+1;},
    classList:{add:x=>set.add(x), remove:x=>set.delete(x), contains:x=>set.has(x),
      toggle(x, force){if(force===undefined) force=!set.has(x); force?set.add(x):set.delete(x);}}};
}
const elements = {};
for (const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)) {
  const classes = (m[0].match(/class="([^"]*)"/)?.[1] || '').split(' ');
  elements[m[2]]=element(m[2],m[1].toUpperCase(),classes);
}
const panels = Object.values(elements).filter(x=>x.classList.contains('tab-panel'));
const tabs = [...html.matchAll(/<button data-tab="([^"]+)"([^>]*)>/g)].map(m=>{
  const el=element('', 'BUTTON', m[2].includes('active')?['active']:[]);el.dataset.tab=m[1];return el;
});
const document = {
  getElementById(id){return elements[id];},
  querySelector(q){return q==='.tabs button.active'?tabs.find(x=>x.classList.contains('active')):elements[q.slice(1)];},
  querySelectorAll(q){return q==='.tabs button'?tabs:q==='.tab-panel'?panels:[];}
};
const context=vm.createContext({document, console, fetch:()=>new Promise(()=>{}), setInterval:()=>{}, Date});
vm.runInContext(fs.readFileSync(path.join(staticDir,'app.js'),'utf8'),context);
context.fixture = {
  ok:true, latest:{life_path:'Corporate', attributes:{}, finished_quests:[], resolved_binary_facts:{},
    inventory_items:[], inventory_records:[]}, decisions:[], quests:[], history:[], stats:{},
  iconic_weapons:{records:[
    {id:'byakko',name:'Byakko',status:'stash',owned:true,game:'base',locations:['stash']},
    {id:'skippy',name:'SKIPPY',status:'equipped',owned:true,game:'base',locations:['equipped']},
    {id:'erebus',name:'EREBUS',status:'stash',owned:true,game:'phantom_liberty',locations:['stash']}
  ],counts:{total:3,owned:3,stash:2,equipped:1}}
};
vm.runInContext('render(fixture)', context);
let iconicRebuilds = 0;
let iconicHtml = elements['iconic-rows'].innerHTML;
Object.defineProperty(elements['iconic-rows'], 'innerHTML', {
  get(){return iconicHtml;},
  set(value){iconicRebuilds++; iconicHtml=value;}
});
vm.runInContext('render(fixture, true)', context);
assert.equal(iconicRebuilds, 0, 'polling must not replace open guide details');
context.fixture.iconic_weapons = {...context.fixture.iconic_weapons, revision:1};
vm.runInContext('render(fixture, true)', context);
assert.equal(iconicRebuilds, 1, 'new Iconic data must still refresh the table');
tabs.find(x=>x.dataset.tab==='iconic').listeners.click();
elements['iconic-search'].value='Byakko';
elements['iconic-status'].value='stash';
vm.runInContext('render(fixture)', context);
assert.deepEqual(panels.filter(x=>!x.classList.contains('hidden')).map(x=>x.id),['iconic']);
assert.equal(elements['iconic-search'].value,'Byakko');
assert.match(elements['iconic-rows'].innerHTML,/SCHOWEK/);
assert.doesNotMatch(elements['iconic-rows'].innerHTML,/SKIPPY/);
elements['iconic-search'].value=''; elements['iconic-status'].value='equipped';
vm.runInContext('renderIconic()',context);
assert.match(elements['iconic-rows'].innerHTML,/SKIPPY/);
elements['iconic-game'].value='phantom_liberty';
vm.runInContext('renderIconic()',context);
assert.match(elements['iconic-rows'].innerHTML,/Brak wyników/);
console.log('PASS: tab persistence, stash and equipped filters, combined game filter, empty state');
context.selectionFixture = {save_selection:{mode:'manual', selected_save:'ManualSave-660', active_save:'ManualSave-660', saves:[
  {save_name:'ManualSave-661',timestamp:'new',level:60,playthrough_hours:177},
  {save_name:'ManualSave-660',timestamp:'old',level:60,playthrough_hours:176}
]}};
vm.runInContext('renderSaveSelection(selectionFixture)',context);
assert.equal(elements['save-select'].value,'ManualSave-660');
assert.match(elements['save-current'].textContent,/ManualSave-660.*ręczny/);
elements['save-select'].value='ManualSave-661';
elements['save-select'].listeners.change();
vm.runInContext('renderSaveSelection(selectionFixture)',context);
assert.equal(elements['save-select'].value,'ManualSave-661');
assert.match(elements['save-current'].textContent,/ManualSave-660/);
vm.runInContext("selectionDirty = false; selectionFixture.save_selection.mode = 'automatic'; selectionFixture.save_selection.selected_save = null; renderSaveSelection(selectionFixture)",context);
assert.equal(elements['save-select'].value,'');
vm.runInContext("render({ok:false,error:'missing',save_selection:selectionFixture.save_selection})",context);
assert.equal(panels.filter(x=>!x.classList.contains('hidden')).length,0);
console.log('PASS: save selection label, pending choice survives polling, automatic mode, missing save hides stale panels');
// Run the real guide renderer against the shipped registry, without network.
const registry = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/iconic_weapons.json'), 'utf8'));
context.fixture.iconic_weapons.records = registry.weapons.map(x => ({...x,status:'stash',owned:true,
  availability_class: 'unknown'}));
context.fixture.iconic_weapons.records.find(x=>x.id==='pariah').availability_class='decision_dependent';
for (const id of ['iconic-search','iconic-game','iconic-status','iconic-guide-filter','iconic-method']) elements[id].value='';
vm.runInContext('render(fixture)',context);
assert.equal((elements['iconic-rows'].innerHTML.match(/<tr class=/g)||[]).length,20);
assert.equal(elements['iconic-page'].textContent,'Strona 1 z 6');
elements['iconic-next'].listeners.click();
assert.equal(elements['iconic-page'].textContent,'Strona 2 z 6');
elements['iconic-guide-filter'].value='needs_verification';
elements['iconic-guide-filter'].listeners.change();
assert.equal((elements['iconic-rows'].innerHTML.match(/<tr class=/g)||[]).length,0);
assert.equal(elements['iconic-page'].textContent,'Strona 1 z 1');
elements['iconic-guide-filter'].value='';
elements['iconic-search'].value='Wakako';
elements['iconic-search'].listeners.input();
assert.match(elements['iconic-rows'].innerHTML,/Byakko/);
assert.match(elements['iconic-rows'].innerHTML,/Professional Widow/);
assert.match(elements['iconic-rows'].innerHTML,/noopener noreferrer/);
elements['iconic-rows'].listeners.toggle({target:{dataset:{guideId:'byakko'},open:true}});
vm.runInContext('render(fixture)',context);
assert.match(elements['iconic-rows'].innerHTML,/data-guide-id="byakko" open/);
elements['iconic-search'].value='';
elements['iconic-method'].value='crafting';
elements['iconic-method'].listeners.change();
assert.equal((elements['iconic-rows'].innerHTML.match(/<tr class=/g)||[]).length,10);
elements['iconic-method'].value='';
elements['iconic-search'].value='genjiroh';
elements['iconic-search'].listeners.input();
assert.equal((elements['iconic-rows'].innerHTML.match(/locationIds=/g)||[]).length,2);
assert.equal(vm.runInContext("guideLink({url:'javascript:alert(1)',label:'bad'})", context),'');
assert.match(vm.runInContext("guideLink({url:'https://example.com/',label:'<script>'})",context),/&lt;script&gt;/);
console.log('PASS: guide pagination, source filters, NPC search, persistent details, crafting, multiple markers, escaped links');

elements['iconic-search'].value='';
elements['iconic-collection'].value='special_reward';
elements['iconic-collection'].listeners.change();
assert.match(elements['iconic-rows'].innerHTML,/YASHA/);
assert.doesNotMatch(elements['iconic-rows'].innerHTML,/Byakko/);
elements['iconic-collection'].value='story_choice';
elements['iconic-collection'].listeners.change();
assert.match(elements['iconic-rows'].innerHTML,/PARIAH/);
elements['iconic-collection'].value='';
elements['iconic-method'].value='purchase';
elements['iconic-method'].listeners.change();
assert.equal((elements['iconic-rows'].innerHTML.match(/<tr class=/g)||[]).length,3);
elements['iconic-method'].value='';
elements['iconic-availability'].value='decision_dependent';
elements['iconic-availability'].listeners.change();
assert.match(elements['iconic-rows'].innerHTML,/PARIAH/);
assert.doesNotMatch(elements['iconic-rows'].innerHTML,/SOVEREIGN/);
elements['iconic-availability'].value='';
elements['iconic-search'].value='Sulimov';
elements['iconic-search'].listeners.input();
assert.equal((elements['iconic-rows'].innerHTML.match(/<tr class=/g)||[]).length,1);
assert.match(elements['iconic-rows'].innerHTML,/PIZDETS/);
console.log('PASS: special rewards, story choices, purchase filter, localized name deduplication');
assert.doesNotMatch(vm.runInContext("guideDetails({id:'old',availability_class:'generally_available'})",context), /Zwykle dostępna/);
assert.match(vm.runInContext("guideDetails({id:'old',availability_class:'generally_available'})",context), /Nie oceniono/);

// New discovery cards: spoiler search boundaries, distinct recipes, safe refresh.
const choiceRegistry = JSON.parse(fs.readFileSync(path.join(__dirname,'../data/quest_choices.json'),'utf8'));
context.fixture.latest.save_name='SaveA';
context.fixture.quest_choices={records:choiceRegistry.records.map(x=>({...x,save_evidence:{status:'unknown',evidence:[]}})),counts:{total:choiceRegistry.records.length},lifepath:'Nomad'};
context.fixture.quickhacks={records:[
  {id:'Items.MemoryWipeLvl3Program',family:'MemoryWipe',name:'Memory Wipe',kind:'program',tier:4,owned:true,location:'player',quantity:1},
  {id:'Items.Recipe_ContagionLvl3Program',family:'Contagion',name:'Contagion',name_pl:'Atak wirusowy',kind:'recipe',tier:4,owned:true,location:'player',quantity:1},
  {id:'Items.ContagionLvl3Program',family:'Contagion',name:'Contagion',name_pl:'Atak wirusowy',kind:'program',tier:4,owned:false,location:'other',quantity:1}
],counts:{owned_program_variants:1,owned_recipe_variants:1}};
elements['quickhack-location'].value='owned';
vm.runInContext('render(fixture)',context);
assert.match(elements['quickhack-list'].innerHTML,/Schemat · IV/);
assert.doesNotMatch(elements['quickhack-list'].innerHTML,/INNY KONTENER/);
elements['quickhack-kind'].value='program';
elements['quickhack-kind'].listeners.change();
assert.match(elements['quickhack-list'].innerHTML,/Memory Wipe/);
assert.doesNotMatch(elements['quickhack-list'].innerHTML,/Atak wirusowy/);
elements['choice-search'].value='Kostaryki'; // present only in a hidden outcome
elements['choice-search'].listeners.input();
assert.match(elements['choice-list'].innerHTML,/Brak zadań/);
elements['choice-search'].value='Anna';
elements['choice-search'].listeners.input();
assert.match(elements['choice-list'].innerHTML,/Anna Hamill/);
assert.match(elements['choice-list'].innerHTML,/data-choice-id="anna-hamill" >/);
elements['choice-list'].listeners.toggle({target:{dataset:{choiceId:'anna-hamill'},open:true}});
vm.runInContext('renderChoices()',context);
assert.match(elements['choice-list'].innerHTML,/data-choice-id="anna-hamill" open/);
let choiceRebuilds=0, choiceHtml=elements['choice-list'].innerHTML;
Object.defineProperty(elements['choice-list'],'innerHTML',{get(){return choiceHtml;},set(value){choiceRebuilds++;choiceHtml=value;}});
vm.runInContext('render(fixture,true)',context);
assert.equal(choiceRebuilds,0,'polling unchanged choices must preserve native details');
context.fixture.latest.save_name='SaveB';
vm.runInContext('render(fixture,true)',context);
assert.match(elements['choice-list'].innerHTML,/data-choice-id="anna-hamill" >/);
assert.doesNotMatch(elements['choice-list'].innerHTML,/data-choice-id="anna-hamill" open/);
console.log('PASS: recipe/program separation, other containers, spoiler search, persistent consequences, save switch closes spoilers');

// The separate bootstrap also handles failure when the main bundle never executes.
assert.ok(html.includes('/boot.js?'));
for (const lang of ['pl','en']) {
  const nodes = {loading:element('loading'),error:element('error','DIV',['hidden'])};
  let handler;
  vm.runInNewContext(fs.readFileSync(path.join(staticDir,'boot.js'),'utf8'),{
    window:{addEventListener:(evt,fn)=>handler=fn},
    document:{documentElement:{lang},querySelector:q=>nodes[q.slice(1)]}
  });
  handler({target:{id:'companion-app'}});
  assert.ok(nodes.loading.classList.contains('hidden'));
  assert.ok(!nodes.error.classList.contains('hidden'));
  assert.match(nodes.error.textContent,lang==='pl'?/Rozpakuj/:/Extract/);
}
console.log('PASS: bilingual bootstrap without inline JavaScript');
