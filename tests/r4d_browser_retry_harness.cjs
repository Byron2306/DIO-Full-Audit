const vm = require('node:vm');
const fs = require('node:fs');
const crypto = require('node:crypto').webcrypto;
const source = fs.readFileSync(process.argv[2], 'utf8');
const attachments = process.argv[3] === 'attachments';
const validation = process.argv[3] === 'validation';
const storage = new Map(), posts = [];
class Element {
  constructor(){ this.value=''; this.files=[]; this.options=[{value:''}]; this.classList={add(){},remove(){}}; }
  addEventListener(){} replaceChildren(){} append(){} focus(){}
  appendChild(row){ this.options.push(row); }
}
async function open(){
  const elements = new Map();
  const context = vm.createContext({
    console, URLSearchParams, crypto, TextEncoder,
    location:{search:'',port:'8770',origin:'http://127.0.0.1:8770'},
    document:{querySelector(key){ if(!elements.has(key)) elements.set(key,new Element()); return elements.get(key); },createElement(){return new Element();}},
    sessionStorage:{getItem(key){return storage.get(key)||null;},setItem(key,value){storage.set(key,String(value));},removeItem(key){storage.delete(key);}},
    FileReader: class {readAsDataURL(){this.result='data:text/plain;base64,YQ==';this.onload();}},
    fetch:async(url,options={})=>{
      const path = new URL(url).pathname;
      if(path.endsWith('/products')) return {ok:true,json:async()=>({incarnations:['ContractProof']})};
      if(path.endsWith('/message')){
        posts.push(JSON.parse(options.body));
        if(validation && posts.length===1) return {ok:false,status:400,json:async()=>({error:'too many attachments',processing_state:'REJECTED_NO_CANONICAL_EFFECT'})};
        return {ok:false,status:503,json:async()=>({error:'response lost; event held'})};
      }
      const session={conversation_id:'VWC-BROWSER-00000001',messages:[],route:{},handoff:{}};
      return {ok:true,json:async()=>options.method==='POST'?{session}:session};
    },
  });
  vm.runInContext(source,context);
  for(let i=0;i<50 && !vm.runInContext('sessionReady',context);i++) await new Promise(setImmediate);
  if(!vm.runInContext('sessionReady',context)) throw Error('session never started');
  return {context,elements};
}
(async()=>{
  let page=await open();
  page.elements.get('#message').value='I need ContractProof.';
  const file={name:'source.txt',size:1,type:'text/plain'};
  if(attachments) page.elements.get('#files').files=[file];
  await vm.runInContext('send()',page.context);
  const initial=posts[0].client_message_id;
  page=await open();
  page.elements.get('#message').value='I need ContractProof.';
  await vm.runInContext('send()',page.context);
  const afterMissingFiles=posts.length;
  if(attachments){ page.elements.get('#files').files=[file]; await vm.runInContext('send()',page.context); }
  const retry=posts.at(-1).client_message_id;
  page.elements.get('#message').value='A changed request.';
  await vm.runInContext('send()',page.context);
  process.stdout.write(JSON.stringify({initial,retry,afterMissingFiles,totalPosts:posts.length}));
})().catch(error=>{console.error(error);process.exitCode=1;});
