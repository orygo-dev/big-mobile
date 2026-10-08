import { useEffect, useRef } from "react";

export default function MapView({ lat, lng, label, height = "220px" }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const hasCoordinates = lat != null && lng != null && Number.isFinite(Number(lat)) && Number.isFinite(Number(lng));

  useEffect(() => {
    if (!hasCoordinates || !window.L || !ref.current) return;
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }
    const map = window.L.map(ref.current, { scrollWheelZoom: false }).setView([lat, lng], 15);
    mapRef.current = map;
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    const popup = document.createElement("span");
    popup.textContent = label || "Lokasi laporan";
    window.L.marker([lat, lng]).addTo(map).bindPopup(popup).openPopup();
    const timer = setTimeout(() => map.invalidateSize(), 200);
    return () => { clearTimeout(timer); if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; } };
  }, [lat, lng, label, hasCoordinates]);

  if (!hasCoordinates) {
    return (
      <div className="rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-sm text-slate-500" style={{ height }}>
        Koordinat lokasi tidak tersedia
      </div>
    );
  }
  return <div ref={ref} data-testid="map-view" className="rounded-xl overflow-hidden border border-slate-200" style={{ height }} />;
}
