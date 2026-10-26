const fs = require('fs');
const vm = require('vm');
const {webcrypto} = require('crypto');
const assert = require('assert');
const source = fs.readFileSync(process.argv[2], 'utf8');
const mode = process.argv[3] || 'accepted';
const storage = new Map();
let posts = [], accepted = null, created = 0;
class Node {
  constructor(){this.children=[];this.options=[];this.value='';this.files=[];this.disabled=false;
    this.classList={add(){},remove(){},toggle(){}};}
  append(...rows){this.children.push(...rows);}
  appendChild(row){this.children.push(row);this.options.push(row);return row;}
  replaceChildren(...rows){this.children=rows;}
  addEventListener(){}
  focus(){}
  setAttribute(){}
  querySelector(){return new Node();}
}
function reply(body, status=200){return {ok:status<400,status,async text(){return JSON.stringify(body);}};}
function frame(){
  const nodes = new Map();
  const select = key=>{if(!nodes.has(key))nodes.set(key,new Node());return nodes.get(key);};
  const context = {
    document:{querySelector:select,createElement:()=>new Node(),createTextNode:text=>({textContent:text})},
    location:{search:'?product=vesper',hostname:'127.0.0.1',origin:'http://127.0.0.1:8870'},
    window:{DIO_SITE_CONFIG:{vesperPresenceApiOrigin:'http://127.0.0.1:8870'}},
    sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,v)=>storage.set(key,v),removeItem:key=>storage.delete(key)},
    crypto:webcrypto,TextEncoder,Headers,URLSearchParams,URL,Blob,Uint8Array,
    navigator:{},console:{warn(){}},btoa:text=>Buffer.from(text,'binary').toString('base64'),
    atob:text=>Buffer.from(text,'base64').toString('binary'),
    setTimeout:callback=>{queueMicrotask(callback);return 1;},clearTimeout(){},
    fetch:async(url,options)=>{
      if(url.endsWith('/session')&&options.method==='POST'){
        created++;return reply({session:{conversation_id:'VWC-ACTUAL',session_token:'private-token'}});
      }
      if(url.includes('/session?')){
        assert.equal(options.headers.get('X-Vesper-Session-Token'),'private-token');
        return reply({session:{conversation_id:'VWC-ACTUAL',messages:accepted?
          [{role:'vesper',text:'legacy greeting'},{role:'customer',text:accepted.message},{role:'vesper',text:'For ContractProof, tell me the outcome.'}]:[{role:'vesper',text:'legacy greeting'}]},
          replies:accepted?[{source_message_id:`web:VWC-ACTUAL:${accepted.client_message_id}`}]:[]});
      }
      if(url.endsWith('/message') || url.endsWith('/voice')){
        const body=JSON.parse(options.body);posts.push(body);
        if(posts.length===1){if(mode==='accepted' || mode==='voice_accepted')accepted=body;throw new Error('network interrupted');}
        accepted=body;return reply({state:'completed',receipt:{}});
      }
      if(url.includes('/replies?'))return reply({replies:accepted?[{sequence:3,reply:{text:'For ContractProof, tell me the outcome.'}}]:[],next_after:3});
      throw new Error(`unexpected request ${url}`);
    },
  };
  vm.createContext(context);vm.runInContext(source,context);
  return {context,nodes};
}
(async()=>{
  const first=frame();await vm.runInContext('startSession()',first.context);
  first.nodes.get('#message').value='What do you need from me for ContractProof?';
  if(mode.startsWith('voice_')){
    await vm.runInContext("submitVoiceBlob(new Blob(['original voice bytes'], {type:'audio/webm'})).catch(()=>{})",first.context);
  }else await vm.runInContext('send()',first.context);
  assert(posts[0].client_message_id);
  assert.equal(posts[0].incarnation_hint,null); // Vesper remains a surface, not a product.
  const second=frame();await vm.runInContext('startSession()',second.context);
  assert.equal(created,1);
  if(mode==='accepted' || mode==='voice_accepted'){
    assert.equal(posts.length,1);
    assert.equal(second.nodes.get('#message').value,'');
    assert.equal(storage.has('dio.actual.vesper:http://127.0.0.1:8870:pending'),false);
  }else{
    assert.equal(second.nodes.get('#message').value,posts[0].message || '');
    await vm.runInContext('send()',second.context);
    assert.equal(posts.length,2);
    assert.equal(posts[1].client_message_id,posts[0].client_message_id);
    if(mode.startsWith('voice_')) assert.equal(posts[1].audio_b64, posts[0].audio_b64);
  }
  process.stdout.write(JSON.stringify({mode,created,totalPosts:posts.length}));
})().catch(error=>{process.stderr.write(error.stack);process.exit(1);});
