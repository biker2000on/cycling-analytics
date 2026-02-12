import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, useMap } from 'react-leaflet';
import type { LatLngBoundsExpression, LatLngTuple } from 'leaflet';
import L from 'leaflet';
import type { RouteGeoJSON } from '../../api/types.ts';
import './RouteMap.css';

// Fix default marker icons for webpack/vite bundling
const startIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const endIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

interface Props {
  route: RouteGeoJSON;
}

/** Fits map bounds to the route polyline. */
function FitBounds({ positions }: { positions: LatLngTuple[] }) {
  const map = useMap();
  const fitted = useRef(false);

  useEffect(() => {
    if (positions.length > 0 && !fitted.current) {
      const bounds: LatLngBoundsExpression = positions.map(
        (p) => [p[0], p[1]] as [number, number],
      );
      map.fitBounds(bounds, { padding: [30, 30] });
      fitted.current = true;
    }
  }, [map, positions]);

  return null;
}

export default function RouteMap({ route }: Props) {
  // GeoJSON coordinates are [lng, lat] -- convert to [lat, lng] for Leaflet
  const coords = route.geometry.coordinates;
  const positions: LatLngTuple[] = coords.map((c) => [c[1], c[0]]);

  if (positions.length === 0) {
    return <div className="chart-empty">No GPS data available for this route.</div>;
  }

  const startPos = positions[0];
  const endPos = positions[positions.length - 1];
  const center = startPos;

  return (
    <div className="route-map-container">
      <MapContainer
        center={center}
        zoom={13}
        className="route-map"
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polyline
          positions={positions}
          pathOptions={{ color: 'var(--color-power)', weight: 3, opacity: 0.8 }}
        />
        <Marker position={startPos} icon={startIcon} />
        <Marker position={endPos} icon={endIcon} />
        <FitBounds positions={positions} />
      </MapContainer>
    </div>
  );
}
