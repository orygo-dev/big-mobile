import { useEffect, useRef } from "react";

export default function MapView({ lat, lng, label, height = "220px" }) {
  const ref = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!lat || !lng || !window.L || !ref.current) return;
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
    window.L.marker([lat, lng]).addTo(map).bindPopup(label || "Lokasi laporan").openPopup();
    setTimeout(() => map.invalidateSize(), 200);
    return () => { if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; } };
  }, [lat, lng, label]);

  if (!lat || !lng) {
    return (
      <div className="rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-sm text-slate-500" style={{ height }}>
        Koordinat lokasi tidak tersedia
      </div>
    );
  }
  return <div ref={ref} data-testid="map-view" className="rounded-xl overflow-hidden border border-slate-200" style={{ height }} />;
}
