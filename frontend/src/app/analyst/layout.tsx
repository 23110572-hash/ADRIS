import type { ReactNode } from "react";
import { AnalystAccess } from "@/features/analyst/access";
import { AnalystShell } from "@/features/analyst/shell";

export default function AnalystLayout({ children }: { children: ReactNode }) {
  return (
    <AnalystShell>
      <AnalystAccess>{children}</AnalystAccess>
    </AnalystShell>
  );
}
