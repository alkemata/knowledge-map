import { useCallback,useEffect,useState } from "react";
import { getIdentity,getMap,getMaps,logout } from "./api";
import type { Identity } from "./api";
import { SearchPanel } from "./SearchPanel";
import { TopicPanel } from "./TopicPanel";
import { WorldMap } from "./WorldMap";
import type { KnowledgeMap,Placement,TopicSummary } from "./types";
type Route={topicId:string|null;placementId:string|null};
function readRoute():Route{const u=new URL(location.href),m=u.pathname.match(/^\/topics\/([0-9a-f-]+)/i);return{topicId:m?.[1]??u.searchParams.get("topic"),placementId:u.searchParams.get("placement")}}
export default function App(){
  const[maps,setMaps]=useState<KnowledgeMap[]>([]),[active,setActive]=useState<KnowledgeMap|null>(null),[route,setRoute]=useState<Route>(readRoute),[camera,setCamera]=useState<{x:number;y:number;z:number}|null>(null),[error,setError]=useState("");
  const[identity,setIdentity]=useState<Identity>({authenticated:false});
  useEffect(()=>{const c=new AbortController();getMaps(c.signal).then(async items=>{setMaps(items);if(items[0])setActive(await getMap(items[0].id,c.signal))}).catch(e=>setError(e.message));return()=>c.abort()},[]);
  useEffect(()=>{const c=new AbortController();getIdentity(c.signal).then(setIdentity).catch(()=>{});return()=>c.abort()},[]);
  useEffect(()=>{const pop=()=>setRoute(readRoute());addEventListener("popstate",pop);return()=>removeEventListener("popstate",pop)},[]);
  const navigate=useCallback((topicId:string,placementId?:string)=>{if(!active)return;const q=new URLSearchParams({topic:topicId,...(placementId?{placement:placementId}:{}),...(camera?{x:String(Math.round(camera.x)),y:String(Math.round(camera.y)),z:String(camera.z)}:{})});history.pushState({},"",`/map/${active.id}?${q}`);setRoute({topicId,placementId:placementId??null})},[active,camera]);
  const selectPlacement=useCallback((p:Placement)=>navigate(p.topic_id,p.id),[navigate]);
  const selectSearch=useCallback((t:TopicSummary)=>navigate(t.id),[navigate]);
  const close=useCallback(()=>{if(!active)return;history.pushState({},"",`/map/${active.id}`);setRoute({topicId:null,placementId:null})},[active]);
  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="/" aria-label="Alkemata Knowledge Map home"><span className="brand-mark">A</span><span><strong>Alkemata</strong><small>{active?.title??"Knowledge Map"}</small></span></a>
      <nav aria-label="Primary navigation"><a href="#main-content">Explore</a><a href="/api/docs">API</a><a href="/api/v1/capabilities">Capabilities</a></nav>
      {identity.authenticated?<div className="account-controls"><span>{identity.display_name}</span><button onClick={()=>{if(identity.csrf_token)logout(identity.csrf_token).then(()=>setIdentity({authenticated:false})).catch(e=>setError(e.message))}}>Sign out</button></div>:<a className="sign-in" href={`/api/v1/auth/oidc/start?next=${encodeURIComponent(location.pathname+location.search)}`}>Sign in</a>}
      {maps.length>1&&<label className="map-picker">World <select value={active?.id??""} onChange={e=>getMap(e.target.value).then(setActive)}>{maps.map(m=><option key={m.id} value={m.id}>{m.title}</option>)}</select></label>}
    </header>
    <main id="main-content" className="main-layout"><SearchPanel onOpen={selectSearch}/><section className="map-stage" aria-label={active?.title??"Knowledge map"}>
      {error&&<p role="alert" className="fatal-error">{error}</p>}{active&&<WorldMap map={active} selectedPlacementId={route.placementId} onSelect={selectPlacement} onCamera={setCamera}/>}</section>
      {route.topicId&&<TopicPanel topicId={route.topicId} onClose={close}/>}</main>
    <footer><span>Select a circle to read a note. Zoom in to discover more.</span><a href="https://alkemata.com">Alkemata articles</a></footer>
  </div>
}
