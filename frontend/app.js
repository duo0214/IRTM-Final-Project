'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let meta, searchSeq=0, phraseSeq=0;
async function api(path, params={}) {
  const response = await fetch(path + (Object.keys(params).length ? '?' + new URLSearchParams(params) : ''));
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || '連線失敗');
  return data;
}
function error(target, message){ $(target).innerHTML = `<div class="error" role="alert">${esc(message)}</div>`; }
function navigate(page, loadPhrase=true){
  if (!['search','explore'].includes(page)) page='search';
  document.querySelectorAll('.page').forEach(p=>p.hidden=p.id!==`page-${page}`);
  document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
  history.replaceState(null,'',`#${page}`);
  if(loadPhrase && page==='explore' && !$('#phrase-result').textContent) explore($('#phrase-input').value);
}
function sourceLink(url){return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">官方來源 ↗</a>`;}
async function search(query){
  if(!meta) return;
  const seq=++searchSeq;
  $('#query').value=query; navigate('search');
  $('#search-status').innerHTML='<div class="loading">搜尋中…</div>';
  $('#results').innerHTML=''; $('#suggestions').innerHTML='';
  try{
    const data=await api('/search',{query,corpus_id:meta.corpus_id,top_k:$('#top-k').value,domain:$('#domain').value});
    if(seq!==searchSeq) return;
    $('#search-status').innerHTML='';
    $('#result-count').textContent=`${data.results.length} 筆結果`;
    $('#results-title').textContent='搜尋結果';
    $('#results').innerHTML=data.results.length ? data.results.map(d=>`<article class="result-card"><div class="result-card-top"><span>${String(d.rank).padStart(2,'0')}<span class="domain-tag">${esc(d.domain)}</span></span></div><h3>${esc(d.law_name)} · ${esc(d.article_no)}</h3><p>${esc(d.snippet)}${d.snippet.length>=220?'…':''}</p><div class="card-actions"><button class="text-button" data-doc="${esc(d.doc_id)}">閱讀完整原文 →</button>${sourceLink(d.source_url)}<span class="subtle">${d.matched_phrases.map(esc).join(' · ')}</span></div></article>`).join('') : '<div class="empty"><h3>找不到符合的文本</h3><p>請試試其他關鍵字，或選擇全部領域。</p></div>';
    $('#suggestions').innerHTML=data.suggestions.length?data.suggestions.map(s=>`<div class="suggestion"><button data-query="${esc(s.phrase)}">${esc(s.phrase)} ↗</button><button data-phrase="${esc(s.phrase)}">探索 →</button></div>`).join(''):'<p>沒有相關詞組。</p>';
  }catch(e){if(seq===searchSeq){error('#search-status',e.message);$('#result-count').textContent='查詢未完成';}}
}
function highlighted(c){
  // Python offsets are Unicode code points; Array.from avoids JS UTF-16 mismatch.
  const chars=Array.from(c.text);
  return esc(chars.slice(0,c.match_start).join(''))+'<mark>'+esc(chars.slice(c.match_start,c.match_end).join(''))+'</mark>'+esc(chars.slice(c.match_end).join(''));
}
async function explore(term){
  if(!meta)return;
  const seq=++phraseSeq;
  $('#phrase-input').value=term;
  $('#phrase-status').innerHTML='<div class="loading">查詢詞組中…</div>';$('#phrase-result').innerHTML='';
  try{
    const d=await api('/phrases/'+encodeURIComponent(term),{corpus_id:meta.corpus_id});
    if(seq!==phraseSeq)return;
    $('#phrase-status').innerHTML='';
    $('#phrase-result').innerHTML=`<div class="phrase-header"><h2>「${esc(d.phrase)}」</h2><button class="text-button" data-query="${esc(d.phrase)}">用這個詞組搜尋 ↗</button></div><div class="metric-grid"><div class="metric"><span>出現次數</span><strong>${d.frequency}</strong></div><div class="metric"><span>文本數</span><strong>${d.df}</strong></div><div class="metric"><span>涵蓋比例</span><strong>${(100*d.df/meta.document_count).toFixed(1)}<small>%</small></strong></div></div><div class="workspace-grid"><div><div class="section-heading"><h2>原文上下文</h2><span class="subtle">${d.df} 筆</span></div>${d.documents.length?d.documents.map(doc=>`<article class="result-card"><div class="result-card-top"><span>${esc(doc.law_name)} · ${esc(doc.article_no)}</span><span>出現 ${doc.tf} 次</span></div>${doc.contexts.map(c=>`<div class="quote">${highlighted(c)}</div>`).join('')}<div class="card-actions"><button class="text-button" data-doc="${esc(doc.doc_id)}">閱讀完整原文 →</button>${sourceLink(doc.source_url)}</div></article>`).join(''):'<div class="empty"><h3>收錄文本中未出現此詞組</h3><p>換一個詞組試試看。</p></div>'}</div><aside class="context-panel"><h3>共同出現的詞組</h3><p>共現不代表同義。</p>${d.related_terms.map(r=>`<div class="suggestion"><button data-phrase="${esc(r.phrase)}">${esc(r.phrase)} →</button></div>`).join('')||'<p>沒有共同出現的詞組。</p>'}</aside></div>`;
  }catch(e){if(seq===phraseSeq)error('#phrase-status',e.message);}
}
async function openDocument(id){
  const dialog=$('#document-dialog');$('#document-content').textContent='載入原文中…';if(!dialog.open)dialog.showModal();
  try{
    const d=await api('/documents/'+encodeURIComponent(id),{corpus_id:meta.corpus_id});
    $('#document-content').innerHTML=`<h2>${esc(d.law_name)} · ${esc(d.article_no)}</h2><div class="full-text">${esc(d.text)}</div><p>${sourceLink(d.source_url)}</p><details class="source-note"><summary>法規版本與施行資訊</summary><p>法規異動日期：${esc(d.law_version_date)}<br>資料擷取日期：${esc(d.retrieved_at.slice(0,10))}（UTC）<br>適用版本請依情境核對，請以官方來源為準。</p><p>${esc(d.effective_note||'來源未另提供施行註記。')}</p></details>`;
  }catch(e){error('#document-content',e.message);}
}
document.addEventListener('click',event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.page)navigate(b.dataset.page);
  if(b.dataset.query!==undefined)search(b.dataset.query);
  if(b.dataset.phrase!==undefined){$('#phrase-input').value=b.dataset.phrase;navigate('explore',false);explore(b.dataset.phrase);}
  if(b.dataset.doc)openDocument(b.dataset.doc);
});
$('#search-form').addEventListener('submit',e=>{e.preventDefault();search($('#query').value);});
$('#phrase-form').addEventListener('submit',e=>{e.preventDefault();explore($('#phrase-input').value);});
$('#close-dialog').addEventListener('click',()=>$('#document-dialog').close());
window.addEventListener('hashchange',()=>navigate(location.hash.slice(1)));
$('#domain').addEventListener('change',()=>{if($('#query').value.trim())search($('#query').value);});
$('#top-k').addEventListener('change',()=>{if($('#query').value.trim())search($('#query').value);});
async function init(){
 try{
  meta=await api('/meta');
  $('#domain-counts').innerHTML=meta.domains.map(d=>`<div class="domain-meter"><span>${esc(d)}</span><i></i><span>${meta.domain_counts[d]} 筆</span></div>`).join('');
  $('#domain').insertAdjacentHTML('beforeend',meta.domains.map(d=>`<option>${esc(d)}</option>`).join(''));
  $('#phrase-seeds').innerHTML='<span>試試看</span>'+meta.seed_phrases.slice(0,10).map(p=>`<button data-phrase="${esc(p)}">${esc(p)}</button>`).join('');
  navigate(location.hash.slice(1)||'search');
 }catch(e){$('#global-error').hidden=false;$('#global-error').textContent='啟動失敗：'+e.message+'。請重新整理後再試。';}
}
init();
