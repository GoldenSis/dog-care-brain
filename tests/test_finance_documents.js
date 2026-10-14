const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');

function reader(width=10,height=10){
  const state={decodes:0,closed:0,canvases:[]};
  const context=vm.createContext({window:{},URL,location:{href:'http://localhost/'},
    createImageBitmap:async()=>{state.decodes++;return {width,height,close(){state.closed++;}};},
    document:{createElement(){const c={width:0,height:0,getContext:()=>({drawImage(){},getImageData:()=>({data:new Uint8Array(c.width*c.height*4)})})};state.canvases.push(c);return c;}}});
  vm.runInContext(fs.readFileSync(require.resolve('../finance-documents.js'),'utf8'),context);
  return {state, api:context.window.FinanceDocuments};
}
function png(width,height){
  const bytes=Buffer.alloc(33);Buffer.from([137,80,78,71,13,10,26,10]).copy(bytes);
  bytes.writeUInt32BE(13,8);bytes.write('IHDR',12);bytes.writeUInt32BE(width,16);bytes.writeUInt32BE(height,20);
  return new Blob([bytes],{type:'image/png'});
}
function jpeg(width,height,marker=0xc0){
  return new Blob([Uint8Array.from([255,216,255,225,0,6,1,2,3,4,255,255,marker,0,11,8,height>>8,height&255,width>>8,width&255,1,1,0x11,0,255,217])],{type:'image/jpeg'});
}
test('encoded oversized images reject before decoding on every rendering path',async()=>{
  for(const file of [png(10000,4001),jpeg(10000,4001),jpeg(65535,65535,0xc2)]){
    const {api,state}=reader(),item={file,meta:{type:file.type}};
    await assert.rejects(api.pages(file,item.meta),/Image too large/);
    await assert.rejects(api.withCanvas(item,720,()=>assert.fail('must not render')),/Image too large/);
    assert.equal(state.decodes,0);assert.equal(state.canvases.length,0);
  }
});
test('eligible PNG and JPEG headers still decode and release the bitmap and canvas',async()=>{
  for(const file of [png(8000,5000),jpeg(10,10),jpeg(10,10,0xc2)]){
    const {api,state}=reader();
    assert.equal(await api.withCanvas({file,meta:{type:file.type}},720,c=>c.width*c.height),100);
    assert.equal(state.decodes,1);assert.equal(state.closed,1);
    assert.ok(state.canvases.every(c=>c.width===0&&c.height===0));
  }
});
test('malformed or unknown encoded dimensions reject before decoding',async()=>{
  const valid=jpeg(10,10);
  for(const file of [png(0,10),jpeg(10,0),valid.slice(0,19,'image/jpeg'),new Blob([Uint8Array.from([255,216,255,225,0,1])],{type:'image/jpeg'}),png(10,10).slice(0,20,'image/png')]){
    const {api,state}=reader();
    await assert.rejects(api.withCanvas({file,meta:{type:file.type}},720,()=>{}));
    assert.equal(state.decodes,0);
  }
});
test('decoded dimensions remain checked and release oversized bitmaps',async()=>{
  const {api,state}=reader(10000,4001),file=png(10,10);
  await assert.rejects(api.withCanvas({file,meta:{type:file.type}},720,()=>{}),/Image too large/);
  assert.equal(state.decodes,1);assert.equal(state.closed,1);assert.equal(state.canvases.length,0);
});
