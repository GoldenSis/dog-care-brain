const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const fflate=require('../assets/vendor/finance/fflate/index.js');
const context=vm.createContext({window:{},fflate});
vm.runInContext(fs.readFileSync(require.resolve('../finance-export.js'),'utf8'),context);
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
