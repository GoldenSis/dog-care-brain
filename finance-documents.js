/* Lazy local OCR/PDF readers. No remote endpoints or document transmission. */
(function(w){
  'use strict';
  const base=new URL('assets/vendor/finance/',location.href).href;
  const scripts=new Map();
  function script(path){if(!scripts.has(path))scripts.set(path,new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=base+path;s.onload=resolve;s.onerror=()=>{scripts.delete(path);s.remove();reject(Error('Reader unavailable'));};document.head.append(s);}));return scripts.get(path);}
  const sha=async blob=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('');
  async function inspect(file){
    if(!file||file.size<1||file.size>5*1024*1024||[...file.name].length>180)throw Error('File size');
    const bytes=new Uint8Array(await file.slice(0,8).arrayBuffer());
    const signatures={'image/jpeg':[255,216,255],'image/png':[137,80,78,71,13,10,26,10],'application/pdf':[37,80,68,70,45]};
    const type=Object.keys(signatures).find(key=>signatures[key].every((v,i)=>bytes[i]===v));if(!type)throw Error('File type');
    const id=await sha(file);return {id,sha256:id,name:file.name,type,size:file.size};
  }
  function canvas(width,height){const c=document.createElement('canvas');c.width=width;c.height=height;return c;}
  async function pages(file,meta){
    if(meta.type==='application/pdf'){
      let task,overLimit=false;
      try{
        const pdfjs=await import(base+'pdfjs-dist/pdf.mjs');pdfjs.GlobalWorkerOptions.workerSrc=base+'pdfjs-dist/pdf.worker.mjs';
        task=pdfjs.getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false,useSystemFonts:true,disableFontFace:true});
        const pdf=await task.promise, result=[];
        if(pdf.numPages>20){overLimit=true;throw Error('Too many pages');}for(let n=1;n<=pdf.numPages;n++){
          const p=await pdf.getPage(n), natural=p.getViewport({scale:1}), scale=Math.min(2,2400/Math.max(natural.width,natural.height)), view=p.getViewport({scale});
          const c=canvas(Math.ceil(view.width),Math.ceil(view.height));await p.render({canvasContext:c.getContext('2d'),viewport:view}).promise;
          result.push({canvas:c,page:n,regions:[{page:n,x:0,y:0,width:1,height:1}]});p.cleanup();
        }return result;
      }catch(error){if(overLimit)throw error;return [{canvas:null,page:null,regions:[null]}];}
      finally{if(task)try{await task.destroy();}catch{}}
    }
    const bitmap=await createImageBitmap(file);try{if(bitmap.width*bitmap.height>40000000)throw Error('Image too large');const scale=Math.min(1,3000/Math.max(bitmap.width,bitmap.height));const c=canvas(Math.round(bitmap.width*scale),Math.round(bitmap.height*scale));c.getContext('2d').drawImage(bitmap,0,0,c.width,c.height);return [{canvas:c,page:1,regions:detect(c)}];}finally{bitmap.close();}
  }
  /* Suggest separate pale paper rectangles on darker tables; always user-correctable. */
  function detect(source){
    const width=240,height=Math.max(1,Math.round(source.height/source.width*width));if(height>1000)return [{page:1,x:0,y:0,width:1,height:1}];
    const c=canvas(width,height),ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(source,0,0,width,height);const pixels=ctx.getImageData(0,0,width,height).data,visited=new Uint8Array(width*height),boxes=[];
    const paper=i=>{const rgb=[pixels[i*4],pixels[i*4+1],pixels[i*4+2]];return Math.min(...rgb)>195&&Math.max(...rgb)-Math.min(...rgb)<55;};
    for(let i=0;i<visited.length;i++){
      if(visited[i]||!paper(i))continue;const stack=[i];visited[i]=1;let minX=width,maxX=0,minY=height,maxY=0,count=0;
      while(stack.length){const p=stack.pop(),x=p%width,y=Math.floor(p/width);count++;minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
        for(const q of [x>0?p-1:-1,x+1<width?p+1:-1,y>0?p-width:-1,y+1<height?p+width:-1])if(q>=0&&!visited[q]&&paper(q)){visited[q]=1;stack.push(q);}}
      if(count>width*height*.025&&(maxX-minX)>20&&(maxY-minY)>20){const x=Math.max(0,(minX-2)/width),y=Math.max(0,(minY-2)/height);boxes.push({page:1,x,y,width:Math.min(1-x,(maxX-minX+5)/width),height:Math.min(1-y,(maxY-minY+5)/height)});}
    }
    return boxes.length>=2&&boxes.length<=10?boxes:[{page:1,x:0,y:0,width:1,height:1}];
  }
  async function recognize(items,language,onProgress){
    await script('tesseract.js/tesseract.min.js');
    const deadline=(promise,ms=120000)=>{let timer;return Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Reader timed out')),ms);})]).finally(()=>clearTimeout(timer));};
    const lang={fr:'fra',en:'eng',de:'deu',it:'ita',es:'spa'}[language]||'fra';let worker,finished=false;
    try{worker=await deadline(Tesseract.createWorker(lang,1,{workerPath:base+'tesseract.js/worker.min.js',corePath:base+'tesseract.js-core',langPath:base+'tessdata',workerBlobURL:false,logger:m=>onProgress(m.progress||0)}).then(value=>{if(finished){value.terminate();throw Error('Reader stopped');}return value;}));
      const result=[];for(const item of items){const c=item.canvas,r=item.region,rectangle={left:Math.floor(r.x*c.width),top:Math.floor(r.y*c.height),width:Math.max(1,Math.floor(r.width*c.width)),height:Math.max(1,Math.floor(r.height*c.height))};
        rectangle.width=Math.min(rectangle.width,c.width-rectangle.left);rectangle.height=Math.min(rectangle.height,c.height-rectangle.top);
        const output=await deadline(worker.recognize(c,{rectangle}));result.push(output.data.text.slice(0,20000));}return result;
    }finally{finished=true;if(worker)await worker.terminate();}
  }
  w.FinanceDocuments={inspect,pages,recognize,script,sha};
})(window);
