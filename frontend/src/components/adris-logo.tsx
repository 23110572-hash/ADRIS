import React from "react";

export function AdrisLogo({ className = "", size = "md" }: { className?: string; size?: "sm" | "md" | "lg" | "xl" }) {
  const sizes = {
    sm: { icon: "size-6", text: "text-lg" },
    md: { icon: "size-9", text: "text-2xl" },
    lg: { icon: "size-12", text: "text-3xl" },
    xl: { icon: "size-16", text: "text-4xl" }
  };
  const { icon, text } = sizes[size];
  
  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      <svg className={icon} viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="shieldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#06b6d4" /> {/* Turquoise */}
            <stop offset="100%" stopColor="#1d4ed8" /> {/* Sapphire Blue */}
          </linearGradient>
        </defs>
        {/* Shield outline / fill in Turquoise -> Sapphire Blue Gradient */}
        <path 
          d="M256 72 410 132v108c0 98-62 164-154 202C164 404 102 338 102 240V132l154-60Z" 
          fill="url(#shieldGradient)" 
        />
        {/* White checkmark inside */}
        <path 
          d="m171 254 54 54 118-126" 
          fill="none" 
          stroke="#ffffff" 
          strokeWidth="38" 
          strokeLinecap="round" 
          strokeLinejoin="round" 
        />
      </svg>
      {/* Deep Navy Text for ADRIS */}
      <span className={`font-black tracking-wider text-[#0a192f] ${text}`}>
        ADRIS
      </span>
    </div>
  );
}
