"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import Link from "next/link";
import { rupees } from "@/lib/utils";

export type MapPoint = {
  gym_code: string;
  name: string;
  slug: string;
  latitude: number;
  longitude: number;
  locality: string;
  district: string;
  monthly_fee: number;
  coach_included: boolean;
  coach_fee_separate: number;
  ac_status: string;
  gym_type: string;
  rating: number;
  review_count: number;
  is_real_listing: boolean;
};

// Leaflet's default marker icons reference image files that don't survive a
// bundler; build small colored pins from inline SVG instead so nothing 404s
// and the real/demo distinction is visible at a glance on the map itself,
// not just inside the popup.
function pinIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<svg width="26" height="34" viewBox="0 0 26 34" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 0C5.8 0 0 5.8 0 13c0 9.75 13 21 13 21s13-11.25 13-21C26 5.8 20.2 0 13 0z"
            fill="${color}" stroke="rgba(0,0,0,.35)" stroke-width="1"/>
      <circle cx="13" cy="13" r="5.5" fill="white" fill-opacity=".92"/>
    </svg>`,
    iconSize: [26, 34],
    iconAnchor: [13, 34],
    popupAnchor: [0, -30],
  });
}

const REAL_ICON = pinIcon("#22C55E");   // emerald - genuine OpenStreetMap-sourced gym
const DEMO_ICON = pinIcon("#657084");   // muted grey - demo/placeholder listing

const KAKINADA: [number, number] = [16.9891, 82.2475];

/** Re-centers the map when the point set changes (e.g. after a filter). */
function FitBounds({ points }: { points: MapPoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    const bounds = L.latLngBounds(points.map((p) => [p.latitude, p.longitude]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }, [points, map]);
  return null;
}

export default function GymMap({
  points,
  heightClass = "h-[70vh]",
}: {
  points: MapPoint[];
  heightClass?: string;
}) {
  // MapContainer keeps internal state that doesn't like re-mounting under
  // React StrictMode's double-invoke in dev - guard with a stable ref key.
  const mapKey = useRef(Math.random().toString(36).slice(2)).current;

  return (
    <div className={`${heightClass} w-full rounded-2xl overflow-hidden border border-ink-800`}>
      <MapContainer
        key={mapKey}
        center={KAKINADA}
        zoom={9}
        scrollWheelZoom
        style={{ height: "100%", width: "100%", background: "#16181d" }}
      >
        {/* OpenStreetMap tiles - free, no API key, standard attribution required */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds points={points} />
        {points.map((p) => (
          <Marker
            key={p.gym_code}
            position={[p.latitude, p.longitude]}
            icon={p.is_real_listing ? REAL_ICON : DEMO_ICON}
          >
            <Popup minWidth={220}>
              <div style={{ fontFamily: "inherit" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <strong style={{ fontSize: 13 }}>{p.name}</strong>
                </div>
                <div style={{ fontSize: 11, color: "#666", marginBottom: 6 }}>
                  {p.locality}, {p.district}
                </div>
                <div
                  style={{
                    fontSize: 10, fontWeight: 700, display: "inline-block",
                    padding: "2px 8px", borderRadius: 999, marginBottom: 6,
                    background: p.is_real_listing ? "#DCFCE7" : "#E5E7EB",
                    color: p.is_real_listing ? "#15803D" : "#4B5563",
                  }}
                >
                  {p.is_real_listing ? "Real gym (verified via OpenStreetMap)" : "Demo listing"}
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 2 }}>
                  {rupees(p.monthly_fee)}/month
                </div>
                <div style={{ fontSize: 11, color: "#666", marginBottom: 8 }}>
                  {p.ac_status} &middot;{" "}
                  {p.coach_included ? "Coach included" : `+${rupees(p.coach_fee_separate)} coach`}
                  {" · "}★ {p.rating} ({p.review_count})
                </div>
                <Link
                  href={`/gyms/${p.gym_code}`}
                  style={{
                    display: "inline-block", fontSize: 12, fontWeight: 600,
                    color: "#ED3311", textDecoration: "none",
                  }}
                >
                  View details →
                </Link>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
