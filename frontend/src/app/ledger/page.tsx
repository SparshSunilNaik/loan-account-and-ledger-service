import { redirect } from "next/navigation";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ loanId?: string }>;
}) {
  const { loanId } = await searchParams;
  redirect(
    "/activity?view=journals" +
      (loanId ? "&loanId=" + encodeURIComponent(loanId) : ""),
  );
}
