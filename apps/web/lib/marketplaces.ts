import { BadgeIndianRupee, Building2, PackageCheck, ShoppingBag, Store, Utensils, Zap } from "lucide-react";

export type Marketplace = {
  key: string;
  name: string;
  category: "Ecommerce" | "Quick Commerce" | "B2B" | "Food" | "Accounting";
  status: "Active" | "Beta" | "Coming Soon";
  requiredFiles: string[];
  guide: string;
  accent: string;
  icon: typeof ShoppingBag;
};

export const marketplaces: Marketplace[] = [
  { key: "amazon", name: "Amazon", category: "Ecommerce", status: "Active", requiredFiles: ["MTR_B2C CSV", "MTR_B2B CSV optional"], guide: "Reports > Manage Taxes > GST Monthly Reports", accent: "from-orange-400 to-slate-900", icon: ShoppingBag },
  { key: "flipkart", name: "Flipkart", category: "Ecommerce", status: "Active", requiredFiles: ["Sales report Excel", "Cash Back report if available", "Next month report if needed"], guide: "Reports Center > Tax Reports > Sales report", accent: "from-yellow-300 to-blue-600", icon: PackageCheck },
  { key: "meesho", name: "Meesho", category: "Ecommerce", status: "Active", requiredFiles: ["tcs_sales.xlsx", "tcs_sales_return.xlsx", "Tax_invoice_details.xlsx"], guide: "Payments > Download GST Reports", accent: "from-pink-500 to-rose-600", icon: Store },
  { key: "myntra", name: "Myntra", category: "Ecommerce", status: "Beta", requiredFiles: ["Sales report"], guide: "Upload Myntra GST report", accent: "from-pink-500 to-orange-400", icon: ShoppingBag },
  { key: "ajio", name: "Ajio", category: "Ecommerce", status: "Coming Soon", requiredFiles: ["Sales report"], guide: "Ajio seller tax report", accent: "from-slate-800 to-slate-500", icon: ShoppingBag },
  { key: "snapdeal", name: "Snapdeal", category: "Ecommerce", status: "Beta", requiredFiles: ["Sales report"], guide: "Snapdeal tax report", accent: "from-red-500 to-pink-500", icon: Store },
  { key: "jiomart", name: "JioMart", category: "Ecommerce", status: "Beta", requiredFiles: ["Sales report"], guide: "JioMart seller tax report", accent: "from-blue-600 to-red-500", icon: Store },
  { key: "tatacliq", name: "Tata CliQ", category: "Ecommerce", status: "Coming Soon", requiredFiles: ["Sales report"], guide: "Tata CliQ sales report", accent: "from-slate-900 to-red-500", icon: ShoppingBag },
  { key: "blinkit", name: "Blinkit", category: "Quick Commerce", status: "Coming Soon", requiredFiles: ["Sales report"], guide: "Blinkit seller report", accent: "from-yellow-300 to-green-600", icon: Zap },
  { key: "zepto", name: "Zepto", category: "Quick Commerce", status: "Coming Soon", requiredFiles: ["Sales report"], guide: "Zepto seller report", accent: "from-purple-500 to-pink-500", icon: Zap },
  { key: "swiggy-instamart", name: "Swiggy Instamart", category: "Food", status: "Coming Soon", requiredFiles: ["Sales report"], guide: "Swiggy Instamart report", accent: "from-orange-500 to-red-500", icon: Utensils },
  { key: "bigbasket", name: "BigBasket", category: "Quick Commerce", status: "Coming Soon", requiredFiles: ["Sales report"], guide: "BigBasket report", accent: "from-green-600 to-lime-400", icon: Zap },
  { key: "udaan", name: "Udaan", category: "B2B", status: "Coming Soon", requiredFiles: ["B2B sales report"], guide: "Udaan seller report", accent: "from-blue-500 to-cyan-400", icon: Building2 },
  { key: "indiamart", name: "IndiaMART", category: "B2B", status: "Coming Soon", requiredFiles: ["Invoice report"], guide: "IndiaMART transaction report", accent: "from-blue-700 to-sky-500", icon: Building2 },
  { key: "shopify", name: "Shopify", category: "Accounting", status: "Beta", requiredFiles: ["Orders CSV"], guide: "Shopify orders export", accent: "from-green-600 to-emerald-400", icon: BadgeIndianRupee },
  { key: "woocommerce", name: "WooCommerce", category: "Accounting", status: "Beta", requiredFiles: ["Orders CSV"], guide: "WooCommerce orders export", accent: "from-purple-700 to-violet-400", icon: BadgeIndianRupee },
  { key: "custom", name: "Custom Excel", category: "Accounting", status: "Active", requiredFiles: ["Mapped Excel/CSV"], guide: "Use GST Bharat common schema template", accent: "from-slate-700 to-slate-400", icon: BadgeIndianRupee }
];

export const marketplaceCategories = ["Ecommerce", "Quick Commerce", "B2B", "Food", "Accounting"] as const;
