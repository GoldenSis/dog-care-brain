/* Minimal typed Open XML workbook: literal strings never become formulas. */
(function(w){
  'use strict';
  const xml=s=>String(s??'').replace(/[&<>"'\r]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;','\r':'&#13;'}[c]));
  const cellText=s=>xml(String(s).replace(/_(?=x[0-9a-fA-F]{4}_)/g,'_x005F_'));
  const column=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
  async function zip(files){
    const parts=[];let failure,size=22;
    const check=size=>{if(size>=0xffffffff)throw Object.assign(Error('ZIP32 capacity exceeded'),{code:'ZIP32_LIMIT'});};
    const archive=new fflate.Zip((error,chunk)=>{if(error)failure=error;else parts.push(new Blob([chunk]));});
    try{
      for await(const [name,bytes] of files){
        check(bytes.length);check(size+=30+16+46+2*fflate.strToU8(name).length);
        await new Promise((resolve,reject)=>{
          const file=new fflate.AsyncZipDeflate(name,{level:6});archive.add(file);
          const ondata=file.ondata;
          file.ondata=(error,chunk,final)=>{
            try{if(failure)throw failure;if(!error)check(size+=chunk.length);ondata(error,chunk,final);if(failure)throw failure;if(final)resolve();}catch(error){failure=error;reject(error);}
          };
          file.push(bytes,true);
        });
      }
      archive.end();if(failure)throw failure;
      return new Blob(parts,{type:'application/zip'});
    }finally{archive.terminate();parts.length=0;}
  }
  function workbook(sheets){
    const ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main',rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships',pack='http://schemas.openxmlformats.org/package/2006/relationships';
    const files={};const put=(name,value)=>files[name]=fflate.strToU8('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+value);
    put('[Content_Types].xml',`<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${sheets.map((_,i)=>`<Override PartName="/xl/worksheets/sheet${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>`);
    put('_rels/.rels',`<Relationships xmlns="${pack}"><Relationship Id="rId1" Type="${rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>`);
    put('xl/workbook.xml',`<workbook xmlns="${ns}" xmlns:r="${rel}"><sheets>${sheets.map((s,i)=>`<sheet name="${xml(s.name.slice(0,31))}" sheetId="${i+1}" r:id="rId${i+1}"/>`).join('')}</sheets></workbook>`);
    put('xl/_rels/workbook.xml.rels',`<Relationships xmlns="${pack}">${sheets.map((_,i)=>`<Relationship Id="rId${i+1}" Type="${rel}/worksheet" Target="worksheets/sheet${i+1}.xml"/>`).join('')}<Relationship Id="styles" Type="${rel}/styles" Target="styles.xml"/></Relationships>`);
    put('xl/styles.xml',`<styleSheet xmlns="${ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/><xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`);
    sheets.forEach((sheet,i)=>{
      const width=sheet.rows.reduce((max,row)=>Math.max(max,row.length),1);
      const rows=sheet.rows.map((row,r)=>`<row r="${r+1}">${row.map((v,c)=>{const ref=column(c)+(r+1);if(v===null||v===undefined)return `<c r="${ref}"/>`;if(typeof v==='number')return `<c r="${ref}" s="2"><v>${v}</v></c>`;return `<c r="${ref}" t="inlineStr" s="${r===0?1:0}"><is><t xml:space="preserve">${cellText(v)}</t></is></c>`;}).join('')}</row>`).join('');
      put(`xl/worksheets/sheet${i+1}.xml`,`<worksheet xmlns="${ns}" xmlns:r="${rel}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="${width}" width="24" customWidth="1"/></cols><sheetData>${rows}</sheetData><autoFilter ref="A1:${column(width-1)}${Math.max(1,sheet.rows.length)}"/>${sheet.links?.length?`<hyperlinks>${sheet.links.map((link,j)=>`<hyperlink ref="${link.ref}" r:id="link${j}"/>`).join('')}</hyperlinks>`:''}</worksheet>`);
      if(sheet.links?.length)put(`xl/worksheets/_rels/sheet${i+1}.xml.rels`,`<Relationships xmlns="${pack}">${sheet.links.map((link,j)=>`<Relationship Id="link${j}" Type="${rel}/hyperlink" Target="${xml(link.target)}" TargetMode="External"/>`).join('')}</Relationships>`);
    });return zip(Object.entries(files));
  }
  function sourceName(d){const extension={'image/jpeg':'jpg','image/png':'png','application/pdf':'pdf'}[d.type];return `originals/${d.id}.${extension}`;}
  async function archive(data,t,getDocument){
    await FinanceDocuments.script('fflate/index.js');FinanceModel.validate(data);
    const m=FinanceModel, sources=new Map(data.documents.map(d=>[d.id,sourceName(d)])), amount=v=>v===null?null:v/100;
    const entries=[[t('number'),t('kind'),t('status'),t('date'),t('due'),t('party'),t('category'),t('currency'),t('amount'),t('vat'),t('paid'),t('outstanding'),t('sourceFile'),t('note'),'ID',t('area'),t('reason'),t('address'),t('issuer'),t('issuerAddress'),t('taxId')]];
    const lines=[['ID',t('description'),t('quantity'),t('unit'),t('currency'),'Booking ID']];
    const payments=[['ID','Payment ID',t('date'),t('amount'),t('currency'),t('note')]];
    for(const e of data.entries){const total=m.total(e);entries.push([e.number,t(e.kind),t(e.status==='confirmed'&&e.kind==='sale'?'issued':e.status),e.date,e.due,e.party,t(e.category),e.currency,amount(total),amount(e.vatMinor),amount(m.paid(e)),total===null?null:amount(total-m.paid(e)),sources.get(e.sourceId)||'',e.note,e.id,e.region?JSON.stringify(e.region):'',e.cancelReason,e.address,e.issuer,e.issuerAddress,e.taxId]);
      e.lines.forEach(l=>lines.push([e.id,l.description,l.quantity,amount(l.unitMinor),e.currency,l.bookingId]));e.payments.forEach(p=>payments.push([e.id,p.id,p.date,amount(p.amountMinor),e.currency,p.note]));}
    const docs=[[t('sourceFile'),t('description'),'SHA-256','Bytes'],...data.documents.map(d=>[sourceName(d),d.name,d.sha256,d.size])];
    async function* files(){
      for(const d of data.documents){const blob=await getDocument(d.id);if(!blob||blob.size!==d.size||await FinanceDocuments.sha(blob)!==d.sha256)throw Error('Missing original');yield [sourceName(d),new Uint8Array(await blob.arrayBuffer())];}
      const book=await workbook([{name:t('journal'),rows:entries,links:data.entries.flatMap((e,i)=>e.sourceId?[{ref:'M'+(i+2),target:sources.get(e.sourceId)}]:[])},{name:t('lines'),rows:lines},{name:t('payments'),rows:payments},{name:t('source'),rows:docs,links:data.documents.map((d,i)=>({ref:'A'+(i+2),target:sourceName(d)}))},{name:t('readme'),rows:[[t('title')],[t('allExport')],[t('summaryHelp')],[t('ocrHelp')]]}]);
      yield ['comptabilite.xlsx',new Uint8Array(await book.arrayBuffer())];
      yield ['records.json',fflate.strToU8(JSON.stringify(data,null,2))];
    }
    return zip(files());
  }
  function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  w.FinanceExport={workbook,archive,download};
})(window);
