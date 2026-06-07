import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "GST Bharat eCommerce GST automation for Indian sellers";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#f6f8fb",
          color: "#10244d",
          padding: 72,
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div
            style={{
              width: 92,
              height: 92,
              borderRadius: 24,
              background: "#10244d",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 42,
              fontWeight: 900,
            }}
          >
            GB
          </div>
          <div style={{ fontSize: 42, fontWeight: 900 }}>GST Bharat</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 76, lineHeight: 1.02, fontWeight: 900, maxWidth: 980 }}>
            eCommerce GST automation for Indian sellers
          </div>
          <div style={{ marginTop: 28, fontSize: 30, lineHeight: 1.35, color: "#40536f", maxWidth: 980 }}>
            Marketplace imports, GSTR-1 exports, Tally XML and 2A/2B reconciliation in one workspace.
          </div>
        </div>
        <div style={{ display: "flex", gap: 18, fontSize: 24, fontWeight: 700, color: "#1746A2" }}>
          <span>GSTR-1 JSON</span>
          <span>•</span>
          <span>Tally XML</span>
          <span>•</span>
          <span>GST Reconciliation</span>
        </div>
      </div>
    ),
    size,
  );
}
