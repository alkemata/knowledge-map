import { describe, expect, it } from "vitest";
import { leafletToWorld, worldToLeaflet } from "./coordinates";

describe("world coordinate adapter", () => {
  it.each([
    { x: 1200, y: 1800 },
    { x: -31.25, y: 4097.75 },
    { x: 87, y: -912 },
  ])("round trips asymmetric point $x,$y", (point) => {
    const [lat, lng] = worldToLeaflet(point);
    expect(leafletToWorld({ lat, lng })).toEqual(point);
  });

  it("maps x to longitude and y to latitude", () => {
    expect(worldToLeaflet({ x: 7, y: 19 })).toEqual([19, 7]);
  });
});
