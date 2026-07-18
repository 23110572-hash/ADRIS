import { LockKeyhole, ShieldCheck } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function CheckIntro({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-6 grid gap-3 sm:grid-cols-2">
      <Alert className="border-emerald-200 bg-emerald-50 text-emerald-950">
        <ShieldCheck className="mb-2 size-5" />
        <AlertTitle>Decision support, not a verdict</AlertTitle>
        <AlertDescription>ADRIS identifies risk signals and uncertainty. It never proves that a person is legitimate or criminal.</AlertDescription>
      </Alert>
      <Alert className="border-slate-200 bg-slate-50 text-slate-800">
        <LockKeyhole className="mb-2 size-5" />
        <AlertTitle>Submit only what you may share</AlertTitle>
        <AlertDescription>{children}</AlertDescription>
      </Alert>
    </div>
  );
}
