import {
  BadgeIndianRupee,
  Building2,
  PackageCheck,
  ShoppingBag,
  Store,
} from "lucide-react";

const marketplaceIcons = {
  amazon: ShoppingBag,
  flipkart: PackageCheck,
  meesho: Store,
  custom: BadgeIndianRupee,
  default: Building2,
};

export function marketplaceIconFor(key: string) {
  return marketplaceIcons[key as keyof typeof marketplaceIcons] || marketplaceIcons.default;
}
