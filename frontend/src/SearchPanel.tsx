import { useEffect,useState } from "react";
import { searchTopics } from "./api";
import type { TopicSummary } from "./types";
export function SearchPanel({onOpen}:{onOpen:(t:TopicSummary)=>void}){
  const[q,setQ]=useState(""),[items,setItems]=useState<TopicSummary[]>([]),[error,setError]=useState("");
  useEffect(()=>{const c=new AbortController(),timer=setTimeout(()=>searchTopics(q,c.signal).then(r=>{setItems(r.items);setError("")}).catch(e=>e.name!=="AbortError"&&setError(e.message)),180);return()=>{c.abort();clearTimeout(timer)}},[q]);
  return <section className="search-panel" aria-label="Search and accessible topic list">
    <label htmlFor="topic-search">Explore topics</label>
    <input id="topic-search" type="search" value={q} onChange={e=>setQ(e.target.value)} placeholder="Search the landscape…" autoComplete="off"/>
    {error&&<p role="alert">{error}</p>}
    <ol className="search-results">{items.map(item=><li key={item.id}><button onClick={()=>onOpen(item)}><strong>{item.title}</strong><span>{item.summary}</span></button></li>)}</ol>
  </section>
}
