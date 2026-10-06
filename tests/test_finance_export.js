const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const fflate=require('../assets/vendor/finance/fflate/index.js');
const {Worker}=require('node:worker_threads'),{resolveObjectURL}=require('node:buffer');
class BrowserWorker {
  constructor(url){
    this.worker=new Worker(`
      const {parentPort}=require('node:worker_threads');
      globalThis.self=globalThis;
      globalThis.postMessage=(data,transfers)=>parentPort.postMessage(data,transfers);
      globalThis.addEventListener=()=>{};
      parentPort.once('message',source=>{
        (0,eval)(source);
        parentPort.on('message',data=>globalThis.onmessage({data}));
      });
    `,{eval:true});
    this.worker.on('message',data=>this.onmessage?.({data}));
    this.worker.on('error',error=>this.onmessage?.({data:{$e$:[error.message,error.code,error.stack]}}));
    this.ready=resolveObjectURL(url).text().then(source=>this.worker.postMessage(source));
  }
  postMessage(data,transfers){this.ready.then(()=>this.worker.postMessage(data,transfers));}
  terminate(){return this.worker.terminate();}
}
function exportContext(extra={}){
  const context=vm.createContext({Blob,URL,Worker:BrowserWorker,Uint8Array,TextEncoder,TextDecoder,...extra});
  context.window=context;context.self=context;
  vm.runInContext(fs.readFileSync(require.resolve('../assets/vendor/finance/fflate/index.js'),'utf8'),context);
  return context;
}
const context=exportContext();
vm.runInContext(fs.readFileSync(require.resolve('../finance-export.js'),'utf8'),context);
test('literal OOXML escapes are protected in every text cell without changing types or links',async()=>{
  const rows=[['INV_x0041_','_x005F_x0041_','_x0041__x00aF_','_x0041_x0042_'],
    ['=_x0041_+1','_x123_ _X0041_ _xZZZZ_',12.5,null]];
  const book=await context.window.FinanceExport.workbook([{name:'Journal',rows,links:[{ref:'A2',target:'originals/_x0041_.pdf'}]}]);
  const bytes=new Uint8Array(await book.arrayBuffer());
  const files=fflate.unzipSync(bytes),sheet=fflate.strFromU8(files['xl/worksheets/sheet1.xml']);
  for(const value of ['INV_x005F_x0041_','_x005F_x005F_x005F_x0041_','_x005F_x0041__x005F_x00aF_',
    '_x005F_x0041_x005F_x0042_','=_x005F_x0041_+1','_x123_ _X0041_ _xZZZZ_'])assert.ok(sheet.includes('>'+value+'</t>'),value);
  assert.ok(sheet.includes('<c r="C2" s="2"><v>12.5</v></c>'));
  assert.ok(sheet.includes('<c r="D2"/>'));assert.equal(sheet.includes('<f>'),false);
  assert.ok(fflate.strFromU8(files['xl/worksheets/_rels/sheet1.xml.rels']).includes('Target="originals/_x0041_.pdf"'));
});
test('archive keeps escape-like ledger text, original bytes and source relationships',async()=>{
  const {createHash}=require('node:crypto'),blob=new Blob(['%PDF-1.4\nfixture'],{type:'application/pdf'});
  const hash=createHash('sha256').update(Buffer.from(await blob.arrayBuffer())).digest('hex');
  const context=exportContext({FinanceDocuments:{script:async()=>{},sha:async()=>hash}});
  vm.runInContext(fs.readFileSync(require.resolve('../finance-model.js'),'utf8'),context);
  context.FinanceModel=context.window.FinanceModel;
  vm.runInContext(fs.readFileSync(require.resolve('../finance-export.js'),'utf8'),context);
  const model=context.FinanceModel,data=model.empty(),entry=model.draft('entry_x0041_','extra');
  Object.assign(entry,{status:'confirmed',party:'Party_x0041_',number:'INV_x0041_',date:'2026-10-06',currency:'CHF',sourceId:hash,note:'_x005F_x0041_'});
  entry.lines=[{description:'=_x0041_+1',quantity:2,unitMinor:100,bookingId:'booking_x0041_'}];
  entry.payments=[{id:'payment_x0041_',date:entry.date,amountMinor:50,note:'Paid_x0041_'}];
  data.entries.push(entry);data.documents.push({id:hash,name:'Original_x0041_.pdf',type:blob.type,size:blob.size,sha256:hash});
  const archive=await context.window.FinanceExport.archive(data,key=>key,async()=>blob);
  const files=fflate.unzipSync(new Uint8Array(await archive.arrayBuffer())),sheets=fflate.unzipSync(files['comptabilite.xlsx']);
  assert.deepEqual(JSON.parse(fflate.strFromU8(files['records.json'])),JSON.parse(JSON.stringify(data)));
  const target=`originals/${hash}.pdf`;
  assert.deepEqual(files[target],new Uint8Array(await blob.arrayBuffer()));
  for(const [sheet,values] of [[1,['INV_x005F_x0041_','Party_x005F_x0041_','_x005F_x005F_x005F_x0041_']],
    [2,['=_x005F_x0041_+1','booking_x005F_x0041_']],[3,['payment_x005F_x0041_','Paid_x005F_x0041_']],
    [4,['Original_x005F_x0041_.pdf']]]){
    const xml=fflate.strFromU8(sheets[`xl/worksheets/sheet${sheet}.xml`]);
    for(const value of values)assert.ok(xml.includes('>'+value+'</t>'),value);
    assert.equal(xml.includes('<f>'),false);
  }
  for(const sheet of [1,4])assert.ok(fflate.strFromU8(sheets[`xl/worksheets/_rels/sheet${sheet}.xml.rels`]).includes(`Target="${target}"`));
});
test('maximum ledger row count exports every row with typed literal cells',async()=>{
  const rows=[['ID','Description','Amount']];
  for(let i=0;i<500000;i++)rows.push(['entry-'+Math.floor(i/100),'=1+1',10.5]);
  const book=await context.window.FinanceExport.workbook([{name:'Lines',rows}]);
  const bytes=new Uint8Array(await book.arrayBuffer());
  const files=fflate.unzipSync(bytes),sheet=fflate.strFromU8(files['xl/worksheets/sheet1.xml']);
  assert.equal((sheet.match(/<row /g)||[]).length,500001);
  assert.ok(sheet.includes('<c r="A500001" t="inlineStr" s="0"><is><t xml:space="preserve">entry-4999</t></is></c>'));
  assert.ok(sheet.includes('<c r="B500001" t="inlineStr" s="0"><is><t xml:space="preserve">=1+1</t></is></c>'));
  assert.ok(sheet.includes('<c r="C500001" s="2"><v>10.5</v></c>'));
  assert.ok(sheet.includes('<autoFilter ref="A1:C500001"/>'));
  assert.equal(sheet.includes('<f>'),false);
});
function simulatedZipContext(lengths,{inputSize}={}){
  const stats={names:[],compressed:0,emitted:0,ends:0,terminated:0,active:new Set(),archives:0};
  class OutputBlob extends Blob {
    constructor(parts,options){super(parts,options);if(options?.type==='application/zip')stats.archives++;}
  }
  const context=exportContext({Blob:OutputBlob}),{Zip,ZipPassThrough,strToU8}=context.fflate;
  context.fflate.Zip=class extends Zip {
    constructor(callback){super((error,chunk,final)=>{
      if(chunk)stats.emitted+=chunk.length;
      if(final)stats.directory=chunk;
      callback(error,chunk,final);
    });}
    add(file){stats.names.push(file.filename);super.add(file);}
    end(){stats.ends++;super.end();}
    terminate(){stats.terminated++;super.terminate();}
  };
  context.fflate.AsyncZipDeflate=class extends ZipPassThrough {
    constructor(name){super(name);stats.active.add(this);this.terminate=()=>stats.active.delete(this);}
    push(bytes){
      this.size=bytes.length;this.crc=0;
      const chunks=lengths(this.filename,stats);
      queueMicrotask(()=>chunks.forEach((length,i)=>{
        const chunk=new Uint8Array(2);Object.defineProperty(chunk,'length',{value:length});
        stats.compressed+=length;this.ondata(null,chunk,i===chunks.length-1);
      }));
    }
  };
  if(inputSize!==undefined)context.fflate.strToU8=value=>{
    const bytes=strToU8(value);
    if(value.includes('<Types '))Object.defineProperty(bytes,'length',{value:inputSize});
    return bytes;
  };
  vm.runInContext(fs.readFileSync(require.resolve('../finance-export.js'),'utf8'),context);
  return {context,stats,run:()=>context.FinanceExport.workbook([{name:'Journal',rows:[['Literal']]}])};
}
const zip32Max=0xffffffff;
const overhead=names=>22+names.reduce((sum,name)=>sum+92+2*Buffer.byteLength(name),0);
test('ZIP32 accepts the last safe byte including headers, descriptors and central directory',async()=>{
  const {run,stats}=simulatedZipContext((name,stats)=>[
    name==='xl/worksheets/sheet1.xml'?zip32Max-1-overhead(stats.names)-stats.compressed:2
  ]);
  await run();
  assert.equal(stats.emitted,zip32Max-1);
  assert.equal(stats.archives,1);assert.equal(stats.ends,1);assert.equal(stats.terminated,1);assert.equal(stats.active.size,0);
  const end=Buffer.from(stats.directory).subarray(-22);
  assert.equal(end.readUInt32LE(16)+end.readUInt32LE(12)+22,zip32Max-1);
});
test('ZIP32 rejects metadata overhead at and beyond capacity before finalization',async t=>{
  for(const extra of [0,1,22,200])await t.test('overflow '+extra,async()=>{
    const {run,stats}=simulatedZipContext((name,stats)=>[
      name==='xl/worksheets/sheet1.xml'?zip32Max+extra-overhead(stats.names)-stats.compressed:2
    ]);
    await assert.rejects(run(),{code:'ZIP32_LIMIT'});
    assert.ok(stats.compressed<zip32Max);
    assert.equal(stats.ends,0);assert.equal(stats.archives,0);assert.equal(stats.terminated,1);assert.equal(stats.active.size,0);
  });
});
test('ZIP32 rejects cumulative offsets from individually eligible chunks and files',async()=>{
  const {run,stats}=simulatedZipContext(()=>[450000000,450000000]);
  await assert.rejects(run(),{code:'ZIP32_LIMIT'});
  assert.ok(stats.names.length>1);assert.ok(stats.names.length<6);
  assert.equal(stats.ends,0);assert.equal(stats.archives,0);assert.equal(stats.terminated,1);assert.equal(stats.active.size,0);
});
test('ZIP32 reserves the next file metadata before starting its compressor',async()=>{
  const {run,stats}=simulatedZipContext((name,stats)=>[zip32Max-1-overhead(stats.names)]);
  await assert.rejects(run(),{code:'ZIP32_LIMIT'});
  assert.equal(stats.names.length,1);assert.equal(stats.emitted+46+Buffer.byteLength(stats.names[0])+22,zip32Max-1);
  assert.equal(stats.ends,0);assert.equal(stats.archives,0);assert.equal(stats.terminated,1);assert.equal(stats.active.size,0);
});
test('ZIP32 checks uncompressed entry size before starting compression',async t=>{
  for(const inputSize of [zip32Max-1,zip32Max,zip32Max+1])await t.test('size '+inputSize,async()=>{
    const {run,stats}=simulatedZipContext(()=>[2],{inputSize});
    if(inputSize<zip32Max){await run();assert.equal(stats.archives,1);}
    else{await assert.rejects(run(),{code:'ZIP32_LIMIT'});assert.equal(stats.names.length,0);assert.equal(stats.archives,0);}
    assert.equal(stats.terminated,1);assert.equal(stats.active.size,0);
  });
});
