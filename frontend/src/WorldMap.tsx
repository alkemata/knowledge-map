import { useEffect, useRef, useState } from "react";
import L, { CRS, LayerGroup, Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { getViewport } from "./api";
import { worldToLeaflet } from "./coordinates";
import type { KnowledgeMap, Placement, Viewport } from "./types";

type Props = {
  map: KnowledgeMap;
  selectedPlacementId: string | null;
  onSelect: (placement: Placement) => void;
  onCamera: (camera: { x: number; y: number; z: number }) => void;
};

export function WorldMap({ map, selectedPlacementId, onSelect, onCamera }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const leaflet = useRef<LeafletMap | null>(null);
  const layers = useRef<LayerGroup | null>(null);
  const abort = useRef<AbortController | null>(null);
  const selectRef = useRef(onSelect);
  const cameraRef = useRef(onCamera);
  const selectedRef = useRef(selectedPlacementId);
  const lastViewport = useRef<Viewport | null>(null);
  const renderRef = useRef<((data: Viewport) => void) | null>(null);
  const [dense, setDense] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    selectRef.current = onSelect;
    cameraRef.current = onCamera;
  }, [onSelect, onCamera]);

  useEffect(() => {
    selectedRef.current = selectedPlacementId;
    if (lastViewport.current) renderRef.current?.(lastViewport.current);
  }, [selectedPlacementId]);

  useEffect(() => {
    if (!host.current) return;

    const tileConfig = map.tiles;
    const instance = L.map(host.current, {
      crs: CRS.Simple,
      minZoom: tileConfig?.min_zoom ?? -4,
      maxZoom: tileConfig?.max_zoom ?? 4,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      attributionControl: false,
    });
    leaflet.current = instance;

    const bounds = map.bounds;
    if (bounds?.min_x != null) {
      const worldBounds = L.latLngBounds(
        worldToLeaflet({ x: bounds.min_x, y: bounds.min_y }),
        worldToLeaflet({ x: bounds.max_x, y: bounds.max_y }),
      );
      if (tileConfig?.image_url) {
        L.imageOverlay(tileConfig.image_url, worldBounds, {
          interactive: false,
          className: "world-background-image",
        }).addTo(instance);
      } else if (tileConfig) {
        L.tileLayer(tileConfig.url_template, {
          tileSize: tileConfig.tile_size,
          minZoom: tileConfig.min_zoom,
          maxNativeZoom: tileConfig.max_native_zoom,
          maxZoom: tileConfig.max_zoom,
          bounds: worldBounds,
          noWrap: true,
          keepBuffer: 2,
          updateWhenIdle: true,
          className: "world-background-tile",
        }).addTo(instance);
      }
      instance.setMaxBounds(worldBounds.pad(0.08));
      instance.setView(worldToLeaflet(map.default_camera), map.default_camera.z);
    } else {
      instance.setView(worldToLeaflet(map.default_camera), map.default_camera.z);
    }

    layers.current = L.layerGroup().addTo(instance);

    const render = (data: Viewport) => {
      const group = layers.current;
      if (!group) return;
      group.clearLayers();

      for (const placement of data.placements) {
        if (!placement.topic) continue;
        const selected = placement.id === selectedRef.current;
        const regionIndex = data.regions.findIndex((region) => region.id === placement.region_id);
        const marker = L.marker(worldToLeaflet(placement), {
          icon: L.divIcon({
            className: `content-node tone-${Math.max(0, regionIndex) % 3}${selected ? " selected" : ""}`,
            html: `<span class="content-node-dot" aria-hidden="true"></span><span class="content-node-label">${escapeHtml(placement.topic.title)}</span>`,
            iconSize: [36, 36],
            iconAnchor: [18, 18],
          }),
          keyboard: true,
          alt: placement.topic.title,
          riseOnHover: true,
        });
        marker.on("click", () => selectRef.current(placement));
        marker.addTo(group);
      }
    };
    renderRef.current = render;

    const refresh = async () => {
      const visible = instance.getBounds();
      const zoom = instance.getZoom();
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      try {
        const data = await getViewport(
          map.id,
          {
            min_x: visible.getWest(),
            min_y: visible.getSouth(),
            max_x: visible.getEast(),
            max_y: visible.getNorth(),
          },
          zoom,
          controller.signal,
        );
        lastViewport.current = data;
        render(data);
        setDense(data.has_more);
        setError("");
        const center = instance.getCenter();
        const camera = { x: center.lng, y: center.lat, z: zoom };
        cameraRef.current(camera);
      } catch (caught) {
        if ((caught as Error).name !== "AbortError") {
          setError((caught as Error).message);
        }
      }
    };

    instance.on("moveend", refresh);
    void refresh();

    return () => {
      abort.current?.abort();
      instance.remove();
      leaflet.current = null;
      layers.current = null;
      lastViewport.current = null;
      renderRef.current = null;
    };
  }, [map.id]);

  return (
    <div className="map-wrap" aria-label="Interactive knowledge map">
      <div ref={host} className="world-map" />
      {dense && <p className="map-notice">Zoom in to reveal more notes.</p>}
      {error && <p className="map-error" role="alert">{error}</p>}
    </div>
  );
}

function escapeHtml(value: string) {
  return value.replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[
        character
      ] ?? character,
  );
}
