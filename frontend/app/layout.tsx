import type { Metadata, Viewport } from "next";
import { Toaster } from "react-hot-toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fitora — Find your gym. Join in minutes.",
  description:
    "Discover gyms near you in the Kakinada region, compare real pricing and equipment, " +
    "join online and get a digital entry pass. Coach fees shown clearly — included or extra.",
  keywords: ["gym", "fitness", "Kakinada", "Andhra Pradesh", "gym membership", "gym near me"],
};

export const viewport: Viewport = {
  themeColor: "#0f1115",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Toaster
          position="top-center"
          toastOptions={{
            duration: 3500,
            style: {
              background: "#1a1d23",
              color: "#ECEEF2",
              border: "1px solid #23262d",
              borderRadius: "12px",
              fontSize: "14px",
              maxWidth: "min(92vw, 420px)",
            },
            success: { iconTheme: { primary: "#22C55E", secondary: "#16181d" } },
            error: { iconTheme: { primary: "#EF4444", secondary: "#16181d" } },
          }}
        />
      </body>
    </html>
  );
}
