import {
  BadgeIndianRupee,
  Building2,
  PackageCheck,
  ShoppingBag,
  Store,
} from "lucide-react";

const marketplaceIcons = {
  amazon: ShoppingBag,
  flipkart: ShoppingBag,
  meesho: Store,
  myntra: ShoppingBag,
  jiomart: Store,
  snapdeal: ShoppingBag,
  blinkit: BadgeIndianRupee,
  ajio: PackageCheck,
  tatacliq: ShoppingBag,
  nykaa: BadgeIndianRupee,
  shopify: ShoppingBag,
  zomato: Store,
  swiggy: PackageCheck,
  firstcry: PackageCheck,
  paytm: BadgeIndianRupee,
  custom: BadgeIndianRupee,
  default: Building2,
};

export function marketplaceIconFor(key: string) {
  const normalized = key?.toLowerCase().trim();
  return marketplaceIcons[normalized as keyof typeof marketplaceIcons] || marketplaceIcons.default;
}
