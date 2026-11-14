import { redirect } from "next/navigation";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ loanId?: string }>;
}) {
  const { loanId } = await searchParams;
  redirect(
    "/testing" + (loanId ? "?loanId=" + encodeURIComponent(loanId) : ""),
  );
}
