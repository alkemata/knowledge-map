import { useCallback,useEffect,useState } from "react";
import { getMap,getMaps } from "./api";
import { SearchPanel } from "./SearchPanel";
import { TopicPanel } from "./TopicPanel";
import { WorldMap } from "./WorldMap";
import type { KnowledgeMap,Placement,TopicSummary } from "./types";
type Route={topicId:string|null;placementId:string|null};
function readRoute():Route{const u=new URL(location.href),m=u.pathname.match(/^\/topics\/([0-9a-f-]+)/i);return{topicId:m?.[1]??u.searchParams.get("topic"),placementId:u.searchParams.get("placement")}}
export default function App(){
  const[maps,setMaps]=useState<KnowledgeMap[]>([]),[active,setActive]=useState<KnowledgeMap|null>(null),[route,setRoute]=useState<Route>(readRoute),[camera,setCamera]=useState<{x:number;y:number;z:number}|null>(null),[error,setError]=useState("");
  useEffect(()=>{const c=new AbortController();getMaps(c.signal).then(async items=>{setMaps(items);if(items[0])setActive(await getMap(items[0].id,c.signal))}).catch(e=>setError(e.message));return()=>c.abort()},[]);
  useEffect(()=>{const pop=()=>setRoute(readRoute());addEventListener("popstate",pop);return()=>removeEventListener("popstate",pop)},[]);
  const navigate=useCallback((topicId:string,placementId?:string)=>{if(!active)return;const q=new URLSearchParams({topic:topicId,...(placementId?{placement:placementId}:{}),...(camera?{x:String(Math.round(camera.x)),y:String(Math.round(camera.y)),z:String(camera.z)}:{})});history.pushState({},"",`/map/${active.id}?${q}`);setRoute({topicId,placementId:placementId??null})},[active,camera]);
  const selectPlacement=useCallback((p:Placement)=>navigate(p.topic_id,p.id),[navigate]);
  const selectSearch=useCallback((t:TopicSummary)=>navigate(t.id),[navigate]);
  const close=useCallback(()=>{if(!active)return;history.pushState({},"",`/map/${active.id}`);setRoute({topicId:null,placementId:null})},[active]);
  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="/" aria-label="Alkemata Knowledge Map home"><span className="brand-mark">A</span><span><strong>Alkemata</strong><small>Knowledge Map</small></span></a>
      <nav aria-label="Primary navigation"><a href="#main-content">Explore</a><a href="/api/docs">API</a><a href="/api/v1/capabilities">Capabilities</a></nav>
      {maps.length>1&&<label className="map-picker">World <select value={active?.id??""} onChange={e=>getMap(e.target.value).then(setActive)}>{maps.map(m=><option key={m.id} value={m.id}>{m.title}</option>)}</select></label>}
    </header>
    <main id="main-content" className="main-layout"><SearchPanel onOpen={selectSearch}/><section className="map-stage"><div className="map-intro"><p className="eyebrow">Explore · Understand · Shape</p><h1>{active?.title??"Knowledge has a landscape"}</h1><p>{active?.description??"Loading the world…"}</p></div>
      {error&&<p role="alert" className="fatal-error">{error}</p>}{active&&<WorldMap map={active} selectedPlacementId={route.placementId} onSelect={selectPlacement} onCamera={setCamera}/>}</section>
      {route.topicId&&<TopicPanel topicId={route.topicId} onClose={close}/>}</main>
    <footer><span>Terrain is a navigational metaphor, not a measure of conceptual distance.</span><a href="https://alkemata.com">Alkemata articles</a></footer>
  </div>
}
