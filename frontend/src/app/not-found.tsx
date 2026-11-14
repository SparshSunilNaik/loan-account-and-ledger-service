import Link from "next/link";
export default function NotFound() {
  return (
    <div className="panel p-8">
      <h1>Account not found</h1>
      <p className="lede">Use the exact loan UUID returned by the backend.</p>
      <Link href="/workspace" className="button button-primary mt-6">
        Open loan workspace
      </Link>
    </div>
  );
}
