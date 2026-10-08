import { act } from "react";
import { createRoot } from "react-dom/client";
import MapView from "./MapView";

global.IS_REACT_ACT_ENVIRONMENT = true;

test("zero coordinates render a map and popup labels remain plain text", () => {
  const container = document.createElement("div");
  const map = { remove: jest.fn(), invalidateSize: jest.fn(), setView: jest.fn() };
  map.setView.mockReturnValue(map);
  const marker = { addTo: jest.fn(), bindPopup: jest.fn(), openPopup: jest.fn() };
  marker.addTo.mockReturnValue(marker);
  marker.bindPopup.mockReturnValue(marker);
  window.L = { map: jest.fn(() => map), tileLayer: jest.fn(() => ({ addTo: jest.fn() })), marker: jest.fn(() => marker) };
  const root = createRoot(container);
  act(() => root.render(<MapView lat={0} lng={0} label={'<img src=x onerror="alert(1)">'} />));
  expect(container.querySelector('[data-testid="map-view"]')).not.toBeNull();
  const popup = marker.bindPopup.mock.calls[0][0];
  expect(popup.textContent).toContain("<img");
  expect(popup.querySelector("img")).toBeNull();
  act(() => root.unmount());
  expect(map.remove).toHaveBeenCalledTimes(1);
  delete window.L;
});
