import { useEffect, useRef, useState } from "react";
import L, { CRS, LayerGroup, Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import { getViewport } from "./api";
import { pointsToLeaflet, worldToLeaflet } from "./coordinates";
import type { KnowledgeMap, Placement, Viewport } from "./types";

type Props = {
  map: KnowledgeMap;
  selectedPlacementId: string | null;
  onSelect: (placement: Placement) => void;
  onCamera: (camera: { x: number; y: number; z: number }) => void;
};

const glyphs: Record<string, string> = {
  building: "◆",
  library: "▤",
  tower: "♜",
  workshop: "⚒",
  observatory: "◉",
  bridge: "⌁",
};

export function WorldMap({ map, selectedPlacementId, onSelect, onCamera }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const leaflet = useRef<LeafletMap | null>(null);
  const layers = useRef<LayerGroup | null>(null);
  const abort = useRef<AbortController | null>(null);
  const selectRef = useRef(onSelect);
  const cameraRef = useRef(onCamera);
  const [dense, setDense] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    selectRef.current = onSelect;
    cameraRef.current = onCamera;
  }, [onSelect, onCamera]);

  useEffect(() => {
    if (!host.current) return;

    const instance = L.map(host.current, {
      crs: CRS.Simple,
      minZoom: -4,
      maxZoom: 4,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      attributionControl: false,
    });
    leaflet.current = instance;

    const bounds = map.bounds;
    if (bounds?.min_x != null) {
      const imageBounds = L.latLngBounds(
        worldToLeaflet({ x: bounds.min_x, y: bounds.min_y }),
        worldToLeaflet({ x: bounds.max_x, y: bounds.max_y }),
      );
      L.imageOverlay("/knowledge-map-landscape.png", imageBounds, {
        opacity: 0.72,
        interactive: false,
        className: "world-background",
      }).addTo(instance);
      instance.fitBounds(imageBounds);
    } else {
      instance.setView(worldToLeaflet(map.default_camera), map.default_camera.z);
    }

    layers.current = L.layerGroup().addTo(instance);

    const render = (data: Viewport) => {
      const group = layers.current;
      if (!group) return;
      group.clearLayers();

      for (const region of data.regions) {
        const area = region.bounds;
        L.rectangle(
          [
            worldToLeaflet({ x: area.min_x, y: area.min_y }),
            worldToLeaflet({ x: area.max_x, y: area.max_y }),
          ],
          {
            color: region.style.accent ?? "#2f5c50",
            fillColor: region.style.fill ?? "#e8efe6",
            fillOpacity: 0.12,
            opacity: 0.7,
            weight: 2,
          },
        )
          .bindTooltip(region.title, {
            permanent: instance.getZoom() < -2,
            direction: "center",
            className: "region-label",
          })
          .addTo(group);
      }

      for (const feature of data.features) {
        const points = feature.geometry.points ?? [];
        if (feature.feature_type === "polygon" && points.length > 2) {
          L.polygon(pointsToLeaflet(points), {
            color: feature.style.stroke ?? "#365314",
            fillColor: feature.style.fill ?? "#d9ead3",
            fillOpacity: 0.2,
            weight: feature.style.weight ?? 2,
            interactive: false,
          }).addTo(group);
        }
        if (feature.feature_type === "polyline" && points.length > 1) {
          L.polyline(pointsToLeaflet(points), {
            color: feature.style.stroke ?? "#854d0e",
            weight: feature.style.weight ?? 5,
            opacity: 0.72,
            interactive: false,
          }).addTo(group);
        }
      }

      for (const placement of data.placements) {
        if (!placement.topic) continue;
        const selected = placement.id === selectedPlacementId;
        const glyph = glyphs[placement.icon] ?? "◆";
        const marker = L.marker(worldToLeaflet(placement), {
          icon: L.divIcon({
            className: `topic-marker${selected ? " selected" : ""}`,
            html:
              `<span aria-hidden="true" class="marker-glyph">${glyph}</span>` +
              `<span class="marker-label">${escapeHtml(placement.topic.title)}</span>`,
            iconSize: [148, 46],
            iconAnchor: [24, 23],
          }),
          keyboard: true,
          title: placement.topic.title,
          alt: placement.topic.title,
          riseOnHover: true,
        });
        marker.on("click", () => selectRef.current(placement));
        marker.addTo(group);
      }
    };

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
        render(data);
        setDense(data.has_more);
        setError("");
        const center = instance.getCenter();
        cameraRef.current({ x: center.lng, y: center.lat, z: zoom });
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
    };
  }, [map.id, selectedPlacementId]);

  return (
    <div className="map-wrap" aria-label="Interactive knowledge map">
      <div ref={host} className="world-map" />
      <aside className="legend" aria-label="Map legend">
        <strong>Legend</strong>
        <span>◆ topic landmark</span>
        <span>Brown path: learning route</span>
        <span>Illustrated terrain is contextual unless stated otherwise.</span>
      </aside>
      {dense && <p className="map-notice">This area is dense. Zoom in to reveal all landmarks.</p>}
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
