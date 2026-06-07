export const siteUrl = (
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.VERCEL_PROJECT_PRODUCTION_URL ||
  "https://gstbharat.app"
).replace(/^([^h])/, "https://$1").replace(/\/$/, "");

export const siteName = "GST Bharat";

export const siteDescription =
  "GST Bharat helps Indian eCommerce sellers import marketplace reports, validate GST data, generate GSTR-1 files, export Tally XML, and reconcile 2A/2B records.";

export const seoKeywords = [
  "GST software",
  "GSTR-1 JSON generator",
  "eCommerce GST automation",
  "GST reconciliation",
  "2A 2B reconciliation",
  "Tally XML export",
  "Amazon GST report",
  "Flipkart GST report",
  "Meesho GST report",
  "Indian sellers GST",
];

export function absoluteUrl(path = "/") {
  return new URL(path, siteUrl).toString();
}
