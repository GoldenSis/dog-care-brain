const test=require('node:test'),assert=require('node:assert/strict');
const M=require('../finance-model.js');
function documents(count){return Array.from({length:count},(_,i)=>{const id=i.toString(16).padStart(64,'0');return {id,name:`Original ${i}.pdf`,type:'application/pdf',size:100,sha256:id};});}
test('retained document comparison stays linear at the 5000-document limit',t=>{
  const stringify=JSON.stringify;
  let calls=0,budget=0;
  t.mock.method(JSON,'stringify',(...args)=>{
    assert.ok(++calls<=budget,'Document comparison exceeded its linear serialization budget');
    return stringify(...args);
  });
  for(const count of [4999,5000]){
    const old=M.empty();old.documents=documents(count);
    const next=structuredClone(old);next.documents=documents(5000).reverse();next.profile.name='Updated business';
    calls=0;budget=old.documents.length+next.documents.length;
    assert.equal(M.validate(next,old),true);
    assert.ok(calls<=budget);
    assert.equal(old.profile.name,'');
    assert.equal(old.documents.length,count);
  }
});
test('retained originals require exact metadata even at the document limit',()=>{
  const old=M.empty();old.documents=documents(5000);
  for(const change of [
    next=>{next.documents[4999].name='Renamed.pdf';},
    next=>{next.documents[4999].type='image/png';},
    next=>{next.documents[4999].size++;},
    next=>{next.documents[4999].id=next.documents[4999].sha256='f'.repeat(64);},
    next=>{next.documents.pop();},
    next=>{next.documents[4999]=Object.fromEntries(Object.entries(next.documents[4999]).reverse());},
    next=>{next.documents[4999]=structuredClone(next.documents[0]);}
  ]){
    const next=structuredClone(old);change(next);
    assert.throws(()=>M.validate(next,old),/Invalid accounting record/);
  }
  const oversized=M.empty();oversized.documents=documents(5001);
  assert.throws(()=>M.validate(oversized,old),/Invalid accounting record/);
});
test('payments retain their currency and cash direction across every editable kind',()=>{
  for(const kind of M.kinds){
    const old=M.empty(),e=invoice();e.kind=kind;e.payments=[{id:'p1',date:e.date,amountMinor:100,note:''}];old.entries.push(e);
    for(const patch of [{currency:'EUR'},...M.kinds.filter(k=>['sale','extra'].includes(k)!==['sale','extra'].includes(kind)).map(kind=>({kind}))]){
      const next=structuredClone(old);Object.assign(next.entries[0],patch);assert.throws(()=>M.validate(next,old),JSON.stringify({kind,patch}));
    }
    assert.equal(M.validate(structuredClone(old),old),true);
    if(kind!=='sale'){const next=structuredClone(old);next.entries[0].note='Corrected receipt note';next.entries[0].payments.push({id:'p2',date:e.date,amountMinor:200,note:''});assert.equal(M.validate(next,old),true);}
  }
});
function invoice(){const e=M.draft('sale-1','sale');Object.assign(e,{number:'F-2026-001',date:'2026-10-06',party:'Client fixture',address:'Client address',issuer:'Fixture business',issuerAddress:'Business address',currency:'CHF',status:'confirmed'});e.lines=[{description:'Day',quantity:2,unitMinor:6500,bookingId:''},{description:'Extra',quantity:1,unitMinor:500,bookingId:''}];return e;}
test('draft unknowns stay unknown; invoice totals and partial payments use exact minor units',()=>{const data=M.empty(),e=invoice();data.entries.push(e);assert.equal(M.total(M.draft('draft')),null);assert.equal(M.total(e),13500);e.payments.push({id:'p1',date:'2026-10-06',amountMinor:3500,note:'Literal =SUM(A1)'});assert.equal(M.paid(e),3500);assert.equal(M.validate(data),true);assert.equal(M.parseMinor('12,30'),1230);assert.throws(()=>M.parseMinor('12.345'));});
test('issued invoice detail, numbering, payments and source identities cannot be rewritten',()=>{const old=M.empty();old.entries.push(invoice());for(const key of ['party','number','currency','issuer']){const next=structuredClone(old);next.entries[0][key]='CHANGED';assert.throws(()=>M.validate(next,old));}const next=structuredClone(old);next.entries.push({...invoice(),id:'duplicate'});assert.throws(()=>M.validate(next));assert.throws(()=>M.validate(M.empty(),old));const paid=structuredClone(old);paid.entries[0].payments.push({id:'p',date:'2026-10-06',amountMinor:1,note:''});assert.throws(()=>M.validate(old,paid));});
test('literal Unicode notes survive validation, malformed values reject, separate currencies remain explicit',()=>{const v=M.empty();v.entries.push(invoice());v.entries[0].note='  café 🐾\n=1+1  ';assert.equal(M.validate(v),true);assert.equal(v.entries[0].note,'  café 🐾\n=1+1  ');for(const patch of [{date:'2026-02-30'},{currency:'CHF\n'},{vatMinor:20000},{status:'paid'},{payments:[{id:'p',date:'2026-10-06',amountMinor:14000,note:''}]}]){const n=structuredClone(v);Object.assign(n.entries[0],patch);assert.throws(()=>M.validate(n));}});
test('OCR provides review proposals and leaves conflicting dates, totals and currencies unknown',()=>{const p=M.propose('Fournisseur Test\nFacture F-123\n06.10.2026\nCroquettes\nTOTAL CHF 42.50');assert.deepEqual(p,{date:'2026-10-06',party:'Fournisseur Test',number:'F-123',currency:'CHF',amount:4250,category:'food'});const q=M.propose('Company\n06.10.2026\n07.10.2026\nTOTAL 10.00 CHF\nTOTAL 20.00 EUR');assert.equal(q.amount,null);assert.equal(q.date,'');assert.equal(q.currency,'');});
test('OCR reference proposals leave field labels and ambiguous values blank',()=>{
  for(const raw of [
    'Invoice\nDate 06.10.2026','Facture\nTOTAL CHF 42.50',
    'Invoice Date 06.10.2026','Facture TOTAL CHF 42.50',
    'Invoice No.\nDate 06.10.2026','Facture n°\nTOTAL CHF 42.50',
    'Rechnung\r\nDatum 06.10.2026','Fattura\nTotale EUR 42.50','Factura\nFecha 06.10.2026',
    'Invoice COPY','Invoice\n2026-10-06','Factura\n06/10/2026',
    'Invoice\n123 Main Street','NotInvoice F-701','Invoice F-701_unreadable',
    'Facture F-701\nFacture F-702'
  ])assert.equal(M.propose(raw).number,'',raw);
  assert.equal(M.propose('Invoice\nDate 06.10.2026').date,'2026-10-06');
  const total=M.propose('Facture\nTOTAL CHF 42.50');
  assert.equal(total.amount,4250);assert.equal(total.currency,'CHF');
});
test('OCR reference proposals preserve clear references in supported languages and layouts',()=>{
  for(const label of ['Facture','Invoice','Rechnung','Fattura','Factura']){
    for(const layout of [' F-701','\tF-701',' : F-701','\nF-701','\r\nF-701',' n° F-701',' No. F-701',' Nr. F-701',' #F-701',' n°\nF-701','\nNr. F-701']){
      const raw=label+layout;assert.equal(M.propose(raw).number,'F-701',raw);
    }
  }
  for(const [raw,expected] of [
    ['Invoice 00701','00701'],['Facture n°F-701','F-701'],['Invoice N701','N701'],
    ['Invoice #ABCD','ABCD'],['Rechnung Nr. ABC/DEF','ABC/DEF'],
    ['Facture n°\nF-701 du 06.10.2026','F-701'],['Rechnung Nr.\nF-701 Datum 06.10.2026','F-701'],
    ['Invoice F-701.','F-701'],['Invoice\nF-701.','F-701'],['Invoice F-701, Date 06.10.2026','F-701'],
    ['Invoice F-701 Date 06.10.2026','F-701'],['Facture F-701\nFacture F-701','F-701'],
    ['Invoice\nDate 06.10.2026\nInvoice F-701','F-701']
  ])assert.equal(M.propose(raw).number,expected,raw);
});
test('OCR does not turn partial grouped amounts into an apparently valid smaller total',()=>{for(const total of ["1'234.50",'1 234.50','1,234.50','1.234,50'])assert.equal(M.propose('TOTAL CHF '+total).amount,null);});
test('card-network headings leave supplier unknown without losing supported receipt fields',()=>{
  for(const heading of ['MASTERCARD','Master Card','visa','VISA DEBIT','Maestro','AMEX','American Express','Carte bancaire','CB']){
    const p=M.propose(`${heading}\nPAIEMENT ACCEPTE\n07.10.2026\nTOTAL EUR 12.50\nCARTE **** 1234`);
    assert.deepEqual(p,{date:'2026-10-07',party:'',number:'',currency:'EUR',amount:1250,category:'other'});
  }
  for(const party of ['Visa Services','Mastercard Supplies','Fournisseur Démo'])assert.equal(M.propose(`${party}\nTOTAL EUR 12.50`).party,party);
});
