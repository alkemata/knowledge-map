import { useEffect,useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { getTopic } from "./api";
import type { ContentBlock,Topic } from "./types";

export function TopicPanel({topicId,onClose}:{topicId:string;onClose:()=>void}){
  const [topic,setTopic]=useState<Topic|null>(null),[error,setError]=useState("");
  useEffect(()=>{const c=new AbortController();setTopic(null);getTopic(topicId,c.signal).then(setTopic).catch(e=>e.name!=="AbortError"&&setError(e.message));return()=>c.abort()},[topicId]);
  return <aside className="topic-panel" aria-label="Topic details" aria-live="polite">
    <button className="close-button" onClick={onClose} aria-label="Close topic panel">×</button>
    {error&&<p role="alert">{error}</p>}{!topic&&!error&&<p className="loading">Opening topic…</p>}
    {topic&&<article><p className="eyebrow">Knowledge landmark</p><h1>{topic.title}</h1><p className="summary">{topic.summary}</p>
      <p className="meta">Published revision {topic.version} · Updated {new Date(topic.updated_at).toLocaleDateString()}</p>
      <div className="content-blocks">{topic.content.blocks.map(b=><Block key={b.id} block={b}/>)}</div>
      <div className="topic-actions"><a href={topic.canonical_url}>Permanent topic page</a><button onClick={()=>navigator.clipboard.writeText(location.href)}>Copy current view</button></div>
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
