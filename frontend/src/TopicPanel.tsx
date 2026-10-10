import { useEffect,useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { changeCategory,deleteTopic,getCategories,getTopic,getTopicPlacements } from "./api";
import type { MapCategory } from "./api";
import type { ContentBlock,Placement,Topic } from "./types";

export function TopicPanel({topicId,mapId,editMode,refreshKey,csrfToken,onChanged,onClose}:{topicId:string;mapId:string;editMode:boolean;refreshKey:number;csrfToken:string|null;onChanged:()=>void;onClose:()=>void}){
  const [topic,setTopic]=useState<Topic|null>(null),[error,setError]=useState("");
  const [categories,setCategories]=useState<MapCategory[]>([]),[placement,setPlacement]=useState<Placement|null>(null),[category,setCategory]=useState(""),[busy,setBusy]=useState(false);
  useEffect(()=>{const c=new AbortController();setTopic(null);setError("");getTopic(topicId,c.signal).then(setTopic).catch(e=>e.name!=="AbortError"&&setError(e.message));return()=>c.abort()},[topicId]);
  useEffect(()=>{if(!editMode)return;Promise.all([getCategories(mapId),getTopicPlacements(topicId)]).then(([items,placements])=>{
    setCategories(items);setPlacement(placements.find(item=>item.map_id===mapId)??null);
    setCategory(items.find(item=>item.id===topicId)?.parent_topic_id??"");
  }).catch(e=>setError(e.message))},[editMode,mapId,topicId,refreshKey]);
  async function saveCategory(){if(!csrfToken||!placement)return;setBusy(true);setError("");try{
    const result=await changeCategory(topicId,category||null,placement.version,csrfToken);
    setPlacement(result.placement);setCategories(items=>items.map(item=>item.id===topicId?{...item,parent_topic_id:category||null}:item));onChanged();
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function removeTopic(){if(!csrfToken||!window.confirm(`Delete “${topic?.title??"this topic"}” from the map? This archives it and its links.`))return;
    setBusy(true);setError("");try{await deleteTopic(topicId,csrfToken);onChanged();onClose()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  return <aside className="topic-panel" aria-label="Topic details" aria-live="polite">
    <button className="close-button" onClick={onClose} aria-label="Close topic panel">×</button>
    {error&&<p role="alert">{error}</p>}{!topic&&!error&&<p className="loading">Opening topic…</p>}
    {topic&&<article><p className="eyebrow">Knowledge landmark</p><h1>{topic.title}</h1><p className="summary">{topic.summary}</p>
      <p className="meta">Published revision {topic.version} · Updated {new Date(topic.updated_at).toLocaleDateString()}</p>
      <div className="content-blocks">{topic.content.blocks.map(b=><Block key={b.id} block={b}/>)}</div>
      <div className="topic-actions"><a href={topic.canonical_url}>Permanent topic page</a><button onClick={()=>navigator.clipboard.writeText(location.href)}>Copy current view</button></div>
      {editMode&&csrfToken&&placement&&<div className="topic-editor"><h2>Edit map topic</h2><p>Drag its circle to move it. A category places it nearby and controls when it appears as you zoom in.</p>
        <label>Category<select value={category} onChange={event=>setCategory(event.target.value)} disabled={busy}><option value="">Top level (map center)</option>{categories.filter(item=>item.id!==topicId).map(item=><option key={item.id} value={item.id}>{"— ".repeat(item.depth)}{item.title}</option>)}</select></label>
        <div className="topic-editor-actions"><button disabled={busy||category===(categories.find(item=>item.id===topicId)?.parent_topic_id??"")} onClick={saveCategory}>Save category</button><button className="danger" disabled={busy} onClick={removeTopic}>Delete topic</button></div>
      </div>}
    </article>}
  </aside>
}
function Block({block}:{block:ContentBlock}){
  const d=block.data;
  switch(block.type){
    case"paragraph":return <p>{String(d.text??"")}</p>;
    case"heading":return Number(d.level)===3?<h3>{String(d.text??"")}</h3>:<h2>{String(d.text??"")}</h2>;
    case"list":return <ul>{(Array.isArray(d.items)?d.items:[]).map((x,i)=><li key={i}>{String(x)}</li>)}</ul>;
    case"equation":return <div className="equation" dangerouslySetInnerHTML={{__html:katex.renderToString(String(d.latex??""),{displayMode:d.mode!=="inline",throwOnError:false,trust:false,strict:"warn"})}}/>;
    case"external_link":return <p className="external-link"><a href={String(d.url)} target="_blank" rel="noreferrer">{String(d.label??d.url)}</a>{d.description?<span>{String(d.description)}</span>:null}</p>;
    case"topic_link":return <a className="topic-link" href={`/topics/${String(d.target_topic_id)}`}>{String(d.label??"Related topic")}</a>;
    case"callout":return <aside className={`callout ${String(d.kind??"note")}`}><strong>{String(d.kind??"Note")}</strong><p>{String(d.text??"")}</p></aside>;
    case"video":return <Video data={d}/>;
    case"image":return <figure><img src={`/api/v1/assets/${String(d.asset_id)}`} alt={String(d.alt??"")} loading="lazy"/><figcaption>{String(d.caption??"")}</figcaption></figure>;
    case"source":return <p className="source-reference">Source reference: {String(d.source_id)}</p>;
    default:return <div className="unsupported" role="note">This content block is not supported by this version.</div>
  }
}
function Video({data}:{data:Record<string,unknown>}){
  const [load,setLoad]=useState(false),provider=String(data.provider??""),id=encodeURIComponent(String(data.video_id??""));
  const src=provider==="youtube"?`https://www.youtube-nocookie.com/embed/${id}`:provider==="vimeo"?`https://player.vimeo.com/video/${id}`:"";
  if(!load||!src)return <div className="video-consent"><p>{String(data.title??"External video")}</p>{src&&<button onClick={()=>setLoad(true)}>Load video from {provider}</button>} <a href={String(data.fallback_url)} target="_blank" rel="noreferrer">Open fallback link</a></div>;
  return <iframe src={src} title={String(data.title??"Video")} loading="lazy" allowFullScreen/>
}
