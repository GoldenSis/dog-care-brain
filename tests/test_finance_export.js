const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const fflate=require('../assets/vendor/finance/fflate/index.js');
const context=vm.createContext({window:{},fflate});
vm.runInContext(fs.readFileSync(require.resolve('../finance-export.js'),'utf8'),context);
test('literal OOXML escapes are protected in every text cell without changing types or links',()=>{
  const rows=[['INV_x0041_','_x005F_x0041_','_x0041__x00aF_','_x0041_x0042_'],
    ['=_x0041_+1','_x123_ _X0041_ _xZZZZ_',12.5,null]];
  const bytes=context.window.FinanceExport.workbook([{name:'Journal',rows,links:[{ref:'A2',target:'originals/_x0041_.pdf'}]}]);
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
  const context=vm.createContext({window:{},fflate,Blob,Uint8Array,FinanceDocuments:{script:async()=>{},sha:async()=>hash}});
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
test('maximum ledger row count exports every row with typed literal cells',()=>{
  const rows=[['ID','Description','Amount']];
  for(let i=0;i<500000;i++)rows.push(['entry-'+Math.floor(i/100),'=1+1',10.5]);
  const bytes=context.window.FinanceExport.workbook([{name:'Lines',rows}]);
  const files=fflate.unzipSync(bytes),sheet=fflate.strFromU8(files['xl/worksheets/sheet1.xml']);
  assert.equal((sheet.match(/<row /g)||[]).length,500001);
  assert.ok(sheet.includes('<c r="A500001" t="inlineStr" s="0"><is><t xml:space="preserve">entry-4999</t></is></c>'));
  assert.ok(sheet.includes('<c r="B500001" t="inlineStr" s="0"><is><t xml:space="preserve">=1+1</t></is></c>'));
  assert.ok(sheet.includes('<c r="C500001" s="2"><v>10.5</v></c>'));
  assert.ok(sheet.includes('<autoFilter ref="A1:C500001"/>'));
  assert.equal(sheet.includes('<f>'),false);
});
