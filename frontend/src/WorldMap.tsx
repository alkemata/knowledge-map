import { useEffect, useRef, useState } from "react";
import L, { CRS, LayerGroup, Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { getViewport } from "./api";
import { pointsToLeaflet, worldToLeaflet } from "./coordinates";
import type { KnowledgeMap, Placement, Viewport } from "./types";

type Props = { map: KnowledgeMap; selectedPlacementId: string | null; onSelect: (p: Placement) => void; onCamera: (c: {x:number;y:number;z:number}) => void };
const glyphs: Record<string,string> = { building:"◆", library:"▤", tower:"♜", workshop:"⚒", observatory:"◉", bridge:"⌁" };

export function WorldMap({map, selectedPlacementId, onSelect, onCamera}: Props) {
  const host=useRef<HTMLDivElement>(null), leaflet=useRef<LeafletMap|null>(null), layers=useRef<LayerGroup|null>(null), abort=useRef<AbortController|null>(null);
  const selectRef=useRef(onSelect), cameraRef=useRef(onCamera);
  const [dense,setDense]=useState(false), [error,setError]=useState("");
  useEffect(()=>{selectRef.current=onSelect;cameraRef.current=onCamera},[onSelect,onCamera]);
  useEffect(()=>{
    if(!host.current)return;
    const instance=L.map(host.current,{crs:CRS.Simple,minZoom:-4,maxZoom:4,zoomSnap:.25,zoomDelta:.5,attributionControl:false});
    leaflet.current=instance; layers.current=L.layerGroup().addTo(instance);
    const b=map.bounds;
    if(b?.min_x!=null) instance.fitBounds([worldToLeaflet({x:b.min_x,y:b.min_y}),worldToLeaflet({x:b.max_x,y:b.max_y})]);
    else instance.setView(worldToLeaflet(map.default_camera),map.default_camera.z);
    const render=(data:Viewport)=>{
      const group=layers.current;if(!group)return;group.clearLayers();
      for(const region of data.regions){
        const q=region.bounds;
        L.rectangle([worldToLeaflet({x:q.min_x,y:q.min_y}),worldToLeaflet({x:q.max_x,y:q.max_y})],{
          color:region.style.accent??"#2f5c50",fillColor:region.style.fill??"#e8efe6",fillOpacity:.7,weight:2
        }).bindTooltip(region.title,{permanent:instance.getZoom()<-2,direction:"center",className:"region-label"}).addTo(group);
      }
      for(const f of data.features){
        const points=f.geometry.points??[];
        if(f.feature_type==="polygon"&&points.length>2)L.polygon(pointsToLeaflet(points),{color:f.style.stroke??"#365314",fillColor:f.style.fill??"#d9ead3",fillOpacity:.45,weight:f.style.weight??2,interactive:false}).addTo(group);
        if(f.feature_type==="polyline"&&points.length>1)L.polyline(pointsToLeaflet(points),{color:f.style.stroke??"#854d0e",weight:f.style.weight??5,opacity:.72,interactive:false}).addTo(group);
      }
      for(const p of data.placements){
        if(!p.topic)continue;
        const selected=p.id===selectedPlacementId, glyph=glyphs[p.icon]??"◆";
        const marker=L.marker(worldToLeaflet(p),{icon:L.divIcon({
          className:`topic-marker${selected?" selected":""}`,
          html:`<span aria-hidden="true" class="marker-glyph">${glyph}</span><span class="marker-label">${escapeHtml(p.topic.title)}</span>`,
          iconSize:[148,46],iconAnchor:[24,23]
        }),keyboard:true,title:p.topic.title,alt:p.topic.title,riseOnHover:true});
        marker.on("click",()=>selectRef.current(p));marker.addTo(group);
      }
    };
    const refresh=async()=>{
      const b=instance.getBounds(), z=instance.getZoom();abort.current?.abort();const c=new AbortController();abort.current=c;
      try{const data=await getViewport(map.id,{min_x:b.getWest(),min_y:b.getSouth(),max_x:b.getEast(),max_y:b.getNorth()},z,c.signal);render(data);setDense(data.has_more);setError("");const center=instance.getCenter();cameraRef.current({x:center.lng,y:center.lat,z})}
      catch(e){if((e as Error).name!=="AbortError")setError((e as Error).message)}
    };
    instance.on("moveend",refresh);void refresh();
    return()=>{abort.current?.abort();instance.remove();leaflet.current=null;layers.current=null};
  },[map.id,selectedPlacementId]);
  return <div className="map-wrap" aria-label="Interactive knowledge map">
    <div ref={host} className="world-map"/>
    <aside className="legend" aria-label="Map legend"><strong>Legend</strong><span>◆ topic landmark</span><span>Brown path: learning route</span><span>Terrain is decorative unless stated otherwise.</span></aside>
    {dense&&<p className="map-notice">This area is dense. Zoom in to reveal all landmarks.</p>}
    {error&&<p className="map-error" role="alert">{error}</p>}
  </div>
}
function escapeHtml(v:string){return v.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]??c))}
