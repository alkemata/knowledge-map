export type TopicSummary = {
  id: string;
  slug: string;
  title: string;
  summary: string;
  language?: string;
  version?: number;
  canonical_url: string;
};

export type ContentBlock = {
  id: string;
  type: string;
  data: Record<string, unknown>;
};

export type Topic = TopicSummary & {
  status: string;
  content: { schema_version: number; blocks: ContentBlock[] };
  updated_at: string;
};

export type Placement = {
  id: string;
  topic_id: string;
  map_id: string;
  region_id: string | null;
  x: number;
  y: number;
  icon: string;
  min_zoom: number;
  max_zoom: number;
  label_priority: number;
  version: number;
  topic?: TopicSummary;
};

export type Region = {
  id: string;
  map_id: string;
  title: string;
  bounds: { min_x: number; min_y: number; max_x: number; max_y: number };
  style: { fill?: string; accent?: string };
  version: number;
};

export type TerrainFeature = {
  id: string;
  layer_id: string;
  feature_type: "polygon" | "polyline" | "symbol";
  geometry: { points?: [number, number][]; x?: number; y?: number };
  symbol?: string;
  style: { fill?: string; stroke?: string; weight?: number };
  version: number;
};

export type Viewport = {
  placements: Placement[];
  regions: Region[];
  layers: { id: string; kind: string; z_index: number }[];
  features: TerrainFeature[];
  has_more: boolean;
};

export type TileConfig = {
  url_template: string;
  image_url?: string;
  tile_size: number;
  min_zoom: number;
  max_native_zoom: number;
  max_zoom: number;
};

export type KnowledgeMap = {
  id: string;
  title: string;
  description: string;
  default_camera: { x: number; y: number; z: number };
  bounds?: { min_x: number; min_y: number; max_x: number; max_y: number };
  tiles?: TileConfig;
  version: number;
};

export type Trail = {
  id: string;
  title: string;
  summary: string;
  start_step_id: string;
  steps: {
    id: string;
    topic_id: string;
    preferred_placement_id: string | null;
    note: string;
  }[];
  edges: {
    from_step_id: string;
    to_step_id: string;
    label: string;
    is_default: boolean;
  }[];
};
