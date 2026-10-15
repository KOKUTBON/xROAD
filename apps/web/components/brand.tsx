"use client";

import { publicAsset } from "@/lib/demo-mode";

import { useInstitution } from "@/components/institution-provider";

export function BrandMark({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  const { config } = useInstitution();
  const logoSrc = config?.brand_logo_url || "/brand/road-accidents-risk-modeling-icon.svg";

  return (
    <img
      src={publicAsset(logoSrc)}
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      className={className}
      draggable={false}
    />
  );
}

export function BrandLockup({
  tagline,
  size = 44,
}: {
  tagline?: string;
  size?: number;
}) {
  const { config } = useInstitution();
  const effectiveTagline = tagline ?? config?.portal_subtitle ?? "Predictive safety intelligence for roads";
  const logoSrc = config?.brand_logo_url || "/brand/road-accidents-risk-modeling-icon.svg";
  const brandName = config?.brand_name || "xROAD";

  return (
    <div className="brand-lockup">
      <img
        src={publicAsset(logoSrc)}
        width={size}
        height={size}
        alt={`${brandName} logo`}
        className="brand-lockup-mark"
        draggable={false}
      />
      <span className="brand-lockup-text">
        <strong>{brandName}</strong>
        {effectiveTagline ? <small>{effectiveTagline}</small> : null}
      </span>
    </div>
  );
}
